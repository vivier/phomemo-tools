#!/usr/bin/env python3
"""
macOS Bluetooth implementation using IOBluetooth via PyObjC.

Requirements:
    pip install pyobjc-framework-IOBluetooth pyobjc-framework-CoreBluetooth
"""

import sys
import time
from typing import List, Optional

# PyObjC imports - only available on macOS
try:
    import objc
    from Foundation import NSObject, NSRunLoop, NSDate, NSDefaultRunLoopMode
    from IOBluetooth import (
        IOBluetoothDevice,
        IOBluetoothRFCOMMChannel,
    )
    IOBT_AVAILABLE = True
except ImportError as e:
    IOBT_AVAILABLE = False
    IOBT_IMPORT_ERROR = str(e)

from bluetooth.base import BluetoothBackend, BluetoothConnection, BluetoothDevice


class RFCOMMChannelDelegate(NSObject):
    """
    Objective-C delegate for IOBluetoothRFCOMMChannel callbacks.

    IOBluetooth uses an event-driven model, so we need this delegate
    to handle channel events (open, data received, close).
    """

    def init(self):
        self = objc.super(RFCOMMChannelDelegate, self).init()
        if self is None:
            return None
        self.received_data = bytearray()
        self.is_open = False
        self.is_closed = False
        self.error = None
        return self

    def rfcommChannelOpenComplete_status_(self, channel, status):
        """Called when RFCOMM channel open completes."""
        if status == 0:  # kIOReturnSuccess
            self.is_open = True
        else:
            self.error = f"Channel open failed with status: {status}"

    def rfcommChannelData_data_length_(self, channel, data, length):
        """Called when data is received on the channel."""
        # Convert NSData to bytes
        if data and length > 0:
            raw_bytes = data.bytes()
            if raw_bytes:
                self.received_data.extend(raw_bytes[:length])

    def rfcommChannelClosed_(self, channel):
        """Called when the channel closes."""
        self.is_closed = True
        self.is_open = False

    def rfcommChannelWriteComplete_refcon_status_(self, channel, refcon, status):
        """Called when a write operation completes."""
        if status != 0:
            self.error = f"Write failed with status: {status}"


class DarwinBluetoothConnection(BluetoothConnection):
    """
    macOS RFCOMM Bluetooth connection using IOBluetooth framework.

    Note: IOBluetooth is callback-based and requires NSRunLoop processing
    for asynchronous operations.
    """

    def __init__(self, address: str, channel_id: int = 1, timeout: float = 10.0):
        """
        Create an RFCOMM connection to a Bluetooth device.

        Args:
            address: MAC address (format: XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)
            channel_id: RFCOMM channel number
            timeout: Connection timeout in seconds
        """
        if not IOBT_AVAILABLE:
            raise ImportError(f"IOBluetooth not available: {IOBT_IMPORT_ERROR}")

        # Normalize address format (IOBluetooth accepts both : and - separators)
        normalized_addr = address.replace('-', ':').upper()

        self.device = IOBluetoothDevice.deviceWithAddressString_(normalized_addr)
        if self.device is None:
            raise ValueError(f"Could not create device for address: {address}")

        self.delegate = RFCOMMChannelDelegate.alloc().init()
        self.channel = None
        self._channel_id = channel_id

        # Open the RFCOMM channel synchronously
        result = self._open_channel_sync(channel_id, timeout)
        if result != 0:
            raise ConnectionError(
                f"Failed to open RFCOMM channel {channel_id} to {address}: error {result}"
            )

    def _open_channel_sync(self, channel_id: int, timeout: float) -> int:
        """
        Synchronous wrapper around async channel open.

        Spins the NSRunLoop until the channel opens or timeout expires.
        """
        # openRFCOMMChannelSync returns (status, channel) tuple
        result = self.device.openRFCOMMChannelSync_withChannelID_delegate_(
            None,  # outChannel - will be set by method
            channel_id,
            self.delegate
        )

        # Handle different return types from PyObjC
        if isinstance(result, tuple):
            status, self.channel = result
        else:
            status = result
            # Try to get channel from delegate or retry
            self.channel = None

        if status != 0:
            return status

        # Wait for delegate callback confirming open
        deadline = time.time() + timeout
        while not self.delegate.is_open and self.delegate.error is None:
            # Process pending events
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )
            if time.time() > deadline:
                return -1  # Timeout

        if self.delegate.error:
            return -1

        return 0

    def send(self, data: bytes) -> int:
        """Send data over the RFCOMM channel."""
        if not self.channel or not self.delegate.is_open:
            raise IOError("Channel not open")

        # Clear any previous write error
        self.delegate.error = None

        # IOBluetooth writeSync expects data and length
        result = self.channel.writeSync_length_(data, len(data))

        if result != 0:
            raise IOError(f"Write failed with status: {result}")

        if self.delegate.error:
            raise IOError(self.delegate.error)

        return len(data)

    def receive(self, size: int, timeout: float = 8.0) -> bytes:
        """Receive data from the RFCOMM channel."""
        if not self.channel or not self.delegate.is_open:
            raise IOError("Channel not open")

        # Clear received buffer
        self.delegate.received_data = bytearray()

        deadline = time.time() + timeout
        while len(self.delegate.received_data) < size:
            # Process pending events to receive callbacks
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )

            if time.time() > deadline:
                break

            if self.delegate.is_closed:
                break

        return bytes(self.delegate.received_data)

    def close(self) -> None:
        """Close the RFCOMM channel."""
        if self.channel:
            try:
                self.channel.closeChannel()
            except Exception:
                pass
            self.channel = None


class DarwinBluetoothBackend(BluetoothBackend):
    """macOS Bluetooth backend using IOBluetooth framework."""

    def __init__(self):
        """Initialize the macOS Bluetooth backend."""
        if not IOBT_AVAILABLE:
            raise ImportError(
                f"IOBluetooth framework not available. "
                f"Install with: pip install pyobjc-framework-IOBluetooth\n"
                f"Error: {IOBT_IMPORT_ERROR}"
            )

    def discover_devices(self) -> List[BluetoothDevice]:
        """
        Discover paired Phomemo Bluetooth devices.

        Uses IOBluetoothDevice.pairedDevices() to get list of paired devices,
        then filters for Phomemo printer name patterns.
        """
        devices = []

        try:
            paired = IOBluetoothDevice.pairedDevices()
        except Exception as e:
            print(f"WARNING: Failed to get paired devices: {e}", file=sys.stderr)
            return devices

        if paired is None:
            return devices

        for device in paired:
            try:
                name = device.name()
                if not name:
                    continue

                name = str(name)
                model = self.extract_model(name)
                if model is None:
                    continue

                address = str(device.addressString())
                devices.append(BluetoothDevice(
                    address=address,
                    name=name,
                    model=model
                ))
            except Exception as e:
                print(f"WARNING: Error processing device: {e}", file=sys.stderr)
                continue

        return devices

    def connect(self, address: str, channel: int = 1) -> BluetoothConnection:
        """
        Create an RFCOMM connection to a Bluetooth printer.

        Args:
            address: MAC address (format: XX:XX:XX:XX:XX:XX)
            channel: RFCOMM channel number

        Returns:
            DarwinBluetoothConnection instance
        """
        return DarwinBluetoothConnection(address, channel)


__all__ = ['DarwinBluetoothBackend', 'DarwinBluetoothConnection']
