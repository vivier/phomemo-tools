# Phomemo Tools - macOS Support

Full macOS support for Phomemo thermal printers, including Apple Silicon (M1/M2/M3/M4).

## Features

| Feature | Status | Method |
|---------|--------|--------|
| USB Printing | Full | PyUSB |
| Bluetooth Printing | Full | IOBluetooth/PyObjC |
| CUPS Integration | Full | Native C filter + helper daemon |
| Direct Printing | Full | Python scripts |

## Supported Printers

- Phomemo M02, M02 Pro, T02
- Phomemo M110, M120, M220, M421
- Phomemo D30

## Requirements

- macOS 10.15 (Catalina) or later
- Python 3.8 or later
- Xcode Command Line Tools

## Quick Start

### 1. Install Dependencies

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install libusb
brew install libusb

# Install Python packages
pip3 install Pillow pyusb pyobjc-framework-IOBluetooth
```

### 2. Direct Printing (Simplest)

#### Bluetooth

```bash
# Pair printer in System Settings > Bluetooth first
python3 print-bluetooth.py image.png
```

#### USB

```bash
python3 print-usb.py image.png
```

### 3. CUPS Printing (Full Integration)

```bash
# Install CUPS components
cd ../cups
make filters
sudo make install

# Install Bluetooth helper (for BT printing via CUPS)
cd ../macos
./install-bt-helper.sh

# Add printer in System Settings > Printers & Scanners
```

## Direct Printing Scripts

### print-bluetooth.py

Prints directly to a Bluetooth-paired Phomemo printer.

```bash
python3 print-bluetooth.py <image_file>
```

Features:
- Auto-detects paired Phomemo printers
- Converts images to printer format
- Supports all Phomemo models

### print-usb.py

Prints directly via USB connection.

```bash
python3 print-usb.py <image_file>
```

Features:
- Auto-detects USB Phomemo printers
- Supports multiple vendor IDs (0x0493, 0x0483)
- Works with all USB-capable models

## CUPS Integration

### How It Works

macOS security (TCC) prevents CUPS from accessing Bluetooth directly. This is solved with a helper daemon architecture:

```
CUPS → phomemo-bt backend → Unix socket → Helper daemon → Bluetooth → Printer
```

The helper daemon runs as a user LaunchAgent with Bluetooth permissions.

### Installation

```bash
./install-bt-helper.sh
```

This installs:
- `phomemo-bt-helper.py` → `~/Library/Application Support/Phomemo/`
- `com.phomemo.bt-helper.plist` → `~/Library/LaunchAgents/`
- `phomemo-bt` → `/usr/libexec/cups/backend/`

### Adding a Bluetooth Printer

1. Pair printer in **System Settings > Bluetooth**
2. Open **System Settings > Printers & Scanners**
3. Click **+** to add printer
4. Your Phomemo printer should appear with `phomemo-bt://` URI
5. Select appropriate PPD driver

### Manual Printer Setup

```bash
# List paired Bluetooth devices
python3 -c "
from IOBluetooth import IOBluetoothDevice
for d in IOBluetoothDevice.pairedDevices() or []:
    print(f'{d.name()}: {d.addressString()}')
"

# Add printer manually
sudo lpadmin -p M220_BT -E \
    -v phomemo-bt://f9-29-79-d5-7b-fe \
    -P /Library/Printers/PPDs/Contents/Resources/Phomemo/Phomemo-M220.ppd

# Print test
echo "Hello" | lp -d M220_BT
```

## Troubleshooting

### Bluetooth Helper Not Running

```bash
# Check socket exists
ls -la /tmp/phomemo-bt.sock

# View logs
tail -f /tmp/phomemo-bt-helper.log

# Restart helper
launchctl unload ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
launchctl load ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
```

### "No module named 'objc'"

Install PyObjC:
```bash
pip3 install pyobjc-framework-IOBluetooth
```

### "No module named 'usb'"

Install PyUSB:
```bash
pip3 install pyusb
brew install libusb
```

### Bluetooth Printer Not Found

1. Check printer is paired in System Settings > Bluetooth
2. Grant Bluetooth access to Terminal: System Settings > Privacy & Security > Bluetooth
3. Test discovery:
   ```bash
   python3 -c "from IOBluetooth import IOBluetoothDevice; print([d.name() for d in IOBluetoothDevice.pairedDevices() or []])"
   ```

### CUPS Filter Failed

macOS sandbox blocks Python filters. Use the native C filter:
```bash
cd ../cups
make filters
sudo make install
```

### USB Device Not Found

1. Check printer is connected and powered on
2. Try different USB port
3. Check USB permissions in System Settings > Privacy & Security
4. List USB devices:
   ```bash
   system_profiler SPUSBDataType | grep -A5 -i phomemo
   ```

### CUPS Printer Disabled After Error

```bash
cupsenable <printer_name>
```

## Uninstallation

```bash
# Remove helper daemon
launchctl unload ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
rm ~/Library/LaunchAgents/com.phomemo.bt-helper.plist
rm -rf ~/Library/Application\ Support/Phomemo

# Remove CUPS backend (requires sudo)
sudo rm /usr/libexec/cups/backend/phomemo-bt

# Remove CUPS filter and PPDs
sudo rm /usr/libexec/cups/filter/rastertopm110
sudo rm -rf /Library/Printers/PPDs/Contents/Resources/Phomemo
```

## Files

| File | Description |
|------|-------------|
| `print-bluetooth.py` | Direct Bluetooth printing script |
| `print-usb.py` | Direct USB printing script |
| `phomemo-bt-helper.py` | CUPS Bluetooth helper daemon |
| `com.phomemo.bt-helper.plist` | LaunchAgent for helper daemon |
| `install-bt-helper.sh` | Installation script |

## License

GNU General Public License v3
