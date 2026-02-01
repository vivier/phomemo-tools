# Phomemo Tools

Linux and macOS printing support for Phomemo thermal label printers.

## Supported Printers

| Model | Resolution | Paper Width | Connection |
|-------|-----------|-------------|------------|
| M02 | 203 dpi | 50mm | Bluetooth, USB |
| M02 Pro | 300 dpi | 50mm | Bluetooth, USB |
| T02 | 203 dpi | 50mm | Bluetooth, USB |
| M110 | 203 dpi | 20-50mm | Bluetooth, USB |
| M120 | 203 dpi | 20-50mm | Bluetooth, USB |
| M220 | 203 dpi | 20-70mm | Bluetooth, USB |
| M421 | 203 dpi | 40-70mm | Bluetooth, USB |
| D30 | 203 dpi | 30-40mm | Bluetooth, USB |

## Platform Support

| Feature | Linux | macOS |
|---------|-------|-------|
| USB Printing | Yes | Yes |
| Bluetooth Printing | Yes | Yes |
| CUPS Integration | Yes | Yes |
| Direct Printing | Yes | Yes |

## Quick Start

### Linux

```bash
# Install dependencies
sudo apt-get install cups python3-pil python3-pyusb

# Build and install
cd cups
make
sudo make install

# Add printer
sudo lpadmin -p MyPrinter -E -v phomemo://AABBCCDDEEFF \
    -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz

# Print
lp -d MyPrinter image.png
```

### macOS

```bash
# Install dependencies
brew install libusb
pip3 install Pillow pyusb pyobjc-framework-IOBluetooth

# Build and install
cd cups
make filters
sudo make install

# For Bluetooth CUPS printing
cd ../macos
./install-bt-helper.sh

# Direct printing (simplest)
python3 macos/print-bluetooth.py image.png
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/README.MD](docs/README.MD) | Complete documentation with protocol reference |
| [macos/README.md](macos/README.md) | macOS-specific setup and troubleshooting |
| [cups/README.md](cups/README.md) | CUPS drivers and filters |

## Project Structure

```
phomemo-tools/
├── cups/                   # CUPS drivers
│   ├── backend/            # Printer backends
│   ├── filter/             # Raster filters
│   ├── drv/                # PPD sources
│   └── ppd/                # Compiled PPDs
├── macos/                  # macOS support
│   ├── print-bluetooth.py  # Direct BT printing
│   ├── print-usb.py        # Direct USB printing
│   └── install-bt-helper.sh
├── tools/                  # Command-line tools
│   ├── phomemo-filter.py   # Image converter
│   └── format-checker.py   # Protocol validator
├── images/                 # Sample images
└── docs/                   # Documentation
```

## License

GNU General Public License v3

Image assets in `images/` are provided under a separate license - see `images/LICENSE`.

## Credits

Protocol reverse-engineered from Android Bluetooth packet captures.

Some CUPS code based on [pretix/cups-fgl-printers](https://github.com/pretix/cups-fgl-printers).
