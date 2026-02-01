#!/usr/bin/env python3
"""
Linux Bluetooth implementation using BlueZ/D-Bus.
"""

import sys
import socket
from typing import List

import dbus

from bluetooth.base import BluetoothBackend, BluetoothConnection, BluetoothDevice


class LinuxBluetoothConnection(BluetoothConnection):
    """Linux RFCOMM Bluetooth connection using kernel socket."""

    def __init__(self, address: str, channel: int = 1):
        """
        Create an RFCOMM connection to a Bluetooth device.

        Args:
            address: MAC address (format: XX:XX:XX:XX:XX:XX)
            channel: RFCOMM channel number
        """
        self.address = address
        self.channel = channel
        self.sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )
        try:
            self.sock.connect((address, channel))
        except OSError as e:
            self.sock.close()
            raise ConnectionError(f"Failed to connect to {address}: {e}")

    def send(self, data: bytes) -> int:
        """Send data over the RFCOMM connection."""
        try:
            self.sock.sendall(data)
            return len(data)
        except socket.error as e:
            raise IOError(f"Send failed: {e}")

    def receive(self, size: int, timeout: float = 8.0) -> bytes:
        """Receive data from the RFCOMM connection."""
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(size)
        except socket.timeout:
            raise TimeoutError(f"Receive timeout after {timeout}s")
        except socket.error as e:
            raise IOError(f"Receive failed: {e}")

    def close(self) -> None:
        """Close the socket connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class LinuxBluetoothBackend(BluetoothBackend):
    """Linux Bluetooth backend using BlueZ via D-Bus."""

    def __init__(self):
        """Initialize D-Bus connection to BlueZ."""
        try:
            self.bus = dbus.SystemBus()
            # Test connection to BlueZ
            self.bus.get_object('org.bluez', '/')
        except dbus.exceptions.DBusException as e:
            raise RuntimeError(f"Failed to connect to BlueZ: {e}")

    def discover_devices(self) -> List[BluetoothDevice]:
        """
        Discover paired Phomemo Bluetooth devices via BlueZ.

        Returns:
            List of discovered BluetoothDevice objects
        """
        devices = []

        try:
            bluez = self.bus.get_object('org.bluez', '/')
            manager = dbus.Interface(bluez, 'org.freedesktop.DBus.ObjectManager')
            objects = manager.GetManagedObjects()
        except dbus.exceptions.DBusException as e:
            print(f"WARNING: BlueZ discovery failed: {e}", file=sys.stderr)
            return devices

        for path, interfaces in objects.items():
            if 'org.bluez.Device1' not in interfaces:
                continue

            properties = interfaces['org.bluez.Device1']

            try:
                name = str(properties['Name'])
            except KeyError:
                continue

            model = self.extract_model(name)
            if model is None:
                continue

            address = str(properties['Address'])
            devices.append(BluetoothDevice(
                address=address,
                name=name,
                model=model
            ))

        return devices

    def connect(self, address: str, channel: int = 1) -> BluetoothConnection:
        """
        Create an RFCOMM connection to a Bluetooth printer.

        Args:
            address: MAC address (format: XX:XX:XX:XX:XX:XX)
            channel: RFCOMM channel number

        Returns:
            LinuxBluetoothConnection instance
        """
        return LinuxBluetoothConnection(address, channel)


__all__ = ['LinuxBluetoothBackend', 'LinuxBluetoothConnection']
