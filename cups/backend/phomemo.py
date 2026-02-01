#!/usr/bin/env python3
"""
Phomemo CUPS Backend

Cross-platform backend supporting both Linux (BlueZ) and macOS (IOBluetooth).
Handles printer discovery and job submission via Bluetooth or USB.

Usage:
    Discovery mode (no arguments):
        phomemo

    Print mode (called by CUPS):
        DEVICE_URI=phomemo://AABBCCDDEEFF phomemo job user title copies options [file]
"""

import sys
import os

# Add current directory to path for module imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Import platform-agnostic backends
from bluetooth import get_bluetooth_backend
from usb import get_usb_backend

# CUPS device ID string
DEVICE_ID = 'CLS:PRINTER;CMD:EPSON;DES:Thermal Printer;MFG:Phomemo;MDL:'


def format_mac_address(compact: str) -> str:
    """
    Convert compact MAC address to colon-separated format.

    Args:
        compact: MAC address without separators (e.g., 'AABBCCDDEEFF')

    Returns:
        Colon-separated MAC address (e.g., 'AA:BB:CC:DD:EE:FF')
    """
    return ':'.join(compact[i:i+2] for i in range(0, 12, 2))


def scan_bluetooth():
    """
    Discover Bluetooth printers and output CUPS discovery format.
    """
    backend = get_bluetooth_backend()
    if backend is None:
        return

    try:
        devices = backend.discover_devices()
    except Exception as e:
        print(f"WARNING: Bluetooth discovery failed: {e}", file=sys.stderr)
        return

    for device in devices:
        device_uri = device.get_cups_uri()
        device_make_and_model = f'Phomemo {device.model}'

        # CUPS discovery output format:
        # class URI "make and model" "info" "device-id"
        print(
            f'direct {device_uri} "{device_make_and_model}" '
            f'"{device_make_and_model} bluetooth {device.address}" '
            f'"{DEVICE_ID}{device.model} (BT);"'
        )


def scan_usb():
    """
    Discover USB printers and output CUPS discovery format.
    """
    backend = get_usb_backend()
    if backend is None:
        return

    try:
        devices = backend.discover_devices()
    except Exception as e:
        print(f"WARNING: USB discovery failed: {e}", file=sys.stderr)
        return

    for device in devices:
        device_uri = device.get_cups_uri()
        device_make_and_model = f'Phomemo {device.model}'

        print(
            f'direct {device_uri} "{device_make_and_model}" '
            f'"{device_make_and_model} USB {device.serial}" '
            f'"{DEVICE_ID}{device.model} (USB);"'
        )


def print_job(address: str):
    """
    Connect to printer and send print job data.

    Args:
        address: Bluetooth MAC address (format: XX:XX:XX:XX:XX:XX)
    """
    backend = get_bluetooth_backend()
    if backend is None:
        print("ERROR: Bluetooth not available on this platform", file=sys.stderr)
        sys.exit(1)

    try:
        print('STATE: +connecting-to-device')
        conn = backend.connect(address, channel=1)

        print('STATE: +sending-data')
        with os.fdopen(sys.stdin.fileno(), 'rb', closefd=False) as stdin:
            while True:
                data = stdin.read(8192)
                if not data:
                    break
                conn.send(data)
                print(f'DEBUG: sent {len(data)}')

        # Wait for printer acknowledgment before closing
        # This prevents premature connection close which stops printing
        print('STATE: +receiving-data')
        try:
            received = conn.receive(28, timeout=8.0)
            if received:
                hex_str = " 0x".join(f"{b:02x}" for b in received)
                print(f'DEBUG: {hex_str}')
        except TimeoutError:
            pass
        except Exception as e:
            print(f'DEBUG: receive error (non-fatal): {e}')

        conn.close()
        print('STATE: -connecting-to-device')
        print('STATE: -sending-data')
        print('STATE: -receiving-data')

    except ConnectionError as e:
        print(f"ERROR: Can't open Bluetooth connection: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"ERROR: Cannot write data: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for CUPS backend."""

    # Discovery mode: no arguments
    if len(sys.argv) == 1:
        scan_bluetooth()
        scan_usb()
        sys.exit(0)

    # Print mode: DEVICE_URI environment variable required
    device_uri = os.environ.get('DEVICE_URI')
    if not device_uri:
        print("ERROR: DEVICE_URI environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Parse device URI
    try:
        scheme, address = device_uri.split('://', 1)
    except ValueError:
        print(f"ERROR: Invalid device URI format: {device_uri}", file=sys.stderr)
        sys.exit(1)

    if scheme != 'phomemo':
        print(f"ERROR: Unsupported URI scheme: {scheme}", file=sys.stderr)
        sys.exit(1)

    # Convert compact address to MAC format
    if len(address) == 12:
        bdaddr = format_mac_address(address)
    elif ':' in address and len(address) == 17:
        bdaddr = address
    else:
        print(f"ERROR: Invalid Bluetooth address: {address}", file=sys.stderr)
        sys.exit(1)

    print(f'DEBUG: {sys.argv[0]} device {bdaddr}')
    print_job(bdaddr)
    sys.exit(0)


if __name__ == '__main__':
    main()
