#! /usr/bin/python3

# Phomemo M832D Bluetooth Low Energy backend.
#
# The M832D is BLE-only: it has no RFCOMM channel, so the phomemo backend hands
# whitelisted queues to this script. It carries the filter output byte-for-byte
# and in order over the FF02 write characteristic, and forwards FF03
# notifications to the filter on the CUPS back channel.
#
# The printer is selected by the explicit address in the device URI, never by
# advertised name, and the LE bearer is chosen explicitly rather than by falling
# back to Classic Bluetooth. Characteristics are resolved by UUID; numeric ATT
# handles taken from captures are never used as configuration.
#
# Nothing here proves physical print completion. A byte is counted as submitted
# before its write is awaited, because an error cannot prove non-delivery, and
# only becomes acknowledged after the ATT response. An acknowledgement confirms
# transport acceptance, not printing. No retry is attempted once data may have
# reached the printer.

import asyncio
import ctypes
import ctypes.util
import errno
import fcntl
import os
import re
import select
import signal
import stat
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

WRITE_UUID = '0000ff02-0000-1000-8000-00805f9b34fb'
NOTIFY_UUID = '0000ff03-0000-1000-8000-00805f9b34fb'

# CUPS backend exit codes
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_HOLD = 3
EXIT_STOP = 4
EXIT_CANCEL = 5
EXIT_RETRY = 6

# CUPS side-channel commands and statuses
SIDE_DRAIN_OUTPUT = 2
SIDE_GET_BIDI = 3
SIDE_GET_STATE = 5
SIDE_GET_CONNECTED = 8
SIDE_OK = 1
SIDE_IO_ERROR = 2
SIDE_TIMEOUT = 3
SIDE_NOT_IMPLEMENTED = 7

# Bounds for one explicitly addressed printer. The 182-byte default is the tested
# acknowledged-write ceiling, not a claim about every negotiated MTU. These bound
# scanning, setup, pairing and individual writes rather than the whole job.
DEFAULT_CHUNK = 182
SCAN_TIMEOUT = 20.0
CONNECT_TIMEOUT = 25.0
WRITE_TIMEOUT = 15.0
BUS_TIMEOUT = 5.0
CALL_TIMEOUT = 30.0
CLEANUP_TIMEOUT = 5.0
DRAIN_TIMEOUT = 60.0

ADDRESS_RE = re.compile(r'^[0-9A-Fa-f]{12}$')
ADAPTER_RE = re.compile(r'^hci[0-9]+$')

AGENT_MANAGER_PATH = '/org/bluez'
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_MANAGER_INTERFACE = 'org.bluez.AgentManager1'
DEVICE_INTERFACE = 'org.bluez.Device1'
LE_BEARER_INTERFACE = 'org.bluez.Bearer.LE1'


class SetupRequiredError(RuntimeError):
    """The selected device needs setup before printing can continue."""


class PairingRequiredError(SetupRequiredError):
    """The selected device is not paired on its LE bearer."""


class PairingFailedError(SetupRequiredError):
    """Automatic pairing could not establish a verified LE bond."""


class CancelledError(RuntimeError):
    """The scheduler or user cancelled the job."""


class TransportCleanupError(RuntimeError):
    """The BLE transport could not confirm that its connection was closed."""


def error(message):
    print('ERROR: ' + message, file=sys.stderr, flush=True)


def debug(message):
    print('DEBUG: ' + message, file=sys.stderr, flush=True)


def state(add = None, remove = None):
    if add:
        print('STATE: +' + add, file=sys.stderr, flush=True)
    if remove:
        print('STATE: -' + remove, file=sys.stderr, flush=True)


def parse_address(text):
    # Accept the compact form the phomemo backend emits as well as the separated
    # form; an advertised name is never a valid address.
    clean = text.replace(':', '').replace('-', '')
    if not ADDRESS_RE.fullmatch(clean):
        raise ValueError('Device URI must contain an explicit Bluetooth address')
    return ':'.join(clean[i:i + 2] for i in range(0, 12, 2)).upper()


def single_value(query, name):
    values = query.get(name)
    if values is None:
        return None
    if len(values) != 1 or not values[0]:
        raise ValueError('%s must appear exactly once with a value' % name)
    return values[0]


def parse_device_uri(uri):
    parsed = urlsplit(uri)
    if parsed.scheme not in ('phomemo', 'phomemo-ble') or not parsed.netloc \
            or parsed.path not in ('', '/'):
        raise ValueError('Expected phomemo://AA-BB-CC-DD-EE-FF/?adapter=hci0')
    if parsed.username or parsed.password or parsed.port:
        raise ValueError('Credentials and ports are not valid in a Bluetooth device URI')
    address = parse_address(parsed.hostname or '')
    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    unknown = set(query) - {'adapter', 'chunk_size'}
    if unknown:
        raise ValueError('Unknown device URI option: %s' % sorted(unknown)[0])
    adapter = single_value(query, 'adapter')
    if adapter is not None and not ADAPTER_RE.fullmatch(adapter):
        raise ValueError('Adapter must be named hci followed by digits')
    chunk_text = single_value(query, 'chunk_size')
    chunk_size = DEFAULT_CHUNK if chunk_text is None else int(chunk_text)
    if not 1 <= chunk_size <= DEFAULT_CHUNK:
        raise ValueError('chunk_size must be in 1..%d' % DEFAULT_CHUNK)
    return address, adapter, chunk_size


def parse_invocation(argv):
    if len(argv) not in (6, 7):
        raise ValueError('Expected job-id user title copies options [filename]')
    try:
        copies = int(argv[4])
    except ValueError:
        raise ValueError('copies must be an integer') from None
    if copies < 1:
        raise ValueError('copies must be positive')
    return argv[1], argv[2], argv[3], copies, argv[5], argv[6] if len(argv) == 7 else None


def fd_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


class CupsChannels:
    """Synchronous libcups ABI for the CUPS back (fd 3) and side (fd 4) channels.

    FF03 values are written raw to the printer-to-filter back channel, where a
    partial write is an error; side-channel requests and responses use fd 4.
    """

    def __init__(self):
        name = ctypes.util.find_library('cups')
        if not name:
            raise RuntimeError('libcups is required for CUPS channel support')
        self.lib = ctypes.CDLL(name, use_errno=True)
        self.lib.cupsBackChannelWrite.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double]
        self.lib.cupsBackChannelWrite.restype = ctypes.c_ssize_t
        self.lib.cupsSideChannelRead.argtypes = [
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int), ctypes.c_double,
        ]
        self.lib.cupsSideChannelRead.restype = ctypes.c_int
        self.lib.cupsSideChannelWrite.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_double,
        ]
        self.lib.cupsSideChannelWrite.restype = ctypes.c_int

    def write_back(self, data, timeout = 1.0):
        if not data or not fd_open(3):
            return
        buffer = ctypes.create_string_buffer(data)
        written = self.lib.cupsBackChannelWrite(buffer, len(data), timeout)
        if written != len(data):
            raise OSError(ctypes.get_errno(),
                          'CUPS back-channel wrote %d/%d bytes' % (written, len(data)))

    def read_side(self, timeout = 0.1):
        if not fd_open(4):
            return None
        command = ctypes.c_int()
        status = ctypes.c_int()
        capacity = ctypes.c_int(2048)
        buffer = ctypes.create_string_buffer(capacity.value)
        if self.lib.cupsSideChannelRead(ctypes.byref(command), ctypes.byref(status),
                                        buffer, ctypes.byref(capacity), timeout) != 0:
            return None
        return command.value, buffer.raw[:capacity.value]

    def write_side(self, command, status, data = b'', timeout = 1.0):
        if not fd_open(4):
            return
        buffer = ctypes.create_string_buffer(data) if data else None
        if self.lib.cupsSideChannelWrite(int(command), int(status), buffer,
                                         len(data), timeout) != 0:
            raise OSError(ctypes.get_errno(), 'Unable to write CUPS side-channel response')


class PrinterLock:
    """Prevent backend processes from interleaving bytes for one printer.

    Contention fails immediately rather than waiting or retrying. The private
    owner-only directory, no-follow open where available, and post-open regular
    file/owner checks reject unsafe ownership, file types and symlinks.
    """

    def __init__(self, key):
        root = os.environ.get('PHOMEMO_BLE_LOCK_DIR')
        if not root:
            root = os.path.join(tempfile.gettempdir(), 'phomemo-ble-%d' % os.getuid())
        self.path = os.path.join(root, 'phomemo-ble-%s.lock' % key)
        self.file = None

    def __enter__(self):
        try:
            os.makedirs(os.path.dirname(self.path), mode = 0o700)
        except FileExistsError:
            pass
        details = os.lstat(os.path.dirname(self.path))
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid() \
                or stat.S_IMODE(details.st_mode) & 0o077:
            raise RuntimeError('Printer lock directory must be private and owned by the backend user')

        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid():
            os.close(descriptor)
            raise RuntimeError('Printer lock file has unsafe ownership or type')
        self.file = os.fdopen(descriptor, 'r+')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            self.file = None
            raise RuntimeError('Printer is already in use by another backend process') from None
        self.file.seek(0)
        self.file.truncate()
        self.file.write('%d\n' % os.getpid())
        self.file.flush()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.file is not None:
            fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()
            self.file = None


from dbus_fast import BusType, DBusError, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method


class ExactDeviceAgent(ServiceInterface):
    """Temporary exact-device Just Works authorization without credentials.

    Confirmation and authorization are accepted only for the configured object
    path. PIN, passkey and display flows are rejected because the backend does
    not support interactive credentials. The agent is never made BlueZ's default
    agent.
    """

    def __init__(self, device_path):
        super().__init__(AGENT_INTERFACE)
        self.device_path = device_path

    def require_device(self, device):
        if device != self.device_path:
            raise DBusError('org.bluez.Error.Rejected', 'Unexpected pairing device')

    def reject_credentials(self, device):
        self.require_device(device)
        raise DBusError('org.bluez.Error.Rejected',
                        'The printer requires interactive PIN or passkey entry')

    @method()
    def Release(self):
        pass

    @method()
    def RequestPinCode(self, device: 'o') -> 's':
        self.reject_credentials(device)

    @method()
    def DisplayPinCode(self, device: 'o', pincode: 's'):
        self.reject_credentials(device)

    @method()
    def RequestPasskey(self, device: 'o') -> 'u':
        self.reject_credentials(device)

    @method()
    def DisplayPasskey(self, device: 'o', passkey: 'u', entered: 'q'):
        self.reject_credentials(device)

    @method()
    def RequestConfirmation(self, device: 'o', passkey: 'u'):
        self.require_device(device)

    @method()
    def RequestAuthorization(self, device: 'o'):
        self.require_device(device)

    @method()
    def AuthorizeService(self, device: 'o', uuid: 's'):
        self.require_device(device)

    @method()
    def Cancel(self):
        pass


def property_bool(properties, name):
    value = getattr(properties.get(name), 'value', properties.get(name))
    return value if isinstance(value, bool) else None


def unsupported_inspection(exc):
    return any(marker in str(exc) for marker in
               ('UnknownMethod', 'UnknownInterface', 'NotSupported'))


async def connect_bus(timeout = BUS_TIMEOUT):
    return await asyncio.wait_for(MessageBus(bus_type = BusType.SYSTEM).connect(), timeout)


async def make_call(bus, path):
    async def call(interface, member, signature = '', body = None, target = None):
        # Cap every D-Bus call independently and normalize BlueZ error replies so
        # only explicit unsupported-capability errors enter fallback branches.
        reply = await asyncio.wait_for(bus.call(Message(
            destination = 'org.bluez', path = target or path, interface = interface,
            member = member, signature = signature, body = body or [],
        )), CALL_TIMEOUT)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('%s: %s' % (reply.error_name, reply.body))
        return reply

    return call


async def property_value(call, name, target = None, interface = DEVICE_INTERFACE):
    reply = await call('org.freedesktop.DBus.Properties', 'Get', 'ss',
                       [interface, name], target = target)
    return getattr(reply.body[0], 'value', reply.body[0])


async def wait_or_cancel(awaitable, cancel_event, timeout, operation):
    """Race one bounded operation against cancellation without retrying it.

    Cancellation wins if both tasks complete together. Abandoned work is cancelled
    and awaited so no write or connection attempt survives the result; after a
    timeout the remote side may nevertheless already have acted.
    """
    task = asyncio.create_task(awaitable)
    cancellation = asyncio.create_task(cancel_event.wait())
    try:
        done, _ = await asyncio.wait({task, cancellation}, timeout = timeout,
                                     return_when = asyncio.FIRST_COMPLETED)
        if cancellation in done and cancellation.result():
            task.cancel()
            await asyncio.gather(task, return_exceptions = True)
            raise CancelledError('Job cancelled during BLE %s; accepted data may still print' % operation)
        if task not in done:
            task.cancel()
            await asyncio.gather(task, return_exceptions = True)
            raise TimeoutError('BLE %s timed out after %gs' % (operation, timeout))
        return task.result()
    finally:
        cancellation.cancel()
        await asyncio.gather(cancellation, return_exceptions = True)


async def pairing_state(call, device_path, discovered_props = None):
    """Return verified paired state, preferring exported LE bearer state.

    Every exported LE bearer must be paired, and an explicit Bonded=False
    invalidates Paired=True; an absent Bonded is tolerated for older BlueZ.
    Unsupported inspection APIs and inconclusive replies fall through to less
    detailed state rather than silently trusting stale discovery properties.
    """
    discovered_props = discovered_props or {}
    try:
        reply = await call('org.freedesktop.DBus.ObjectManager', 'GetManagedObjects',
                           target = '/')
    except RuntimeError as exc:
        if not unsupported_inspection(exc):
            raise
    else:
        bearers = []
        device_state = None
        for path, interfaces in reply.body[0].items():
            if path == device_path and DEVICE_INTERFACE in interfaces:
                properties = interfaces[DEVICE_INTERFACE]
                device_state = property_bool(properties, 'Paired') is True \
                    and property_bool(properties, 'Bonded') is not False
            if path != device_path and not path.startswith(device_path + '/'):
                continue
            properties = interfaces.get(LE_BEARER_INTERFACE)
            if properties is not None:
                bearers.append(property_bool(properties, 'Paired') is True
                               and property_bool(properties, 'Bonded') is not False)
        if bearers:
            return all(bearers)
        if device_state is not None:
            return device_state

    try:
        reply = await call('org.freedesktop.DBus.Properties', 'GetAll', 's',
                           [DEVICE_INTERFACE], target = device_path)
    except RuntimeError as exc:
        if not unsupported_inspection(exc):
            raise
    else:
        properties = reply.body[0]
        if property_bool(properties, 'Paired') is not None:
            return property_bool(properties, 'Paired') is True \
                and property_bool(properties, 'Bonded') is not False

    paired = discovered_props.get('Paired')
    bonded = discovered_props.get('Bonded')
    if isinstance(paired, bool):
        return paired is True and bonded is not False
    return None


async def cancel_pairing(call, device_path):
    try:
        await call(DEVICE_INTERFACE, 'CancelPairing', target = device_path)
    except Exception:
        pass


async def ensure_paired(bus, call, device_path, discovered_props, cancel_event, timeout,
                        pairing_callback = None):
    """Pair once through a temporary non-default agent and verify the LE bond.

    Pairing is refused when existing bond state cannot be inspected. Completion is
    rechecked before returning, and timeout or cancellation requests CancelPairing.
    Trust is deliberately applied later, only after verification.
    """
    try:
        paired = await pairing_state(call, device_path, discovered_props)
    except PairingRequiredError:
        raise
    except Exception as exc:
        raise PairingFailedError('Unable to inspect the configured LE pairing state: %s' % exc) from exc
    if paired is True:
        return False
    if paired is None:
        raise PairingRequiredError('BlueZ did not expose enough state to verify the configured LE bond')

    pairing_callback = pairing_callback or (lambda active: None)
    pairing_callback(True)
    agent_path = '/org/phomemo_ble/agent/%d_%x' % (os.getpid(), id(bus))
    agent = ExactDeviceAgent(device_path)
    registered = False
    exported = False
    try:
        bus.export(agent_path, agent)
        exported = True
        await call(AGENT_MANAGER_INTERFACE, 'RegisterAgent', 'os',
                   [agent_path, 'NoInputNoOutput'], target = AGENT_MANAGER_PATH)
        registered = True
        try:
            await wait_or_cancel(call(DEVICE_INTERFACE, 'Pair', target = device_path),
                                 cancel_event, timeout, 'pairing')
        except asyncio.CancelledError:
            await cancel_pairing(call, device_path)
            raise
        except Exception:
            await cancel_pairing(call, device_path)
            raise
        if await pairing_state(call, device_path, discovered_props) is not True:
            raise PairingFailedError('BlueZ completed pairing without a verifiable LE bond')
        return True
    except CancelledError:
        raise
    except PairingFailedError:
        raise
    except Exception as exc:
        raise PairingFailedError('Automatic LE pairing failed: %s' % exc) from exc
    finally:
        if registered:
            try:
                await call(AGENT_MANAGER_INTERFACE, 'UnregisterAgent', 'o', [agent_path],
                           target = AGENT_MANAGER_PATH)
            except Exception:
                pass
        try:
            if exported:
                bus.unexport(agent_path, agent)
        finally:
            pairing_callback(False)


async def device_connected(call, path):
    value = await property_value(call, 'Connected', target = path)
    if not isinstance(value, bool):
        raise RuntimeError('BlueZ Device1.Connected did not contain a boolean')
    return value


async def connect_device(call):
    try:
        await call(DEVICE_INTERFACE, 'Connect')
    except RuntimeError as exc:
        if 'AlreadyConnected' not in str(exc):
            raise


async def ensure_preferred_le(call):
    """Provision and verify the exact device's persistent LE preference."""
    try:
        value = await property_value(call, 'PreferredBearer')
        if value == 'le':
            return False
        await call('org.freedesktop.DBus.Properties', 'Set', 'ssv',
                   [DEVICE_INTERFACE, 'PreferredBearer', Variant('s', 'le')])
        value = await property_value(call, 'PreferredBearer')
    except RuntimeError as exc:
        raise SetupRequiredError(
            'Unable to provision PreferredBearer=le for the configured printer: %s' % exc) from exc
    if value != 'le':
        raise SetupRequiredError('BlueZ did not retain PreferredBearer=le for the configured printer')
    return True


async def connect_with_provisioned_le(call):
    """Verify an administrator-provisioned LE preference without changing it."""
    if await property_value(call, 'PreferredBearer') != 'le':
        raise SetupRequiredError('BlueZ PreferredBearer must be provisioned as le before printing')
    await connect_device(call)


async def ensure_trusted(call, discovered_props = None):
    """Trust only the exact configured device after its LE bond is verified."""
    discovered_props = discovered_props or {}
    if discovered_props.get('Trusted') is True:
        return False
    try:
        if await property_value(call, 'Trusted') is True:
            return False
        await call('org.freedesktop.DBus.Properties', 'Set', 'ssv',
                   [DEVICE_INTERFACE, 'Trusted', Variant('b', True)])
        value = await property_value(call, 'Trusted')
    except RuntimeError as exc:
        raise SetupRequiredError('Unable to trust the configured printer after pairing: %s' % exc) from exc
    if value is not True:
        raise SetupRequiredError('BlueZ did not retain Trusted=true for the configured printer')
    return True


async def explicit_le_connect(device, configured_adapter = None, cancel_event = None,
                              allow_pairing = False, pairing_callback = None):
    """Connect the exact BlueZ device without an ambiguous bearer fallback.

    An existing exact-address connection is adopted. Otherwise this prefers
    Adapter1.ConnectDevice, permits generic Device1.Connect only for a sole new LE
    bond, a random address, or a verified PreferredBearer=le, and fails closed for
    an ambiguous public-address device. Pairing and connection each receive one
    bounded attempt; connections created during a failed attempt are rolled back
    best-effort.
    """
    path = device.details.get('path')
    props = device.details.get('props', {})
    if not path:
        raise RuntimeError('BlueZ discovery did not provide a device object path')
    adapter_path = path.rsplit('/', 1)[0]
    if configured_adapter and adapter_path.rsplit('/', 1)[-1] != configured_adapter:
        raise RuntimeError('Printer was discovered through an adapter other than the configured adapter')
    address_type = props.get('AddressType')
    if address_type not in ('public', 'random'):
        raise RuntimeError('BlueZ discovery did not provide an LE address type')
    if not allow_pairing and props.get('Paired') is not True:
        raise PairingRequiredError(
            'Configured printer is not paired on the LE bearer; diagnostics do not initiate pairing')

    bus = await connect_bus()
    call = await make_call(bus, path)

    initial_connected = False
    owns_connection = False
    try:
        initial_connected = await device_connected(call, path)
        if initial_connected:
            # A connected printer may stop advertising. Bleak can adopt it using
            # the BlueZ object path discovered above.
            return True

        newly_paired = False
        if allow_pairing:
            if address_type == 'public':
                await ensure_preferred_le(call)
            newly_paired = await ensure_paired(bus, call, path, props,
                                               cancel_event or asyncio.Event(),
                                               CONNECT_TIMEOUT, pairing_callback)
            await ensure_trusted(call, props)
        if newly_paired:
            if await device_connected(call, path):
                # Device1.Pair connected over the LE discovery path and completed
                # service discovery. Keep that selected bearer for Bleak to reuse.
                return True
            # The new LE bond is the only bond because pairing was entered only
            # after verifying that no bond existed. BlueZ selects the sole bonded
            # bearer even when its experimental bearer-selection APIs are absent.
            await connect_device(call)
            return True

        try:
            await call('org.bluez.Adapter1', 'ConnectDevice', 'a{sv}', [{
                'Address': Variant('s', device.address),
                'AddressType': Variant('s', address_type),
            }], target = adapter_path)
            owns_connection = True
        except RuntimeError as exc:
            if 'AlreadyConnected' in str(exc):
                owns_connection = True
            elif not any(marker in str(exc) for marker in ('UnknownMethod', 'NotSupported')):
                raise
            else:
                try:
                    await connect_with_provisioned_le(call)
                except SetupRequiredError:
                    raise
                except RuntimeError as fallback:
                    if not unsupported_inspection(fallback):
                        raise
                    if address_type == 'random':
                        # A random Bluetooth address cannot identify a BR/EDR
                        # bearer, so Device1.Connect remains explicitly LE.
                        await connect_device(call)
                    else:
                        raise RuntimeError(
                            'BlueZ cannot select an LE bearer explicitly for this '
                            'public-address device; ConnectDevice or PreferredBearer '
                            'support is required') from fallback
        return owns_connection
    except BaseException:
        if not initial_connected:
            try:
                if await device_connected(call, path):
                    await call(DEVICE_INTERFACE, 'Disconnect')
            except Exception:
                pass
        raise
    finally:
        bus.disconnect()


async def find_connected_device(address, adapter):
    """Recover an exact configured LE device that is not advertising."""
    from bleak.backends.device import BLEDevice

    bus = await connect_bus(SCAN_TIMEOUT)
    try:
        reply = await asyncio.wait_for(bus.call(Message(
            destination = 'org.bluez', path = '/',
            interface = 'org.freedesktop.DBus.ObjectManager',
            member = 'GetManagedObjects', signature = '', body = [],
        )), SCAN_TIMEOUT)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('%s: %s' % (reply.error_name, reply.body))
        for path, interfaces in reply.body[0].items():
            props = interfaces.get(DEVICE_INTERFACE)
            if props is None:
                continue
            props = {name: getattr(value, 'value', value) for name, value in props.items()}
            if str(props.get('Address', '')).lower() != address.lower():
                continue
            if adapter and path.rsplit('/', 1)[0].rsplit('/', 1)[-1] != adapter:
                continue
            if props.get('Connected') is not True:
                continue
            if props.get('AddressType') not in ('public', 'random'):
                continue
            return make_ble_device(BLEDevice, address,
                                   props.get('Alias') or props.get('Name') or '',
                                   {'path': path, 'props': props}, props.get('RSSI', -127))
        return None
    finally:
        bus.disconnect()


def make_ble_device(device_type, address, name, details, rssi):
    """Construct a Bleak device across legacy and current Bleak APIs."""
    try:
        return device_type(address, name, details)
    except TypeError as exc:
        text = str(exc)
        if 'missing' not in text or 'required positional argument' not in text \
                or "'rssi'" not in text:
            raise
        return device_type(address, name, details, rssi = rssi)


def is_authentication_error(exc):
    text = str(exc).lower()
    return any(marker in text for marker in ('authentication', 'not authorized',
                                             'notauthorized', 'insufficient authentication'))


class BleTransport:
    """Exact-address, explicit-LE transport for one ordered byte stream.

    Characteristics are resolved by UUID for each connection and writes are
    serialized with ATT responses; no transport retry is performed. A byte is
    submitted before its write is awaited because an error cannot prove
    non-delivery, and is acknowledged only after that await succeeds. Both
    counters describe host-side transport, not physical printing.
    """

    def __init__(self, address, adapter, chunk_size, notification_callback,
                 cancel_event = None, pairing_callback = None, allow_pairing = True):
        self.address = address
        self.adapter = adapter
        self.chunk_size = chunk_size
        self.notification_callback = notification_callback
        self.cancel_event = cancel_event or asyncio.Event()
        self.pairing_callback = pairing_callback or (lambda active: None)
        self.allow_pairing = allow_pairing
        self.client = None
        self.device_path = None
        self.owns_connection = False
        self.write_characteristic = None
        self.notify_characteristic = None
        self.notifications_started = False
        self.submitted_bytes = 0
        self.acknowledged_bytes = 0

    async def connect(self):
        """Select the exact LE device and establish the required GATT channels."""
        from bleak import BleakClient, BleakScanner

        # A connected printer may stop advertising. Check BlueZ first so the
        # filter can begin its readiness exchange without waiting for a full
        # discovery timeout.
        device = await find_connected_device(self.address, self.adapter)
        if device is None:
            options = {'bluez': {'filters': {'Transport': 'le'}}}
            if self.adapter:
                options['adapter'] = self.adapter
            device = await BleakScanner.find_device_by_filter(
                lambda found, advertisement: found.address.lower() == self.address.lower(),
                timeout = SCAN_TIMEOUT, **options)
        if device is None:
            raise RuntimeError('Configured printer was not found during the bounded LE '
                               'scan or as an already-connected BlueZ LE device')

        self.device_path = device.details.get('path')
        try:
            self.owns_connection = await explicit_le_connect(device, self.adapter,
                                                             self.cancel_event, self.allow_pairing,
                                                             self.pairing_callback)
        except Exception as exc:
            if is_authentication_error(exc):
                exc = SetupRequiredError(
                    'LE authentication failed; automatic pairing or bond recovery is required')
            await self.rollback()
            raise exc

        try:
            client = BleakClient(device, timeout = CONNECT_TIMEOUT)
            await wait_or_cancel(client.connect(), self.cancel_event,
                                 CONNECT_TIMEOUT, 'connection')
            self.client = client
        except Exception as exc:
            if is_authentication_error(exc):
                raise SetupRequiredError(
                    'LE authentication failed; automatic pairing or bond recovery is required') from exc
            raise

        # ATT handles vary by device and connection, so captured numeric handles
        # are never production configuration. Acknowledged FF02 writes and FF03
        # notifications are required before any job bytes are accepted.
        self.write_characteristic = self.client.services.get_characteristic(WRITE_UUID)
        self.notify_characteristic = self.client.services.get_characteristic(NOTIFY_UUID)
        if self.write_characteristic is None or self.notify_characteristic is None:
            raise RuntimeError('Required FF02/FF03 characteristics are missing')
        if 'write' not in self.write_characteristic.properties:
            raise RuntimeError('FF02 does not support acknowledged writes')
        if 'notify' not in self.notify_characteristic.properties:
            raise RuntimeError('FF03 does not support notifications')

        try:
            await wait_or_cancel(self.client.start_notify(self.notify_characteristic, self.notify),
                                 self.cancel_event, CONNECT_TIMEOUT, 'notification setup')
            self.notifications_started = True
        except Exception as exc:
            if is_authentication_error(exc):
                exc = SetupRequiredError(
                    'LE authentication failed; automatic pairing or bond recovery is required')
            await self.rollback()
            raise exc

    async def write(self, data):
        """Write opaque bytes sequentially, without delay, framing, or retry."""
        if self.client is None or self.write_characteristic is None:
            raise RuntimeError('BLE transport is not connected')
        for offset in range(0, len(data), self.chunk_size):
            if self.cancel_event.is_set():
                raise CancelledError('Job cancelled; already accepted data may still print')
            chunk = data[offset:offset + self.chunk_size]
            # Advance before the await: timeout, cancellation, or an error leaves
            # peripheral receipt uncertain. An ATT success still does not establish
            # that the printer physically processed the bytes.
            self.submitted_bytes += len(chunk)
            await wait_or_cancel(self.client.write_gatt_char(
                self.write_characteristic, chunk, response = True),
                self.cancel_event, WRITE_TIMEOUT, 'write')
            self.acknowledged_bytes += len(chunk)

    def notify(self, sender, data):
        self.notification_callback(bytes(data))

    async def rollback(self):
        try:
            await self.close()
        except TransportCleanupError:
            pass

    async def close(self):
        """Perform bounded teardown and report an unverified owned disconnect.

        Cleanup continues after individual failures so notifications, Bleak and the
        exact BlueZ connection all get a chance to close. Local state is reset
        before raising because callers use cleanup failure in retry policy.
        """
        client = self.client
        device_path = self.device_path
        owns_connection = self.owns_connection
        cleanup = []
        try:
            if client is not None and self.notify_characteristic is not None \
                    and client.is_connected and self.notifications_started:
                try:
                    await asyncio.wait_for(client.stop_notify(self.notify_characteristic),
                                           CLEANUP_TIMEOUT)
                except Exception as exc:
                    cleanup.append(exc)
        finally:
            if client is not None:
                try:
                    if client.is_connected:
                        await asyncio.wait_for(client.disconnect(), CLEANUP_TIMEOUT)
                except Exception as exc:
                    cleanup.append(exc)
            if owns_connection and device_path is not None:
                try:
                    if await device_connected_path(device_path):
                        await disconnect_device_path(device_path)
                except Exception as exc:
                    cleanup.append(exc)
            self.client = None
            self.device_path = None
            self.owns_connection = False
            self.write_characteristic = None
            self.notify_characteristic = None
            self.notifications_started = False
        if cleanup:
            raise TransportCleanupError('BLE teardown failed: %s' % cleanup[-1]) from cleanup[-1]


async def device_connected_path(path):
    """Read the exact device connection state through the system bus."""
    bus = await connect_bus()
    try:
        call = await make_call(bus, path)
        value = await property_value(call, 'Connected')
        if not isinstance(value, bool):
            raise RuntimeError('BlueZ Device1.Connected did not contain a boolean')
        return value
    finally:
        bus.disconnect()


async def disconnect_device_path(path):
    """Disconnect and verify the exact BlueZ device path."""
    bus = await connect_bus()
    try:
        call = await make_call(bus, path)
        await call(DEVICE_INTERFACE, 'Disconnect')
    finally:
        bus.disconnect()
    for _ in range(10):
        if not await device_connected_path(path):
            return
        await asyncio.sleep(0.2)
    raise TimeoutError('BlueZ did not confirm printer disconnection')


class TransferTracker:
    """Track a host-side drain fence, not printer processing or completion.

    produced counts bytes removed from filter input; acknowledged counts bytes
    whose complete transport write returned successfully. A recorded failure wakes
    drain waiters rather than leaving them blocked.
    """

    def __init__(self):
        self.produced = 0
        self.acknowledged = 0
        self.finished = False
        self.failed = None
        self.changed = asyncio.Condition()

    async def add_produced(self, count):
        async with self.changed:
            self.produced += count
            self.changed.notify_all()

    async def add_acknowledged(self, count):
        async with self.changed:
            self.acknowledged += count
            self.changed.notify_all()

    async def wait_acknowledged(self, barrier, timeout = DRAIN_TIMEOUT):
        async def wait():
            async with self.changed:
                await self.changed.wait_for(
                    lambda: self.acknowledged >= barrier or self.failed is not None)
                if self.failed is not None:
                    raise self.failed
        await asyncio.wait_for(wait(), timeout)

    async def capture_drain_barrier(self, source = None):
        """Fence bytes already in the filter pipe before replying to drain.

        Filter output and side-channel requests use separate descriptors, so a
        drain request can be observed just before earlier pipe data. For FIFOs,
        yield until currently readable input has been consumed; other sources use a
        short scheduling fence. The returned count is not evidence of physical
        print completion.
        """
        if source is None:
            observed = self.produced
            while not self.finished and self.failed is None:
                try:
                    async with self.changed:
                        await asyncio.wait_for(
                            self.changed.wait_for(lambda: self.produced != observed), 0.01)
                        observed = self.produced
                except TimeoutError:
                    break
            return self.produced
        try:
            mode = os.fstat(source.fileno()).st_mode
        except (AttributeError, OSError):
            mode = 0
        if stat.S_ISFIFO(mode):
            while not self.finished and self.failed is None:
                if not select.select([source.fileno()], [], [], 0)[0]:
                    break
                await asyncio.sleep(0)
        else:
            await asyncio.sleep(0)
        return self.produced


class BackendRuntime:
    """Coordinate a bounded, ordered data pipeline with the CUPS channels.

    One producer and consumer preserve source order through a bounded data queue.
    FF03 values remain opaque and ordered in a separate bounded queue; overflow is
    fatal rather than silently dropping status bytes. Side- and back-channel pumps
    run concurrently with transmission.
    """

    def __init__(self, transport, channels, source, cancel_event):
        self.transport = transport
        self.channels = channels
        self.source = source
        self.cancel_event = cancel_event
        self.queue = asyncio.Queue(maxsize = 16)
        self.notifications = asyncio.Queue(maxsize = 64)
        self.tracker = TransferTracker()
        self.connected = True
        self.transmitting = False
        self.back_channel_closed = False
        self._stopping = asyncio.Event()
        self._channel_error = None
        self._channel_failed = asyncio.Event()
        self._side_idle = asyncio.Event()

    def notification(self, data):
        """Queue one opaque FF03 value without assigning it status meaning."""
        if self._stopping.is_set():
            return
        try:
            self.notifications.put_nowait(data)
        except asyncio.QueueFull:
            self._channel_error = RuntimeError('Notification queue limit exceeded')
            self._channel_failed.set()

    async def run(self):
        """Supervise transfer and channel tasks, then stop all remaining work."""
        producer = asyncio.create_task(self.produce())
        consumer = asyncio.create_task(self.consume())
        notifier = asyncio.create_task(self.notification_pump())
        side = asyncio.create_task(self.side_channel_pump())
        failure = asyncio.create_task(self._channel_failed.wait())
        data_tasks = {producer, consumer}
        channel_tasks = {notifier, side, failure}
        try:
            while data_tasks:
                done, _ = await asyncio.wait(data_tasks | channel_tasks,
                                             return_when = asyncio.FIRST_COMPLETED)
                if failure in done:
                    raise self._channel_error or RuntimeError('CUPS channel failed')
                for task in done & {notifier, side}:
                    await task
                    raise RuntimeError('CUPS channel pump stopped unexpectedly')
                for task in done & data_tasks:
                    await task
                    data_tasks.remove(task)

            # These bounded waits are flush opportunities for accepted channel
            # work, not printer-completion waits.
            self._side_idle.clear()
            await asyncio.wait_for(self._side_idle.wait(), 0.2)
            if self._channel_failed.is_set():
                raise self._channel_error or RuntimeError('CUPS channel failed')
            for task in (notifier, side):
                if task.done():
                    await task
                    raise RuntimeError('CUPS channel pump stopped unexpectedly')
            await asyncio.wait_for(self.notifications.join(), 2.0)
        finally:
            self._stopping.set()
            try:
                self.notifications.put_nowait(None)
            except asyncio.QueueFull:
                pass
            tasks = data_tasks | channel_tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions = True)

    async def produce(self):
        """Read fixed chunks into the bounded queue and account before enqueue."""
        try:
            while not self.cancel_event.is_set():
                data = await self.read_chunk()
                if not data:
                    break
                await self.tracker.add_produced(len(data))
                await self.queue.put(data)
            if self.cancel_event.is_set():
                raise CancelledError('Job cancelled before all input was submitted')
        finally:
            self.tracker.finished = True
            if asyncio.current_task().cancelling():
                try:
                    self.queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            else:
                await self.queue.put(None)

    async def read_chunk(self):
        """Read files in a worker, but keep pipe reads cancellable by readiness."""
        try:
            fd = self.source.fileno()
            mode = os.fstat(fd).st_mode
        except (AttributeError, OSError):
            return await asyncio.to_thread(self.source.read, 4096)
        if stat.S_ISREG(mode):
            return await asyncio.to_thread(self.source.read, 4096)

        loop = asyncio.get_running_loop()
        ready = loop.create_future()
        cancelled = asyncio.create_task(self.cancel_event.wait())

        def mark_ready():
            if not ready.done():
                ready.set_result(None)

        loop.add_reader(fd, mark_ready)
        try:
            done, _ = await asyncio.wait({ready, cancelled},
                                         return_when = asyncio.FIRST_COMPLETED)
            if cancelled in done and cancelled.result():
                raise CancelledError('Job cancelled while waiting for input')
            return os.read(fd, 4096)
        finally:
            loop.remove_reader(fd)
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions = True)

    async def consume(self):
        """Perform one ordered transport write at a time with no requeue."""
        self.transmitting = True
        try:
            while True:
                data = await self.queue.get()
                if data is None:
                    return
                try:
                    await self.transport.write(data)
                except Exception as exc:
                    self.tracker.failed = exc
                    async with self.tracker.changed:
                        self.tracker.changed.notify_all()
                    raise
                await self.tracker.add_acknowledged(len(data))
        finally:
            self.transmitting = False

    async def notification_pump(self):
        """Forward raw notification values to CUPS fd 3 in callback order."""
        while not self._stopping.is_set():
            data = await self.notifications.get()
            try:
                if data is None:
                    return
                if self.back_channel_closed:
                    continue
                try:
                    await asyncio.to_thread(self.channels.write_back, data)
                except OSError as exc:
                    if not isinstance(exc, BrokenPipeError) \
                            and exc.errno not in (errno.EBADF, errno.EPIPE):
                        raise
                    # The filter has closed fd 3 and cannot consume further
                    # notifications. Continue sending output it already emitted.
                    self.back_channel_closed = True
            finally:
                self.notifications.task_done()

    async def side_channel_pump(self):
        while not self._stopping.is_set():
            request = await asyncio.to_thread(self.channels.read_side, 0.05)
            if request is None:
                self._side_idle.set()
                await asyncio.sleep(0)
                continue
            self._side_idle.clear()
            command, data = request
            if command == SIDE_DRAIN_OUTPUT:
                # OK fences acknowledged transport writes preceding this request;
                # it neither parses printer state nor confirms physical output.
                barrier = await self.tracker.capture_drain_barrier(self.source)
                try:
                    await self.tracker.wait_acknowledged(barrier)
                    status, data = SIDE_OK, b''
                except TimeoutError:
                    status, data = SIDE_TIMEOUT, b''
                except Exception:
                    status, data = SIDE_IO_ERROR, b''
            elif command == SIDE_GET_BIDI:
                status, data = SIDE_OK, b'\x01'
            elif command == SIDE_GET_CONNECTED:
                status, data = SIDE_OK, bytes([1 if self.connected else 0])
            elif command == SIDE_GET_STATE:
                status, data = SIDE_OK, bytes([2 if self.transmitting else 1])
            else:
                status, data = SIDE_NOT_IMPLEMENTED, b''
            await asyncio.to_thread(self.channels.write_side, command, status, data)


async def run_job(invocation, config, channels = None, transport_factory = BleTransport):
    """Run one serialized job and map uncertainty to conservative CUPS exits.

    Failures requiring administrator setup hold the job, cancellation reports
    cancellation, and ordinary failures are retryable only while no write has been
    submitted. Once a write may have reached the printer, including when teardown
    subsequently fails, replay could duplicate output and the queue is stopped
    instead. Success establishes host-side delivery only, never physical print
    completion.
    """
    job_id = invocation[0]
    address, adapter, chunk_size = config
    started = time.monotonic()
    cancel_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, cancel_event.set)
        except NotImplementedError:
            pass

    channels = channels or CupsChannels()
    transport = None
    source = None
    connecting = False
    pairing = False
    cleanup_error = None

    def pairing_status(active):
        nonlocal pairing
        pairing = active
        if active:
            debug('job %s: configured printer is unpaired; pairing automatically' % job_id)
            state(add = 'authentication-required')
        else:
            state(remove = 'authentication-required')

    try:
        source = open(invocation[5], 'rb') if invocation[5] else sys.stdin.buffer
        # Keep the per-printer lock through connection teardown. Releasing it
        # sooner could let another backend interleave with an uncertain session.
        with PrinterLock(address.replace(':', '').lower()):
            try:
                debug('job %s: connecting to configured LE printer' % job_id)
                state(add = 'connecting-to-device')
                connecting = True
                # Notifications cannot arrive until connect() subscribes, after
                # runtime has been assigned, so this closure is safe despite the
                # construction order.
                transport = transport_factory(address, adapter, chunk_size,
                                              lambda data: runtime.notification(data),
                                              cancel_event, pairing_status)
                runtime = BackendRuntime(transport, channels, source, cancel_event)
                connect_task = asyncio.create_task(transport.connect())
                cancel_task = asyncio.create_task(cancel_event.wait())
                done, _ = await asyncio.wait({connect_task, cancel_task},
                                             return_when = asyncio.FIRST_COMPLETED)
                # Cancellation wins a simultaneous race so transmission cannot
                # begin merely because connection setup also completed.
                if cancel_task in done and cancel_task.result():
                    connect_task.cancel()
                    await asyncio.gather(connect_task, return_exceptions = True)
                    raise CancelledError('Job cancelled while connecting')
                cancel_task.cancel()
                await asyncio.gather(cancel_task, return_exceptions = True)
                await connect_task
                state(remove = 'connecting-to-device')
                connecting = False
                debug('job %s: BLE ready; transmitting vendor-filter output' % job_id)
                await runtime.run()
                if runtime.back_channel_closed:
                    debug('job %s: filter closed the back channel; '
                          'remaining notifications were discarded' % job_id)
                debug('job %s: submitted=%d acknowledged=%d elapsed=%.3fs; '
                      'physical completion is unconfirmed'
                      % (job_id, transport.submitted_bytes, transport.acknowledged_bytes,
                         time.monotonic() - started))
                result = EXIT_OK
            finally:
                if transport is not None:
                    try:
                        await transport.close()
                    except Exception as exc:
                        cleanup_error = exc
                        error('job %s: cleanup failed: %s' % (job_id, exc))
            if cleanup_error is not None:
                raise TransportCleanupError(str(cleanup_error)) from cleanup_error
            return result
    except SetupRequiredError as exc:
        error('job %s: setup required: %s' % (job_id, exc))
        state(add = 'authentication-required')
        return EXIT_HOLD
    except CancelledError as exc:
        submitted = transport.submitted_bytes if transport is not None else 0
        acknowledged = transport.acknowledged_bytes if transport is not None else 0
        error('job %s: %s; submitted=%d acknowledged=%d elapsed=%.3fs'
              % (job_id, exc, submitted, acknowledged, time.monotonic() - started))
        return EXIT_CANCEL
    except Exception as exc:
        submitted = transport.submitted_bytes if transport is not None else 0
        # Submission is counted before awaiting the ATT response. Any positive
        # count therefore means delivery is uncertain and automatic replay is
        # unsafe, regardless of how many bytes were acknowledged.
        if submitted:
            error('job %s: submitted=%d acknowledged=%d elapsed=%.3fs; '
                  'data may have reached the printer and automatic replay is unsafe: %s'
                  % (job_id, submitted, transport.acknowledged_bytes,
                     time.monotonic() - started, exc))
            state(add = 'uncertain-partial-print')
            return EXIT_STOP
        error('job %s: failed before transmission; retry is safe: %s' % (job_id, exc))
        state(add = 'offline-report')
        return EXIT_RETRY
    finally:
        if connecting:
            state(remove = 'connecting-to-device')
        if pairing:
            state(remove = 'authentication-required')
        if invocation[5] and source is not None:
            source.close()


def main(argv = None):
    argv = list(sys.argv if argv is None else argv)
    if len(argv) == 1:
        # Discovery is the phomemo backend's job: it owns the model whitelist and
        # emits the queue URI this script is reached through.
        print('WARNING: use the phomemo backend to discover printers', file=sys.stderr)
        return EXIT_OK
    try:
        invocation = parse_invocation(argv)
        uri = os.environ.get('DEVICE_URI')
        if not uri:
            raise ValueError('DEVICE_URI is required for a print job')
        config = parse_device_uri(uri)
    except (ValueError, OSError) as exc:
        error(str(exc))
        return EXIT_STOP
    return int(asyncio.run(run_job(invocation, config)))


if __name__ == '__main__':
    exit(main())





