#!/usr/bin/env python3
"""
Phomemo Bluetooth Helper Daemon

Runs as a user LaunchAgent with Bluetooth permissions.
CUPS backend connects via Unix socket to send print data.

Install:
    cp phomemo-bt-helper.py ~/Library/Application\\ Support/Phomemo/
    cp com.phomemo.bt-helper.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
"""

import os
import sys
import socket
import struct
import time
import json

# PyObjC imports
try:
    import objc
    from Foundation import NSObject, NSRunLoop, NSDate, NSDefaultRunLoopMode
    from IOBluetooth import IOBluetoothDevice, IOBluetoothRFCOMMChannel
    BLUETOOTH_AVAILABLE = True
except ImportError as e:
    BLUETOOTH_AVAILABLE = False
    print(f"Bluetooth not available: {e}", file=sys.stderr)

SOCKET_PATH = "/tmp/phomemo-bt.sock"


class RFCOMMDelegate(NSObject):
    """Delegate for RFCOMM channel callbacks."""

    def init(self):
        self = objc.super(RFCOMMDelegate, self).init()
        if self is None:
            return None
        self.is_open = False
        self.error = None
        return self

    def rfcommChannelOpenComplete_status_(self, channel, status):
        if status == 0:
            self.is_open = True
        else:
            self.error = f"Open failed: {status}"

    def rfcommChannelClosed_(self, channel):
        self.is_open = False


def resolve_device(address_or_name):
    """Resolve device by address or name."""
    # Check if it looks like a MAC address (XX-XX-XX-XX-XX-XX or XX:XX:XX:XX:XX:XX)
    import re
    if re.match(r'^([0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}$', address_or_name):
        # It's an address
        device = IOBluetoothDevice.deviceWithAddressString_(address_or_name)
        if device:
            return device

    # Try to find by name in paired devices
    for device in IOBluetoothDevice.pairedDevices() or []:
        name = device.name()
        if name and name == address_or_name:
            return device

    # Not found
    return None


def connect_bluetooth(address_or_name, channel_id=1, timeout=10.0):
    """Connect to Bluetooth device and return RFCOMM channel."""
    device = resolve_device(address_or_name)
    if not device:
        raise ValueError(f"Device not found: {address_or_name}")

    delegate = RFCOMMDelegate.alloc().init()

    result = device.openRFCOMMChannelSync_withChannelID_delegate_(
        None, channel_id, delegate
    )

    if isinstance(result, tuple):
        status, channel = result
    else:
        status = result
        channel = None

    if status != 0:
        raise ConnectionError(f"RFCOMM open failed: {status}")

    # Wait for connection
    deadline = time.time() + timeout
    while not delegate.is_open and not delegate.error:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            NSDefaultRunLoopMode,
            NSDate.dateWithTimeIntervalSinceNow_(0.1)
        )
        if time.time() > deadline:
            raise TimeoutError("Connection timeout")

    if delegate.error:
        raise ConnectionError(delegate.error)

    time.sleep(0.5)  # Stabilize connection
    return channel


def send_data(channel, data):
    """Send data over RFCOMM channel."""
    chunk_size = 512
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        result = channel.writeSync_length_(chunk, len(chunk))
        if result != 0:
            raise IOError(f"Write failed: {result}")
        time.sleep(0.01)
    return len(data)


def handle_client(conn):
    """Handle a client connection from CUPS backend."""
    try:
        # Read header: address length (4 bytes) + address + data
        header = conn.recv(4)
        if len(header) < 4:
            conn.send(b"ERR:Invalid header\n")
            return

        addr_len = struct.unpack("!I", header)[0]
        address = conn.recv(addr_len).decode('utf-8')

        print(f"Connecting to {address}...", file=sys.stderr)

        # Connect Bluetooth
        channel = connect_bluetooth(address)

        conn.send(b"OK:Connected\n")

        # Receive and forward data
        total = 0
        while True:
            data = conn.recv(4096)
            if not data:
                break
            send_data(channel, data)
            total += len(data)

        channel.closeChannel()
        conn.send(f"OK:Sent {total} bytes\n".encode())
        print(f"Sent {total} bytes to {address}", file=sys.stderr)

    except Exception as e:
        error_msg = f"ERR:{e}\n"
        try:
            conn.send(error_msg.encode())
        except:
            pass
        print(f"Error: {e}", file=sys.stderr)


def main():
    if not BLUETOOTH_AVAILABLE:
        print("Bluetooth not available", file=sys.stderr)
        return 1

    # Remove old socket
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    # Create Unix socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)  # Allow all users to connect
    server.listen(5)

    print(f"Phomemo Bluetooth helper listening on {SOCKET_PATH}", file=sys.stderr)

    while True:
        conn, _ = server.accept()
        try:
            handle_client(conn)
        finally:
            conn.close()


if __name__ == '__main__':
    sys.exit(main() or 0)
