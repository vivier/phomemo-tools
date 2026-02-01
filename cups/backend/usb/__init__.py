#!/usr/bin/env python3
"""
USB backend dispatcher for phomemo-tools.
Automatically selects the appropriate platform-specific implementation.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platform import get_platform

_backend = None


def get_usb_backend():
    """
    Returns the appropriate USB backend for the current platform.

    Returns:
        USBBackend: Platform-specific USB backend instance,
                    or None if USB support is not available.
    """
    global _backend
    if _backend is not None:
        return _backend

    system = get_platform()

    if system == 'linux':
        try:
            from usb.linux import LinuxUSBBackend
            _backend = LinuxUSBBackend()
        except ImportError as e:
            print(f"WARNING: Linux USB unavailable: {e}", file=sys.stderr)
            return None
    elif system == 'darwin':
        try:
            from usb.darwin import DarwinUSBBackend
            _backend = DarwinUSBBackend()
        except ImportError as e:
            print(f"WARNING: macOS USB unavailable: {e}", file=sys.stderr)
            return None
    else:
        print(f"WARNING: Unsupported platform for USB: {system}", file=sys.stderr)
        return None

    return _backend


__all__ = ['get_usb_backend']
