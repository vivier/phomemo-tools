#!/usr/bin/env python3
"""
Platform detection and utilities for phomemo-tools.
Provides cross-platform path resolution and capability detection.
"""

import platform
import os
import struct


def get_platform():
    """
    Returns the current platform identifier.

    Returns:
        str: 'linux', 'darwin', or 'unknown'
    """
    system = platform.system().lower()
    if system in ('linux', 'darwin'):
        return system
    return 'unknown'


def is_apple_silicon():
    """
    Detects if running on Apple Silicon (arm64 macOS).

    Returns:
        bool: True if Apple Silicon, False otherwise
    """
    return get_platform() == 'darwin' and platform.machine() == 'arm64'


def is_macos():
    """
    Detects if running on macOS.

    Returns:
        bool: True if macOS, False otherwise
    """
    return get_platform() == 'darwin'


def is_linux():
    """
    Detects if running on Linux.

    Returns:
        bool: True if Linux, False otherwise
    """
    return get_platform() == 'linux'


def get_cups_paths():
    """
    Returns platform-appropriate CUPS installation directories.

    Returns:
        dict: Dictionary with keys 'backend', 'filter', 'ppd', 'drv'
    """
    if is_macos():
        return {
            'backend': '/usr/local/lib/cups/backend',
            'filter': '/usr/local/lib/cups/filter',
            'ppd': '/Library/Printers/PPDs/Contents/Resources/Phomemo',
            'drv': '/Library/Printers/PPDs/Contents/Resources',
        }
    else:
        # Linux defaults
        return {
            'backend': '/usr/lib/cups/backend',
            'filter': '/usr/lib/cups/filter',
            'ppd': '/usr/share/cups/model/Phomemo',
            'drv': '/usr/share/cups/drv',
        }


def check_bluetooth_available():
    """
    Checks if Bluetooth stack is accessible on this platform.

    Returns:
        bool: True if Bluetooth is available, False otherwise
    """
    if is_linux():
        try:
            import dbus
            bus = dbus.SystemBus()
            bus.get_object('org.bluez', '/')
            return True
        except Exception:
            return False
    elif is_macos():
        try:
            from IOBluetooth import IOBluetoothDevice
            return True
        except ImportError:
            return False
    return False


def check_usb_available():
    """
    Checks if USB support is available.

    Returns:
        bool: True if PyUSB is available, False otherwise
    """
    try:
        import usb.core
        return True
    except ImportError:
        return False
