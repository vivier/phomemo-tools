#! /usr/bin/python3

"""
Phomemo CUPS Backend for macOS - USB Only

This backend handles USB printer discovery and printing for Phomemo
thermal printers on macOS. Bluetooth is not supported on macOS due
to different Bluetooth stack requirements.

Usage:
    As CUPS backend (discovery): ./phomemo-usb
    As CUPS backend (print job): DEVICE_URI=usb://... ./phomemo-usb job user title copies options [file]
"""

import sys
import os
from urllib.parse import quote, unquote, parse_qs

# Device identification string for CUPS
DEVICE_ID = 'CLS:PRINTER;CMD:EPSON;DES:Thermal Printer;MFG:Phomemo;MDL:'

# Vendor ID for Phomemo printers (MAG Technology)
PHOMEMO_VENDOR_ID = 0x0493

# Known product IDs
PRODUCT_IDS = {
    0xb002: 'M02',
    0x8760: 'M110',
    0x8761: 'M110',  # Alternative ID
    0x8762: 'M120',
    0x8763: 'M220',
    0x8764: 'M421',
}


class FindPrinterClass:
    """USB device matcher for printer class devices."""

    def __init__(self, device_class=7):
        self._class = device_class

    def __call__(self, device):
        if device.bDeviceClass == self._class:
            return True

        for cfg in device:
            import usb.util
            intf = usb.util.find_descriptor(cfg, bInterfaceClass=self._class)
            if intf is not None:
                return True

        return False


def scan_usb():
    """Scan for Phomemo USB printers and output CUPS device lines."""
    try:
        import usb.core
        import usb.util
    except ImportError:
        print("WARNING: PyUSB not found. Install with: pip3 install pyusb", file=sys.stderr)
        print("WARNING: On macOS, also install libusb: brew install libusb", file=sys.stderr)
        return

    try:
        printers = usb.core.find(
            find_all=True,
            custom_match=FindPrinterClass(7),
            idVendor=PHOMEMO_VENDOR_ID
        )
    except usb.core.USBError as e:
        print(f"WARNING: USB access error: {e}", file=sys.stderr)
        print("WARNING: On macOS, you may need to allow USB access in System Preferences", file=sys.stderr)
        return

    for printer in printers:
        try:
            interface_num = None
            for cfg in printer:
                import usb.util
                intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
                if intf is not None:
                    interface_num = intf.bInterfaceNumber
                    break

            if interface_num is None:
                continue

            # Get model name from product ID
            model = PRODUCT_IDS.get(printer.idProduct, f'Unknown(0x{printer.idProduct:04x})')

            # Get serial number
            try:
                usb.util.get_langids(printer)
                serial_number = usb.util.get_string(printer, printer.iSerialNumber)
            except Exception:
                serial_number = 'UNKNOWN'

            # Get manufacturer and product strings
            try:
                manufacturer = usb.util.get_string(printer, printer.iManufacturer) or 'Phomemo'
                product = usb.util.get_string(printer, printer.iProduct) or model
            except Exception:
                manufacturer = 'Phomemo'
                product = model

            # Build device URI
            device_uri = 'usb://{}/{}?serial={}&interface={}'.format(
                quote(manufacturer),
                quote(product),
                serial_number,
                interface_num
            )

            device_make_and_model = f'Phomemo {model}'

            # Output CUPS device line format:
            # device-class device-uri "device-make-and-model" "device-info" "device-id"
            print(f'direct {device_uri} "{device_make_and_model}" '
                  f'"{device_make_and_model} USB {serial_number}" '
                  f'"{DEVICE_ID}{model} (USB);"')

        except Exception as e:
            print(f"WARNING: Error processing USB device: {e}", file=sys.stderr)
            continue


def print_job():
    """Handle a print job from CUPS."""
    device_uri = os.environ.get('DEVICE_URI', '')

    if not device_uri:
        print("ERROR: No DEVICE_URI environment variable", file=sys.stderr)
        return 1

    # For USB URIs, CUPS handles the actual data transmission through the usb backend
    # This backend just needs to forward the data
    print(f'DEBUG: {sys.argv[0]} handling device {device_uri}', file=sys.stderr)

    # For USB printers, the data is typically handled by CUPS' built-in usb backend
    # Our backend is mainly for device discovery
    # If we get here with a print job, we pass through to stdout

    print('STATE: +connecting-to-device', file=sys.stderr)
    print('STATE: +sending-data', file=sys.stderr)

    try:
        with os.fdopen(sys.stdin.fileno(), 'rb', closefd=False) as stdin:
            with os.fdopen(sys.stdout.fileno(), 'wb', closefd=False) as stdout:
                while True:
                    data = stdin.read(8192)
                    if not data:
                        break
                    stdout.write(data)
                    print(f'DEBUG: sent {len(data)} bytes', file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to send print data: {e}", file=sys.stderr)
        return 1

    return 0


def main():
    # No arguments = device discovery mode
    if len(sys.argv) == 1:
        scan_usb()
        return 0

    # With arguments = print job mode
    # CUPS calls backend with: job-id user title copies options [file]
    return print_job()


if __name__ == '__main__':
    sys.exit(main() or 0)
