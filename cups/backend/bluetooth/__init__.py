#!/usr/bin/env python3
"""
Bluetooth backend dispatcher for phomemo-tools.
Automatically selects the appropriate platform-specific implementation.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platform import get_platform

_backend = None


def get_bluetooth_backend():
    """
    Returns the appropriate Bluetooth backend for the current platform.

    Returns:
        BluetoothBackend: Platform-specific Bluetooth backend instance,
                          or None if Bluetooth is not available.
    """
    global _backend
    if _backend is not None:
        return _backend

    system = get_platform()

    if system == 'linux':
        try:
            from bluetooth.linux import LinuxBluetoothBackend
            _backend = LinuxBluetoothBackend()
        except ImportError as e:
            print(f"WARNING: Linux Bluetooth unavailable: {e}", file=sys.stderr)
            return None
    elif system == 'darwin':
        try:
            from bluetooth.darwin import DarwinBluetoothBackend
            _backend = DarwinBluetoothBackend()
        except ImportError as e:
            print(f"WARNING: macOS Bluetooth unavailable: {e}", file=sys.stderr)
            return None
    else:
        print(f"WARNING: Unsupported platform for Bluetooth: {system}", file=sys.stderr)
        return None

    return _backend


__all__ = ['get_bluetooth_backend']
