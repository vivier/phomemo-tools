#!/usr/bin/env python3
"""
Direct USB printing for Phomemo M110/M220 printers on macOS.

Usage:
    python3 print-usb.py <image_file>
    python3 print-usb.py --list    # List connected printers
"""

import sys
import os
import argparse
import usb.core
import usb.util
from PIL import Image, ImageOps

# Known vendor IDs for Phomemo printers
VENDOR_IDS = [
    0x0493,  # MAG Technology (original Phomemo)
    0x0483,  # Jieli Technology (some M220 models)
]

# Known product IDs by vendor
PRODUCT_IDS = {
    # MAG Technology (0x0493)
    0xb002: 'M02',
    0x8760: 'M110',
    0x8761: 'M110',
    0x8762: 'M120',
    0x8763: 'M220',
    0x8764: 'M421',
    # Jieli Technology (0x0483)
    0x5740: 'M220',
}

# Printer commands
ESC = b'\x1b'
GS = b'\x1d'


def find_printers():
    """Find all connected Phomemo printers."""
    printers = []

    try:
        for vendor_id in VENDOR_IDS:
            devices = usb.core.find(find_all=True, idVendor=vendor_id)
            for dev in devices:
                # Check if it's a printer class device
                is_printer = False
                for cfg in dev:
                    intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
                    if intf:
                        is_printer = True
                        break

                if not is_printer:
                    continue

                model = PRODUCT_IDS.get(dev.idProduct, f'Unknown(0x{dev.idProduct:04x})')
                try:
                    serial = usb.util.get_string(dev, dev.iSerialNumber)
                except:
                    serial = 'Unknown'
                printers.append({
                    'device': dev,
                    'model': model,
                    'serial': serial,
                    'product_id': dev.idProduct,
                    'vendor_id': vendor_id,
                })
    except Exception as e:
        print(f"Error scanning USB: {e}", file=sys.stderr)

    return printers


def list_printers():
    """List all connected printers."""
    printers = find_printers()
    if not printers:
        print("No Phomemo printers found.")
        print("\nMake sure:")
        print("  - Printer is connected via USB")
        print("  - Printer is turned on")
        print("  - libusb is installed: brew install libusb")
        return

    print(f"Found {len(printers)} printer(s):\n")
    for i, p in enumerate(printers):
        print(f"  [{i}] {p['model']} (Serial: {p['serial']})")


def open_printer(printer_info):
    """Open USB connection to printer and return endpoints."""
    dev = printer_info['device']

    # Detach kernel driver if active
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except:
        pass

    # Set configuration
    try:
        dev.set_configuration()
    except:
        pass

    # Find printer interface (class 7)
    cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)

    if intf is None:
        raise RuntimeError("Could not find printer interface")

    # Find OUT endpoint
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )

    if ep_out is None:
        raise RuntimeError("Could not find OUT endpoint")

    return dev, ep_out


def print_image_m110(ep_out, image, media_type=10):
    """Send image to M110/M220 printer."""

    # Convert image to 1-bit
    img = image.convert('L')
    img = ImageOps.invert(img)
    img = img.convert('1')

    # Printer commands
    def write(data):
        ep_out.write(data)

    # Set speed
    write(ESC + b'\x4e\x0d\x05')

    # Set density
    write(ESC + b'\x4e\x04\x0a')

    # Set media type
    write(b'\x1f\x11' + media_type.to_bytes(1, 'little'))

    # Print raster
    width_bytes = (img.width + 7) // 8
    height = img.height

    write(GS + b'v0\x00')  # Print raster command, mode 0
    write(width_bytes.to_bytes(2, 'little'))
    write(height.to_bytes(2, 'little'))
    write(img.tobytes())

    # Footer
    write(b'\x1f\xf0\x05\x00')
    write(b'\x1f\xf0\x03\x00')

    print(f"Sent {img.width}x{img.height} image to printer")


def main():
    parser = argparse.ArgumentParser(description='Direct USB printing for Phomemo printers')
    parser.add_argument('image', nargs='?', help='Image file to print')
    parser.add_argument('--list', '-l', action='store_true', help='List connected printers')
    parser.add_argument('--width', '-w', type=int, default=384, help='Max print width in pixels (default: 384)')
    parser.add_argument('--media', '-m', type=int, default=10, help='Media type (10=gap, 11=continuous, 38=marks)')

    args = parser.parse_args()

    if args.list:
        list_printers()
        return 0

    if not args.image:
        parser.print_help()
        return 1

    # Find printer
    printers = find_printers()
    if not printers:
        print("No Phomemo printer found!", file=sys.stderr)
        return 1

    printer = printers[0]
    print(f"Using printer: {printer['model']} (Serial: {printer['serial']})")

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

    # Open printer
    try:
        dev, ep_out = open_printer(printer)
    except Exception as e:
        print(f"Error opening printer: {e}", file=sys.stderr)
        return 1

    # Print
    try:
        print_image_m110(ep_out, img, args.media)
        print("Print complete!")
    except Exception as e:
        print(f"Error printing: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
