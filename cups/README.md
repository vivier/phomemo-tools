# Phomemo CUPS Drivers

CUPS printing support for Phomemo thermal label printers on Linux and macOS.

## Contents

- `backend/` - CUPS backends for printer communication
- `filter/` - CUPS filters for raster-to-printer conversion
- `drv/` - PPD driver source files
- `ppd/` - Compiled PPD files

## Installation

### Linux

```bash
make
sudo make install
```

### macOS

```bash
make filters    # Compile native C filter (required)
sudo make install
```

For Bluetooth printing on macOS, also install the helper daemon:
```bash
cd ../macos
./install-bt-helper.sh
```

## Filters

| Filter | Printers | Language |
|--------|----------|----------|
| rastertopm02_t02 | M02, M02 Pro, T02 | Python (Linux), C (macOS) |
| rastertopm110 | M110, M120, M220, M421 | Python (Linux), C (macOS) |
| rastertopd30 | D30 | Python |

The C filter (`filter/rastertopm110.c`) is required on macOS because Python filters are blocked by the CUPS sandbox.

## Backends

| Backend | Connection | Platform |
|---------|------------|----------|
| phomemo | Bluetooth/USB | Linux |
| phomemo-bt | Bluetooth | macOS |

The macOS Bluetooth backend uses a helper daemon architecture to work around TCC restrictions.

## Credits

Some code based on:
- https://behind.pretix.eu/2018/01/20/cups-driver/
- https://github.com/pretix/cups-fgl-printers
