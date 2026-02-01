#!/usr/bin/env python3
"""
Abstract base classes for USB functionality.
Defines the interface that platform-specific implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import quote


@dataclass
class USBDevice:
    """Platform-agnostic USB device representation."""
    vendor_id: int
    product_id: int
    serial: str
    model: str
    interface: int
    manufacturer: str
    product: str
    device_path: Optional[str] = None  # Platform-specific device path

    def get_cups_uri(self) -> str:
        """Returns CUPS-compatible device URI."""
        return (
            f'usb://{quote(self.manufacturer)}/{quote(self.product)}'
            f'?serial={self.serial}&interface={self.interface}'
        )


class USBBackend(ABC):
    """Abstract base class for platform-specific USB backends."""

    # Phomemo vendor ID (MAG Technology Co., Ltd)
    PHOMEMO_VENDOR_ID = 0x0493

    # Known Phomemo product IDs
    PRODUCT_MAP = {
        0xb002: 'M02',
        0x8760: 'M110',
        # Add more product IDs as discovered
    }

    @abstractmethod
    def discover_devices(self) -> List[USBDevice]:
        """
        Scan for connected Phomemo USB printers.

        Returns:
            List of discovered USBDevice objects

        Raises:
            RuntimeError: If discovery fails
        """
        pass

    @classmethod
    def get_model_name(cls, product_id: int) -> str:
        """
        Get model name from USB product ID.

        Args:
            product_id: USB product ID

        Returns:
            Model name or 'Unknown(0xXXXX)' if not recognized
        """
        return cls.PRODUCT_MAP.get(product_id, f'Unknown(0x{product_id:04x})')


__all__ = ['USBDevice', 'USBBackend']
