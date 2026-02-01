#!/bin/bash
#
# Phomemo Tools - macOS USB Installation Script
#
# This script installs Phomemo printer drivers for macOS with USB support.
# Bluetooth is not supported on macOS due to different Bluetooth stack requirements.
#
# Usage: sudo ./install.sh
#
# Requirements:
#   - macOS 10.15 (Catalina) or later
#   - Python 3.8+
#   - Homebrew (for libusb)
#   - PyUSB and Pillow Python packages
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# CUPS directories on macOS
CUPS_FILTER_DIR="/usr/local/libexec/cups/filter"
CUPS_BACKEND_DIR="/usr/local/libexec/cups/backend"
CUPS_PPD_DIR="/Library/Printers/PPDs/Contents/Resources"
SHARE_DIR="/usr/local/share/phomemo"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo " Phomemo Tools - macOS USB Installer"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed${NC}"
    echo "Install Python 3 from https://python.org or via Homebrew: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}Found Python ${PYTHON_VERSION}${NC}"

# Check for required Python packages
echo "Checking Python dependencies..."

check_python_package() {
    if python3 -c "import $1" 2>/dev/null; then
        echo -e "  ${GREEN}$1 - OK${NC}"
        return 0
    else
        echo -e "  ${YELLOW}$1 - Missing${NC}"
        return 1
    fi
}

MISSING_PACKAGES=""
if ! check_python_package "PIL"; then
    MISSING_PACKAGES="$MISSING_PACKAGES Pillow"
fi
if ! check_python_package "usb"; then
    MISSING_PACKAGES="$MISSING_PACKAGES pyusb"
fi

if [ -n "$MISSING_PACKAGES" ]; then
    echo ""
    echo -e "${YELLOW}Missing Python packages:$MISSING_PACKAGES${NC}"
    echo "Install them with: pip3 install$MISSING_PACKAGES"
    echo ""
    read -p "Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for libusb (required by PyUSB on macOS)
if ! brew list libusb &>/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: libusb not found via Homebrew${NC}"
    echo "PyUSB requires libusb. Install with: brew install libusb"
fi

echo ""
echo "Installing Phomemo drivers..."

# Create directories
echo "  Creating directories..."
mkdir -p "$CUPS_FILTER_DIR"
mkdir -p "$CUPS_BACKEND_DIR"
mkdir -p "$CUPS_PPD_DIR/Phomemo"
mkdir -p "$SHARE_DIR"

# Install filters
echo "  Installing CUPS filters..."
install -m 755 "$PROJECT_DIR/cups/filter/rastertopm02_t02.py" "$CUPS_FILTER_DIR/rastertopm02_t02"
install -m 755 "$PROJECT_DIR/cups/filter/rastertopm110.py" "$CUPS_FILTER_DIR/rastertopm110"
install -m 755 "$PROJECT_DIR/cups/filter/rastertopd30.py" "$CUPS_FILTER_DIR/rastertopd30"

# Install USB backend
echo "  Installing USB backend..."
install -m 755 "$SCRIPT_DIR/backend/phomemo-usb.py" "$CUPS_BACKEND_DIR/phomemo"

# Install tools
echo "  Installing tools..."
install -m 755 "$PROJECT_DIR/tools/phomemo-filter.py" "$SHARE_DIR/phomemo-filter.py"
install -m 644 "$PROJECT_DIR/README.md" "$SHARE_DIR/"
install -m 644 "$PROJECT_DIR/LICENSE" "$SHARE_DIR/"

# Check if PPDs exist (they need to be built first)
if [ -d "$PROJECT_DIR/cups/ppd" ]; then
    echo "  Installing PPD files..."
    for ppd in "$PROJECT_DIR/cups/ppd"/*.ppd.gz; do
        if [ -f "$ppd" ]; then
            install -m 644 "$ppd" "$CUPS_PPD_DIR/Phomemo/"
        fi
    done
else
    echo -e "  ${YELLOW}Warning: PPD files not found. Run 'make' in the cups directory first.${NC}"
fi

# Restart CUPS
echo ""
echo "Restarting CUPS..."
launchctl stop org.cups.cupsd 2>/dev/null || true
launchctl start org.cups.cupsd 2>/dev/null || true

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Connect your Phomemo printer via USB"
echo "  2. Open System Preferences > Printers & Scanners"
echo "  3. Click '+' to add a printer"
echo "  4. Select your Phomemo printer from the list"
echo "  5. Choose the appropriate PPD driver"
echo ""
echo "For direct printing (without CUPS), use:"
echo "  python3 $SHARE_DIR/phomemo-filter.py image.png | cat > /dev/cu.usbmodem*"
echo ""
echo "Note: On Apple Silicon Macs, you may need to allow the USB device"
echo "      in System Preferences > Security & Privacy."
