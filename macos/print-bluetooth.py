#!/usr/bin/env python3
"""
Direct Bluetooth printing for Phomemo M110/M220 printers on macOS.

Requirements:
    pip install pyobjc-framework-IOBluetooth pillow

Usage:
    python3 print-bluetooth.py <image_file>
    python3 print-bluetooth.py --list    # List paired Phomemo printers
"""

import sys
import os
import argparse
import time
from PIL import Image, ImageOps

# PyObjC imports for Bluetooth
try:
    import objc
    from Foundation import NSObject, NSRunLoop, NSDate, NSDefaultRunLoopMode
    from IOBluetooth import IOBluetoothDevice, IOBluetoothRFCOMMChannel
    BLUETOOTH_AVAILABLE = True
except ImportError as e:
    BLUETOOTH_AVAILABLE = False
    BLUETOOTH_ERROR = str(e)

# Printer commands
ESC = b'\x1b'
GS = b'\x1d'

# Known Phomemo printer name patterns
PHOMEMO_PATTERNS = ['M02', 'M110', 'M120', 'M220', 'M421', 'T02', 'D30']

# Some printers use serial number as name (e.g., Q198G43S2490044)
import re
SERIAL_PATTERN = re.compile(r'^[A-Z]\d{3}[A-Z]\d{2}[A-Z]\d+$')


class RFCOMMDelegate(NSObject):
    """Delegate for RFCOMM channel callbacks."""

    def init(self):
        self = objc.super(RFCOMMDelegate, self).init()
        if self is None:
            return None
        self.is_open = False
        self.is_closed = False
        self.error = None
        return self

    def rfcommChannelOpenComplete_status_(self, channel, status):
        if status == 0:
            self.is_open = True
        else:
            self.error = f"Open failed: {status}"

    def rfcommChannelClosed_(self, channel):
        self.is_closed = True
        self.is_open = False


def find_phomemo_printers():
    """Find paired Phomemo printers."""
    if not BLUETOOTH_AVAILABLE:
        print(f"Bluetooth not available: {BLUETOOTH_ERROR}", file=sys.stderr)
        return []

    printers = []
    paired = IOBluetoothDevice.pairedDevices()

    if not paired:
        return printers

    for device in paired:
        name = device.name()
        if not name:
            continue

        name = str(name)
        # Check if this looks like a Phomemo printer
        model = None
        for pattern in PHOMEMO_PATTERNS:
            if pattern.lower() in name.lower():
                model = pattern
                break

        # Also check for serial number pattern (some printers use serial as name)
        if not model and SERIAL_PATTERN.match(name):
            model = 'Phomemo'

        if model:
            addr = str(device.addressString())
            printers.append({
                'device': device,
                'name': name,
                'address': addr,
                'model': model,
            })

    return printers


def list_printers():
    """List paired Phomemo printers."""
    if not BLUETOOTH_AVAILABLE:
        print(f"Bluetooth not available: {BLUETOOTH_ERROR}")
        print("\nInstall with: pip install pyobjc-framework-IOBluetooth")
        return

    printers = find_phomemo_printers()
    if not printers:
        print("No Phomemo printers found in paired devices.")
        print("\nMake sure the printer is:")
        print("  - Turned on and in Bluetooth mode")
        print("  - Paired via System Settings > Bluetooth")
        print("\nPaired devices on this Mac:")
        paired = IOBluetoothDevice.pairedDevices()
        if paired:
            for d in paired:
                name = d.name()
                if name:
                    print(f"  - {name}")
        return

    print(f"Found {len(printers)} Phomemo printer(s):\n")
    for i, p in enumerate(printers):
        print(f"  [{i}] {p['model']} - {p['name']} ({p['address']})")


def connect_rfcomm(device, channel_id=1, timeout=10.0):
    """Open RFCOMM connection to device."""
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
        raise ConnectionError(f"Failed to open RFCOMM channel: {status}")

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

    # Small delay to let connection stabilize
    time.sleep(0.5)

    return channel


def send_data(channel, data, chunk_size=512):
    """Send data over RFCOMM channel in chunks."""
    total = 0
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        result = channel.writeSync_length_(chunk, len(chunk))
        if result != 0:
            raise IOError(f"Write failed at offset {i}: {result}")
        total += len(chunk)
        time.sleep(0.01)  # Small delay between chunks
    return total


def print_image_m110(channel, image, media_type=10):
    """Send image to M110/M220 printer via Bluetooth."""

    # Convert image to 1-bit
    img = image.convert('L')
    img = ImageOps.invert(img)
    img = img.convert('1')

    # Set speed: ESC N 0x0d <speed>
    send_data(channel, ESC + b'\x4e\x0d\x05')

    # Set density: ESC N 0x04 <density>
    send_data(channel, ESC + b'\x4e\x04\x0a')

    # Set media type: 0x1f 0x11 <type>
    send_data(channel, b'\x1f\x11' + media_type.to_bytes(1, 'little'))

    # Print raster
    width_bytes = (img.width + 7) // 8
    height = img.height

    # GS v 0 <mode> <width_lo> <width_hi> <height_lo> <height_hi>
    header = GS + b'v0\x00'
    header += width_bytes.to_bytes(2, 'little')
    header += height.to_bytes(2, 'little')
    send_data(channel, header)

    # Send image data
    send_data(channel, img.tobytes())

    # Footer
    send_data(channel, b'\x1f\xf0\x05\x00')
    send_data(channel, b'\x1f\xf0\x03\x00')

    print(f"Sent {img.width}x{img.height} image to printer")


def main():
    parser = argparse.ArgumentParser(description='Bluetooth printing for Phomemo printers')
    parser.add_argument('image', nargs='?', help='Image file to print')
    parser.add_argument('--list', '-l', action='store_true', help='List paired printers')
    parser.add_argument('--address', '-a', help='Bluetooth address (XX:XX:XX:XX:XX:XX)')
    parser.add_argument('--width', '-w', type=int, default=384, help='Max print width (default: 384)')
    parser.add_argument('--media', '-m', type=int, default=10, help='Media type (10=gap, 11=continuous)')
    parser.add_argument('--channel', '-c', type=int, default=1, help='RFCOMM channel (default: 1)')

    args = parser.parse_args()

    if not BLUETOOTH_AVAILABLE:
        print(f"Error: Bluetooth not available: {BLUETOOTH_ERROR}", file=sys.stderr)
        print("Install with: pip install pyobjc-framework-IOBluetooth", file=sys.stderr)
        return 1

    if args.list:
        list_printers()
        return 0

    if not args.image:
        parser.print_help()
        return 1

    # Find printer
    if args.address:
        # Use specified address
        device = IOBluetoothDevice.deviceWithAddressString_(args.address.upper())
        if not device:
            print(f"Could not find device: {args.address}", file=sys.stderr)
            return 1
        printer_name = args.address
    else:
        # Find first Phomemo printer
        printers = find_phomemo_printers()
        if not printers:
            print("No Phomemo printer found!", file=sys.stderr)
            print("Use --list to see paired devices, or --address to specify manually")
            return 1
        device = printers[0]['device']
        printer_name = printers[0]['name']

    print(f"Using printer: {printer_name}")

    # Load image
    try:
        img = Image.open(args.image)
    except Exception as e:
        print(f"Error loading image: {e}", file=sys.stderr)
        return 1

    # Resize if needed
    if img.width > args.width:
        ratio = args.width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((args.width, new_height), Image.Resampling.LANCZOS)
        print(f"Resized image to {img.width}x{img.height}")

    # Connect
    print(f"Connecting via Bluetooth (channel {args.channel})...")
    try:
        channel = connect_rfcomm(device, args.channel)
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1

    # Print
    try:
        print_image_m110(channel, img, args.media)
        print("Print complete!")
    except Exception as e:
        print(f"Print failed: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            channel.closeChannel()
        except:
            pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
