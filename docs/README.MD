# Phomemo Tools Documentation

Complete documentation for phomemo-tools, covering Linux and macOS support for Phomemo thermal label printers.

## Table of Contents

1. [Overview](#overview)
2. [Supported Printers](#supported-printers)
3. [Quick Start](#quick-start)
4. [Command-Line Tools](#command-line-tools)
5. [CUPS Integration](#cups-integration)
6. [macOS Support](#macos-support)
7. [Protocol Reference](#protocol-reference)
8. [Troubleshooting](#troubleshooting)

---

## Overview

Phomemo-tools provides complete printing support for Phomemo thermal label printers on Linux and macOS. The package includes:

- **Command-line tools** for direct printing via Bluetooth or USB
- **CUPS backend** for printer discovery and connection management
- **CUPS filters** for converting raster images to printer protocol
- **PPD drivers** for printer capability definitions

All protocol information has been reverse-engineered from Bluetooth packet captures.

---

## Supported Printers

| Model | Resolution | Paper Width | Connection | Filter |
|-------|-----------|-------------|------------|--------|
| M02 | 203 dpi | 50mm (384 dots) | BT/USB | rastertopm02_t02 |
| M02 Pro | 300 dpi | 50mm | BT/USB | rastertopm02_t02 |
| T02 | 203 dpi | 50mm (384 dots) | BT/USB | rastertopm02_t02 |
| M110 | 203 dpi | 20-50mm (344 dots max) | BT/USB | rastertopm110 |
| M120 | 203 dpi | 20-50mm | BT/USB | rastertopm110 |
| M220 | 203 dpi | 20-70mm | BT/USB | rastertopm110 |
| M421 | 203 dpi | 40-70mm | BT/USB | rastertopm110 |
| D30 | 203 dpi | 30-40mm | BT/USB | rastertopd30 |

---

## Quick Start

### Linux

```bash
# Install dependencies
sudo apt-get install cups python3-pil python3-pyusb

# Clone and install
git clone https://github.com/vivier/phomemo-tools.git
cd phomemo-tools/cups
make
sudo make install

# Add printer via CUPS web interface or CLI
sudo lpadmin -p MyPhomemo -E -v phomemo://AABBCCDDEEFF \
    -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

### macOS

```bash
# Install dependencies
brew install libusb
pip3 install Pillow pyusb pyobjc-framework-IOBluetooth

# Clone and install
git clone https://github.com/vivier/phomemo-tools.git
cd phomemo-tools/cups
make filters  # Compile native C filter
sudo make install

# For Bluetooth CUPS printing, install helper daemon
cd ../macos
./install-bt-helper.sh
```

---

## Command-Line Tools

### phomemo-filter.py

**Location:** `tools/phomemo-filter.py`

Converts images to printer protocol and outputs to stdout.

```bash
# Print via Bluetooth (Linux)
tools/phomemo-filter.py image.png > /dev/rfcomm0

# Print via USB
tools/phomemo-filter.py image.png > /dev/usb/lp0

# Disable auto-rotation
tools/phomemo-filter.py --no-rotate image.png > /dev/rfcomm0
```

**Options:**
| Option | Description |
|--------|-------------|
| `--no-rotate` | Disable automatic rotation of landscape images |
| `file` | Path to the image file (PNG, JPG, etc.) |

### format-checker.py

**Location:** `tools/format-checker.py`

Validates and reconstructs images from printer protocol data. Useful for debugging.

```bash
tools/phomemo-filter.py image.png | tools/format-checker.py
```

---

## CUPS Integration

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Application   │────▶│   CUPS Daemon    │────▶│  CUPS Backend   │
│ (lp, lpr, GUI)  │     │   (cupsd)        │     │  (phomemo)      │
└─────────────────┘     └────────┬─────────┘     └────────┬────────┘
                                 │                        │
                        ┌────────▼─────────┐              │
                        │   CUPS Filter    │              │
                        │ (rastertopm*)    │              │
                        └────────┬─────────┘              │
                                 │                        │
                        ┌────────▼─────────┐     ┌────────▼────────┐
                        │  Printer Data    │────▶│ Printer Device  │
                        │  (ESC/POS)       │     │  (BT/USB)       │
                        └──────────────────┘     └─────────────────┘
```

### CUPS Filters

All filters convert CUPS Raster format to printer-specific ESC/POS protocol.

| Filter | Printers | Notes |
|--------|----------|-------|
| rastertopm02_t02 | M02, M02 Pro, T02 | 255-line blocks |
| rastertopm110 | M110, M120, M220, M421 | Speed/density control |
| rastertopd30 | D30 | 90° rotation |

### PPD Driver Files

| Driver | Models | Resolution |
|--------|--------|------------|
| Phomemo-M02.ppd | M02, T02 | 203 dpi |
| Phomemo-M02Pro.ppd | M02 Pro | 300 dpi |
| Phomemo-M110.ppd | M110, M120 | 203 dpi |
| Phomemo-M220.ppd | M220 | 203 dpi |
| Phomemo-M421.ppd | M421 | 203 dpi |
| Phomemo-D30.ppd | D30 | 203 dpi |

### Adding a Printer

**Via CLI (Bluetooth):**
```bash
sudo lpadmin -p M02 -E -v phomemo://DC0D309023C7 \
    -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

**Via CLI (USB):**
```bash
sudo lpadmin -p M02 -E -v serial:/dev/usb/lp0 \
    -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

**Printing:**
```bash
echo "Hello World" | lp -d M02 -o media=w50h60 -
lp -d M02 -o media=w50h60 image.png
```

---

## macOS Support

Phomemo-tools provides **full macOS support** including Apple Silicon (M1/M2/M3/M4).

### Feature Support

| Feature | Status | Notes |
|---------|--------|-------|
| USB Printing | Full | Via PyUSB |
| Bluetooth Printing | Full | Via IOBluetooth |
| CUPS Filters | Full | Native C filter |
| CUPS Bluetooth | Full | Via helper daemon |
| Direct Printing | Full | Scripts in macos/ |

### Installation

#### Prerequisites

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install libusb
pip3 install Pillow pyusb pyobjc-framework-IOBluetooth
```

#### Install CUPS Components

```bash
cd cups
make filters    # Compile native C filter (required for macOS)
sudo make install
```

#### Install Bluetooth Helper (for CUPS Bluetooth printing)

```bash
cd macos
./install-bt-helper.sh
```

This installs:
- Helper daemon at `~/Library/Application Support/Phomemo/`
- LaunchAgent for auto-start
- CUPS backend at `/usr/libexec/cups/backend/phomemo-bt`

### Direct Printing (Without CUPS)

#### USB Printing

```bash
cd macos
python3 print-usb.py image.png
```

#### Bluetooth Printing

```bash
cd macos
python3 print-bluetooth.py image.png
```

### CUPS Printing

#### Adding a Bluetooth Printer

1. Pair the printer in **System Settings > Bluetooth**
2. Open **System Settings > Printers & Scanners**
3. Click **+** to add a printer
4. Select your Phomemo printer (phomemo-bt:// URI)
5. Choose the appropriate PPD

Or via CLI:
```bash
# Find printer address
python3 -c "from IOBluetooth import IOBluetoothDevice; [print(f'{d.name()}: {d.addressString()}') for d in IOBluetoothDevice.pairedDevices() or []]"

# Add printer
sudo lpadmin -p M220_BT -E -v phomemo-bt://f9-29-79-d5-7b-fe \
    -P /Library/Printers/PPDs/Contents/Resources/Phomemo/Phomemo-M220.ppd
```

### Architecture (macOS Bluetooth CUPS)

Due to macOS TCC (Transparency, Consent, and Control) restrictions, CUPS daemons cannot directly access Bluetooth. The solution uses a helper daemon:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│    CUPS     │────▶│   Backend   │────▶│   Unix Socket       │
│   Daemon    │     │ phomemo-bt  │     │ /tmp/phomemo-bt.sock│
└─────────────┘     └─────────────┘     └──────────┬──────────┘
                                                   │
                                        ┌──────────▼──────────┐
                                        │   Helper Daemon     │
                                        │ (user LaunchAgent)  │
                                        └──────────┬──────────┘
                                                   │ IOBluetooth
                                        ┌──────────▼──────────┐
                                        │  Bluetooth Printer  │
                                        └─────────────────────┘
```

The helper daemon runs as a user process with Bluetooth permissions and communicates with the CUPS backend via Unix socket.

### Troubleshooting (macOS)

#### Filter Failed

The Python CUPS filters don't work on macOS due to sandbox restrictions. Use the native C filter:

```bash
cd cups
make filters
sudo make install
```

#### Bluetooth Helper Not Running

```bash
# Check status
ls -la /tmp/phomemo-bt.sock

# View logs
tail -f /tmp/phomemo-bt-helper.log

# Restart helper
launchctl unload ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
launchctl load ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
```

#### Printer Not Found

1. Ensure printer is paired in System Settings > Bluetooth
2. Check PyObjC is installed: `python3 -c "from IOBluetooth import IOBluetoothDevice; print('OK')"`
3. Grant Bluetooth access to Terminal in System Settings > Privacy & Security > Bluetooth

---

## Protocol Reference

### M02/T02 Protocol (ESC/POS)

**Header:**
```
1B 40        ESC @     Initialize printer
1B 61 01     ESC a 1   Center justification
1F 11 02 04            Phomemo-specific init
```

**Image Block (max 256 lines):**
```
1D 76 30     GS v 0    Print raster bit image
00                     Mode (0=normal)
30 00                  Bytes per line (48 = 384/8), little-endian
FF 00                  Lines (max 255), little-endian
[image data]           48 bytes/line, MSB first
```

**Footer:**
```
1B 64 02     ESC d 2   Feed 2 lines
1F 11 08/0E/07/09      Phomemo-specific
```

### M110/M120/M220/M421 Protocol

**Header:**
```
1B 4E 0D 05  Print speed (01-05)
1B 4E 04 0F  Print density (01-0F)
1F 11 0A     Media type (0A=gaps, 0B=continuous, 26=marks)
```

**Image Block:**
```
1D 76 30 00  GS v 0
2B 00        Bytes per line (43 = 344/8)
F0 00        Lines
[data]
```

**Footer:**
```
1F F0 05 00  End print
1F F0 03 00  Finalize
```

---

## Troubleshooting

### Filter Failure Error

Install Python dependencies:
```bash
# Linux
sudo apt-get install python3-pil python3-pyusb

# macOS - use native C filter instead
cd cups && make filters && sudo make install
```

### Bluetooth Permission Denied (Linux)

```bash
# Fedora/SELinux
sudo semanage permissive -a cupsd_t
```

### Printer Not Discovered

1. Ensure printer is paired (Bluetooth) or connected (USB)
2. Run backend manually: `/usr/lib/cups/backend/phomemo`
3. Check CUPS logs: `tail -f /var/log/cups/error_log`

### Image Quality Issues

- Use high-contrast black & white images
- Optimal width: 384 pixels (M02/T02), 344 pixels (M110)
- Avoid gradients (thermal printers use dithering)

---

## License

Phomemo-tools is licensed under the GNU General Public License v3.

Image assets in the `images/` directory are provided under a separate license - see `images/LICENSE`.
