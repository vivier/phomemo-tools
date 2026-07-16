#!/usr/bin/env python3
"""
phomemo-m835-bt — Print to Phomemo M835 thermal printer via Bluetooth from Linux.

The M835 uses BLE for discovery and Classic Bluetooth RFCOMM (SPP) for data
transfer. The print protocol is ESC/POS raster (GS v 0), same as the M02 family,
but at 300 DPI with wider paper support.

Discovery: BLE (printer advertises as "M835")
Connection: Classic BT RFCOMM, SPP UUID 00001101, channel 1
Protocol: ESC/POS raster (GS v 0) with Phomemo header/footer
Flow control: 256-byte chunks, 30ms delay (critical — buffer overflows otherwise)

Tested on: Ubuntu 26.04, BlueZ 5.85, Python 3.14
Printer: Phomemo M835-White-Phomemo

Requirements:
    - Python 3 (stdlib bluetooth socket — no PyBluez needed)
    - Pillow (PIL) for image handling
    - bleak (for BLE discovery, optional)
    - BlueZ (bluetoothctl for pairing)

Usage:
    python3 phomemo-m835-bt.py image.png
    python3 phomemo-m835-bt.py image.png --mac FE:10:1D:EE:5F:C2 --feed 40
    python3 phomemo-m835-bt.py --discover

Discovered by: Sean (battlemark-ai) and Mechanic (Hermes Agent, glm-5.2:cloud)
Date: 2026-07-03
"""

import argparse
import socket
import sys
import time
from PIL import Image

# ── Constants ──────────────────────────────────────────────────────────────

PRINTER_MAC = "FE:10:1D:EE:5F:C2"  # Default M835 MAC (from QR code)
RFCOMM_CHANNEL = 1                  # SPP channel (from sdptool)
SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"

# Flow control — critical for not overflowing the printer's buffer
CHUNK_SIZE = 256       # bytes per write
CHUNK_DELAY = 0.03     # 30ms between chunks

# Printer: 300 DPI
DPI = 300
DOTS_PER_MM = DPI / 25.4  # ~11.81 dots/mm

# ESC/POS protocol bytes (Phomemo M02-family variant)
HEADER = b'\x1b\x40'           # ESC @ — initialize printer
PHOMEMO_INIT = b'\x1f\x11\x02\x04'  # Phomemo-specific init sequence
RASTER_CMD = b'\x1d\x76\x30'   # GS v 0 — print raster bit image
FOOTER = (
    b'\x1b\x64\x02'   # ESC d 2 — feed 2 lines
    b'\x1b\x64\x02'   # ESC d 2 — feed 2 lines
    b'\x1f\x11\x08'   # Phomemo footer
    b'\x1f\x11\x0e'
    b'\x1f\x11\x07'
    b'\x1f\x11\x09'
)


# ── Image Processing ────────────────────────────────────────────────────────

def load_image(path, width=None, threshold=128):
    """
    Load an image file and convert to 1-bit (black/white) for thermal printing.

    Args:
        path: Path to image file (PNG, JPG, etc.)
        width: Target width in pixels. If None, uses image's native width
               (rounded up to nearest multiple of 8).
        threshold: Grayscale threshold (0-255). Pixels below this = black.

    Returns:
        PIL.Image in mode '1' (1-bit), width divisible by 8.
    """
    img = Image.open(path)

    if img.mode != 'L':
        img = img.convert('L')

    if width:
        ratio = width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((width, new_height), Image.LANCZOS)

    w, h = img.size
    if w % 8 != 0:
        new_w = ((w + 7) // 8) * 8
        img = img.resize((new_w, h), Image.LANCZOS)

    img = img.point(lambda p: 255 if p > threshold else 0, mode='1')

    return img


def image_to_escpos(img):
    """
    Convert a 1-bit PIL image to ESC/POS raster print data.

    Uses GS v 0 command with Phomemo header/footer.
    Splits into blocks of max 255 lines if image is tall.

    Args:
        img: PIL Image in mode '1' (width must be divisible by 8)

    Returns:
        bytes: Complete ESC/POS data stream ready to send to printer.
    """
    if img.mode != '1':
        raise ValueError("Image must be in 1-bit mode")

    width, height = img.size
    bytes_per_line = width // 8

    data = bytearray()
    data.extend(HEADER)
    data.extend(PHOMEMO_INIT)

    pixels = list(img.getdata())

    max_block = 255
    remaining = height

    while remaining > 0:
        block_lines = min(remaining, max_block)
        start_line = height - remaining

        data.extend(RASTER_CMD)
        data.append(0x00)  # mode: normal
        data.extend(bytes_per_line.to_bytes(2, 'little'))
        data.extend(block_lines.to_bytes(2, 'little'))

        for y in range(start_line, start_line + block_lines):
            for x_byte in range(bytes_per_line):
                byte_val = 0
                for bit in range(8):
                    px = x_byte * 8 + bit
                    if px < width:
                        if pixels[y * width + px] == 0:  # black pixel
                            byte_val |= (0x80 >> bit)
                data.append(byte_val)

        remaining -= block_lines

    data.extend(FOOTER)

    return bytes(data)


def add_feed_space(data, width, feed_mm):
    """
    Append blank raster space for tear-off.

    Args:
        data: Existing ESC/POS bytearray
        width: Image width in pixels (must be divisible by 8)
        feed_mm: Blank space in millimeters

    Returns:
        bytearray with blank space appended
    """
    if feed_mm <= 0:
        return data

    feed_lines = int(feed_mm * DOTS_PER_MM)
    bytes_per_line = width // 8

    data = bytearray(data)
    data.extend(RASTER_CMD)
    data.append(0x00)
    data.extend(bytes_per_line.to_bytes(2, 'little'))
    data.extend(feed_lines.to_bytes(2, 'little'))
    data.extend(b'\x00' * (bytes_per_line * feed_lines))

    return data


# ── Bluetooth ────────────────────────────────────────────────────────────────

def discover_printer(name="M835", timeout=15):
    """
    Scan for the printer via BLE using bleak.

    Returns:
        MAC address string if found, None if not found.
    """
    try:
        from bleak import BleakScanner
    except ImportError:
        print("bleak not installed — install with: pip3 install bleak")
        return None

    import asyncio

    async def scan():
        print(f"Scanning for '{name}' via BLE ({timeout}s)...")
        devices = await BleakScanner.discover(timeout=timeout)
        for d in devices:
            if d.name and name.upper() in d.name.upper():
                print(f"  Found: {d.name} at {d.address}")
                return d.address
        print(f"  '{name}' not found in scan")
        return None

    return asyncio.run(scan())


def pair_printer(mac):
    """
    Pair and trust the printer via bluetoothctl.
    Safe to call if already paired — it will just confirm.
    """
    import subprocess

    print(f"Pairing {mac}...")
    r = subprocess.run(['bluetoothctl', 'pair', mac],
                       capture_output=True, text=True, timeout=15)
    if 'Pairing successful' in r.stdout or 'already paired' in r.stdout.lower():
        print("  Paired.")
    else:
        print(f"  Pair result: {r.stdout.strip()}")

    print(f"Trusting {mac}...")
    r = subprocess.run(['bluetoothctl', 'trust', mac],
                       capture_output=True, text=True, timeout=10)
    print(f"  Trusted.")

    return True


def send_to_printer(data, mac=PRINTER_MAC, channel=RFCOMM_CHANNEL,
                    chunk_size=CHUNK_SIZE, delay=CHUNK_DELAY):
    """
    Send ESC/POS data to the printer via Classic Bluetooth RFCOMM.

    Uses Python's built-in bluetooth socket (AF_BLUETOOTH, BTPROTO_RFCOMM).
    No PyBluez required.

    Args:
        data: ESC/POS byte data
        mac: Printer MAC address
        channel: RFCOMM channel (1 for SPP)
        chunk_size: Bytes per write (flow control)
        delay: Seconds between writes (flow control)

    Returns:
        True if all data sent successfully, False on error.
    """
    total = len(data)
    print(f"Connecting to {mac} channel {channel}...")

    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                         socket.BTPROTO_RFCOMM)
    sock.settimeout(30)

    try:
        sock.connect((mac, channel))
        print(f"Connected! Sending {total} bytes ({total/1024:.1f} KB)...")

        sent = 0
        for i in range(0, total, chunk_size):
            chunk = data[i:i + chunk_size]
            try:
                sock.send(chunk)
                sent += len(chunk)
                pct = sent * 100 // total
                if pct % 10 == 0 and sent > 0:
                    print(f"  {sent}/{total} bytes ({pct}%)")
                time.sleep(delay)
            except Exception as e:
                # Buffer full — drain and retry
                print(f"  Buffer full at {sent} bytes, waiting...")
                sock.settimeout(2)
                try:
                    sock.recv(1024)
                except socket.timeout:
                    pass
                sock.settimeout(30)
                try:
                    sock.send(chunk)
                    sent += len(chunk)
                    time.sleep(delay * 3)  # Longer delay after recovery
                except Exception as e2:
                    print(f"  Send failed: {e2}")
                    return False

        print(f"Sent {sent}/{total} bytes ✓")

        # Read status response
        sock.settimeout(5)
        try:
            resp = sock.recv(1024)
            print(f"Printer response: {resp.hex()} ({len(resp)} bytes)")
        except socket.timeout:
            print("No response (normal for some commands)")

        sock.close()
        return True

    except Exception as e:
        print(f"Connection error: {e}")
        try:
            sock.close()
        except:
            pass
        return False


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Print an image to Phomemo M835 via Bluetooth')
    parser.add_argument('image', nargs='?',
                        help='Image file to print (PNG, JPG, etc.)')
    parser.add_argument('--mac', default=PRINTER_MAC,
                        help=f'Printer MAC address (default: {PRINTER_MAC})')
    parser.add_argument('--width', type=int, default=None,
                        help='Output width in pixels (default: native image width)')
    parser.add_argument('--feed', type=int, default=40,
                        help='Blank space after print in mm (default: 40)')
    parser.add_argument('--threshold', type=int, default=128,
                        help='B/W threshold 0-255 (default: 128, lower=darker)')
    parser.add_argument('--discover', action='store_true',
                        help='Scan for printer via BLE and exit')
    parser.add_argument('--pair-only', action='store_true',
                        help='Pair printer and exit (no print)')

    args = parser.parse_args()

    if args.discover:
        mac = discover_printer()
        if mac:
            print(f"\nPrinter found at {mac}")
            print(f"To pair: bluetoothctl pair {mac}")
        else:
            print("\nPrinter not found. Make sure it's powered on (green light).")
        return

    if args.pair_only:
        pair_printer(args.mac)
        return

    if not args.image:
        parser.print_help()
        print("\nError: image file required for printing")
        sys.exit(1)

    print(f"Loading {args.image}...")
    img = load_image(args.image, width=args.width, threshold=args.threshold)
    print(f"  Image: {img.size[0]}x{img.size[1]}px, {img.size[0]//8} bytes/line")

    print("Converting to ESC/POS raster...")
    data = image_to_escpos(img)
    print(f"  ESC/POS data: {len(data)} bytes ({len(data)/1024:.1f} KB)")

    if args.feed > 0:
        data = add_feed_space(data, img.size[0], args.feed)
        feed_lines = int(args.feed * DOTS_PER_MM)
        print(f"  Added {args.feed}mm ({feed_lines} lines) tear-off space")

    success = send_to_printer(data, mac=args.mac)

    if success:
        print("\n✓ Print complete!")
    else:
        print("\n✗ Print failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()