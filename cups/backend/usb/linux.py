#!/usr/bin/env python3
"""
Linux USB implementation using PyUSB.
"""

import sys
from typing import List

try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False

from usb.base import USBBackend, USBDevice


class FindPrinterClass:
    """Custom matcher for USB printer class devices."""

    PRINTER_CLASS = 7  # USB Printer class

    def __init__(self):
        pass

    def __call__(self, device):
        """Check if device is a printer class device."""
        # Check device class
        if device.bDeviceClass == self.PRINTER_CLASS:
            return True

        # Check interface classes
        for cfg in device:
            intf = usb.util.find_descriptor(
                cfg,
                bInterfaceClass=self.PRINTER_CLASS
            )
            if intf is not None:
                return True

        return False


class LinuxUSBBackend(USBBackend):
    """Linux USB backend using PyUSB."""

    def __init__(self):
        """Initialize the Linux USB backend."""
        if not PYUSB_AVAILABLE:
            raise ImportError(
                "PyUSB not available. Install with: pip install pyusb"
            )

    def discover_devices(self) -> List[USBDevice]:
        """
        Discover connected Phomemo USB printers.

        Returns:
            List of discovered USBDevice objects
        """
        devices = []

        try:
            printers = usb.core.find(
                find_all=True,
                custom_match=FindPrinterClass(),
                idVendor=self.PHOMEMO_VENDOR_ID
            )
        except Exception as e:
            print(f"WARNING: USB discovery failed: {e}", file=sys.stderr)
            return devices

        for printer in printers:
            try:
                # Find printer interface
                interface_num = None
                for cfg in printer:
                    intf = usb.util.find_descriptor(
                        cfg,
                        bInterfaceClass=FindPrinterClass.PRINTER_CLASS
                    )
                    if intf is not None:
                        interface_num = intf.bInterfaceNumber
                        break

                if interface_num is None:
                    continue

                # Get device strings
                try:
                    usb.util.get_langids(printer)
                    serial = usb.util.get_string(printer, printer.iSerialNumber)
                    manufacturer = printer.manufacturer or 'Unknown'
                    product = printer.product or 'Unknown'
                except Exception:
                    serial = 'Unknown'
                    manufacturer = 'Unknown'
                    product = 'Unknown'

                model = self.get_model_name(printer.idProduct)

                devices.append(USBDevice(
                    vendor_id=printer.idVendor,
                    product_id=printer.idProduct,
                    serial=serial,
                    model=model,
                    interface=interface_num,
                    manufacturer=manufacturer,
                    product=product,
                    device_path=f'/dev/usb/lp0'  # Linux USB printer path
                ))

            except Exception as e:
                print(f"WARNING: Error processing USB device: {e}", file=sys.stderr)
                continue

        return devices


__all__ = ['LinuxUSBBackend']
