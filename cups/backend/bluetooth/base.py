#!/usr/bin/env python3
"""
Abstract base classes for Bluetooth functionality.
Defines the interface that platform-specific implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class BluetoothDevice:
    """Platform-agnostic Bluetooth device representation."""
    address: str    # MAC address (format: XX:XX:XX:XX:XX:XX)
    name: str       # Device name as reported by Bluetooth
    model: str      # Extracted Phomemo model (e.g., 'M02', 'T02', 'M110')

    def get_compact_address(self) -> str:
        """Returns MAC address without colons (e.g., 'AABBCCDDEEFF')."""
        return self.address.replace(':', '')

    def get_cups_uri(self) -> str:
        """Returns CUPS-compatible device URI."""
        return f'phomemo://{self.get_compact_address()}'


class BluetoothConnection(ABC):
    """Abstract base class for Bluetooth RFCOMM connections."""

    @abstractmethod
    def send(self, data: bytes) -> int:
        """
        Send data to the connected printer.

        Args:
            data: Bytes to send

        Returns:
            Number of bytes sent

        Raises:
            IOError: If send fails
        """
        pass

    @abstractmethod
    def receive(self, size: int, timeout: float = 8.0) -> bytes:
        """
        Receive data from the printer.

        Args:
            size: Maximum number of bytes to receive
            timeout: Timeout in seconds

        Returns:
            Received bytes (may be less than size)

        Raises:
            TimeoutError: If timeout expires
            IOError: If receive fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection and release resources."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class BluetoothBackend(ABC):
    """Abstract base class for platform-specific Bluetooth backends."""

    # Phomemo device name patterns
    DEVICE_PREFIXES = ['Mr.in_', 'Mr.in']
    DEVICE_EXACT_NAMES = ['T02']

    @abstractmethod
    def discover_devices(self) -> List[BluetoothDevice]:
        """
        Scan for paired Phomemo Bluetooth devices.

        Returns:
            List of discovered BluetoothDevice objects

        Raises:
            RuntimeError: If discovery fails
        """
        pass

    @abstractmethod
    def connect(self, address: str, channel: int = 1) -> BluetoothConnection:
        """
        Create an RFCOMM connection to a Bluetooth printer.

        Args:
            address: MAC address of the printer (format: XX:XX:XX:XX:XX:XX)
            channel: RFCOMM channel number (default: 1)

        Returns:
            BluetoothConnection instance

        Raises:
            ConnectionError: If connection fails
            ValueError: If address is invalid
        """
        pass

    @classmethod
    def extract_model(cls, device_name: str) -> Optional[str]:
        """
        Extract Phomemo model from device name.

        Args:
            device_name: Bluetooth device name

        Returns:
            Model name (e.g., 'M02', 'T02') or None if not a Phomemo device
        """
        if device_name in cls.DEVICE_EXACT_NAMES:
            return device_name

        for prefix in cls.DEVICE_PREFIXES:
            if device_name.startswith(prefix):
                return device_name[len(prefix):]

        return None

    @classmethod
    def is_phomemo_device(cls, device_name: str) -> bool:
        """
        Check if a device name matches Phomemo device patterns.

        Args:
            device_name: Bluetooth device name

        Returns:
            True if device appears to be a Phomemo printer
        """
        return cls.extract_model(device_name) is not None


__all__ = ['BluetoothDevice', 'BluetoothConnection', 'BluetoothBackend']
