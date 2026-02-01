#!/usr/bin/env python3
"""
macOS USB implementation using PyUSB and system tools.
"""

import sys
import glob
import subprocess
import re
from typing import List, Optional

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
        if device.bDeviceClass == self.PRINTER_CLASS:
            return True

        for cfg in device:
            intf = usb.util.find_descriptor(
                cfg,
                bInterfaceClass=self.PRINTER_CLASS
            )
            if intf is not None:
                return True

        return False


class DarwinUSBBackend(USBBackend):
    """macOS USB backend using PyUSB and ioreg."""

    def __init__(self):
        """Initialize the macOS USB backend."""
        if not PYUSB_AVAILABLE:
            raise ImportError(
                "PyUSB not available. Install with: pip install pyusb"
            )

    def _find_cu_device(self, serial: Optional[str] = None) -> Optional[str]:
        """
        Find /dev/cu.usbmodem* device, optionally matching serial.

        Args:
            serial: USB serial number to match (optional)

        Returns:
            Device path or None
        """
        candidates = glob.glob('/dev/cu.usbmodem*')

        if not candidates:
            return None

        if serial and len(candidates) > 1:
            # Try to match by checking ioreg for serial
            # This is a best-effort match
            for candidate in candidates:
                if serial in candidate:
                    return candidate

        # Return first match if no serial match or single device
        return candidates[0] if candidates else None

    def _get_usb_info_from_ioreg(self) -> dict:
        """
        Get USB device information from ioreg.

        Returns:
            Dictionary mapping serial numbers to device info
        """
        info = {}

        try:
            result = subprocess.run(
                ['ioreg', '-p', 'IOUSB', '-l', '-w', '0'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return info

            current_device = {}
            for line in result.stdout.split('\n'):
                # Look for Phomemo vendor ID (0x0493 = 1171 decimal)
                if 'idVendor' in line:
                    match = re.search(r'= (\d+)', line)
                    if match and int(match.group(1)) == self.PHOMEMO_VENDOR_ID:
                        current_device['vendor'] = self.PHOMEMO_VENDOR_ID

                elif 'idProduct' in line and 'vendor' in current_device:
                    match = re.search(r'= (\d+)', line)
                    if match:
                        current_device['product_id'] = int(match.group(1))

                elif 'USB Serial Number' in line and 'vendor' in current_device:
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        serial = match.group(1)
                        current_device['serial'] = serial
                        info[serial] = current_device.copy()
                        current_device = {}

        except Exception as e:
            print(f"WARNING: ioreg parsing failed: {e}", file=sys.stderr)

        return info

    def discover_devices(self) -> List[USBDevice]:
        """
        Discover connected Phomemo USB printers on macOS.

        Uses both PyUSB for device enumeration and ioreg for
        mapping to /dev/cu.* device paths.

        Returns:
            List of discovered USBDevice objects
        """
        devices = []

        # Get supplementary info from ioreg
        ioreg_info = self._get_usb_info_from_ioreg()

        try:
            printers = usb.core.find(
                find_all=True,
                custom_match=FindPrinterClass(),
                idVendor=self.PHOMEMO_VENDOR_ID
            )
        except usb.core.NoBackendError:
            print(
                "WARNING: No USB backend found. Install libusb: brew install libusb",
                file=sys.stderr
            )
            return devices
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
                    manufacturer = printer.manufacturer or 'Phomemo'
                    product = printer.product or 'Thermal Printer'
                except Exception:
                    serial = 'Unknown'
                    manufacturer = 'Phomemo'
                    product = 'Thermal Printer'

                model = self.get_model_name(printer.idProduct)

                # Find corresponding /dev/cu.* device
                device_path = self._find_cu_device(serial)

                devices.append(USBDevice(
                    vendor_id=printer.idVendor,
                    product_id=printer.idProduct,
                    serial=serial,
                    model=model,
                    interface=interface_num,
                    manufacturer=manufacturer,
                    product=product,
                    device_path=device_path
                ))

            except Exception as e:
                print(f"WARNING: Error processing USB device: {e}", file=sys.stderr)
                continue

        return devices


__all__ = ['DarwinUSBBackend']
