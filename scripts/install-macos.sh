#!/bin/bash
#
# macOS Installation Script for phomemo-tools
#
# This script installs phomemo-tools with full Bluetooth and USB support
# on macOS, including Apple Silicon (M1/M2/M3) Macs.
#
# Requirements:
#   - macOS 11.0 (Big Sur) or later
#   - Homebrew (will be installed if missing)
#   - Python 3.9+
#
# Usage:
#   ./scripts/install-macos.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Phomemo Tools - macOS Installation Script           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo -e "${GREEN}✓${NC} Detected: Apple Silicon (arm64)"
    HOMEBREW_PREFIX="/opt/homebrew"
else
    echo -e "${GREEN}✓${NC} Detected: Intel ($ARCH)"
    HOMEBREW_PREFIX="/usr/local"
fi

# Check macOS version
MACOS_VERSION=$(sw_vers -productVersion)
echo -e "${GREEN}✓${NC} macOS Version: $MACOS_VERSION"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to install Homebrew if missing
install_homebrew() {
    if ! command_exists brew; then
        echo -e "${YELLOW}→${NC} Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add Homebrew to PATH for Apple Silicon
        if [ "$ARCH" = "arm64" ]; then
            eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"
        fi
    else
        echo -e "${GREEN}✓${NC} Homebrew is already installed"
    fi
}

# Function to check Python version
check_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
            echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
            return 0
        fi
    fi
    return 1
}

# Step 1: Install Homebrew
echo -e "${BLUE}Step 1: Checking Homebrew...${NC}"
install_homebrew
echo ""

# Step 2: Install system dependencies
echo -e "${BLUE}Step 2: Installing system dependencies...${NC}"
brew install python3 libusb 2>/dev/null || true
echo -e "${GREEN}✓${NC} System dependencies installed"
echo ""

# Step 3: Check Python version
echo -e "${BLUE}Step 3: Checking Python version...${NC}"
if ! check_python; then
    echo -e "${RED}✗${NC} Python 3.9+ is required. Installing..."
    brew install python@3.11
fi
echo ""

# Step 4: Install Python dependencies
echo -e "${BLUE}Step 4: Installing Python dependencies...${NC}"

# Core dependencies
echo -e "${YELLOW}→${NC} Installing core dependencies (pillow, pyusb)..."
pip3 install --user pillow pyusb

# PyObjC for Bluetooth support
echo -e "${YELLOW}→${NC} Installing PyObjC for Bluetooth support..."
pip3 install --user pyobjc-framework-IOBluetooth pyobjc-framework-CoreBluetooth pyobjc-core

echo -e "${GREEN}✓${NC} Python dependencies installed"
echo ""

# Step 5: Get script directory and navigate to repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

echo -e "${BLUE}Step 5: Building CUPS drivers...${NC}"
echo -e "${YELLOW}→${NC} Working directory: $REPO_DIR"

# Build PPD files
cd cups
if command_exists ppdc; then
    make ppds
    echo -e "${GREEN}✓${NC} PPD files built"
else
    echo -e "${YELLOW}!${NC} ppdc not found - using pre-built PPDs if available"
fi
echo ""

# Step 6: Create CUPS directories
echo -e "${BLUE}Step 6: Creating CUPS directories...${NC}"
echo -e "${YELLOW}→${NC} This requires administrator privileges"

sudo mkdir -p /usr/local/lib/cups/backend
sudo mkdir -p /usr/local/lib/cups/backend/bluetooth
sudo mkdir -p /usr/local/lib/cups/backend/usb
sudo mkdir -p /usr/local/lib/cups/filter
sudo mkdir -p /Library/Printers/PPDs/Contents/Resources/Phomemo

echo -e "${GREEN}✓${NC} CUPS directories created"
echo ""

# Step 7: Install files
echo -e "${BLUE}Step 7: Installing phomemo-tools...${NC}"
sudo make install-darwin
echo -e "${GREEN}✓${NC} Files installed"
echo ""

# Step 8: Configure CUPS
echo -e "${BLUE}Step 8: Configuring CUPS...${NC}"

CUPS_CONF="/etc/cups/cups-files.conf"
SERVERBIN_LINE="ServerBin /usr/local/lib/cups"

if grep -q "^ServerBin" "$CUPS_CONF" 2>/dev/null; then
    if grep -q "^$SERVERBIN_LINE" "$CUPS_CONF"; then
        echo -e "${GREEN}✓${NC} CUPS already configured for custom backend path"
    else
        echo -e "${YELLOW}!${NC} Warning: ServerBin is already set in cups-files.conf"
        echo -e "   You may need to manually add: $SERVERBIN_LINE"
    fi
else
    echo -e "${YELLOW}→${NC} Adding ServerBin configuration..."
    echo "$SERVERBIN_LINE" | sudo tee -a "$CUPS_CONF" > /dev/null
    echo -e "${GREEN}✓${NC} CUPS configuration updated"
fi
echo ""

# Step 9: Restart CUPS
echo -e "${BLUE}Step 9: Restarting CUPS service...${NC}"
sudo launchctl stop org.cups.cupsd 2>/dev/null || true
sleep 1
sudo launchctl start org.cups.cupsd
echo -e "${GREEN}✓${NC} CUPS restarted"
echo ""

# Done!
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║               Installation Complete!                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Pair your Phomemo printer via System Settings → Bluetooth"
echo ""
echo "2. Add the printer using one of these methods:"
echo ""
echo "   ${YELLOW}GUI:${NC}"
echo "   - Open System Settings → Printers & Scanners"
echo "   - Click '+' to add a printer"
echo "   - Your Phomemo printer should appear in the list"
echo ""
echo "   ${YELLOW}Command Line (Bluetooth):${NC}"
echo "   sudo lpadmin -p PhomemoM02 -E \\"
echo "       -v phomemo://AABBCCDDEEFF \\"
echo "       -P /Library/Printers/PPDs/Contents/Resources/Phomemo/Phomemo-M02.ppd.gz"
echo ""
echo "   ${YELLOW}Command Line (USB):${NC}"
echo "   sudo lpadmin -p PhomemoM02 -E \\"
echo "       -v serial:/dev/cu.usbmodem* \\"
echo "       -P /Library/Printers/PPDs/Contents/Resources/Phomemo/Phomemo-M02.ppd.gz"
echo ""
echo "3. Test printing:"
echo "   echo 'Hello World' | lp -d PhomemoM02 -o media=w50h60 -"
echo ""
echo -e "${BLUE}Troubleshooting:${NC}"
echo "   - Check CUPS logs: tail -f /var/log/cups/error_log"
echo "   - List printers:   lpstat -p -d"
echo "   - Run discovery:   /usr/local/lib/cups/backend/phomemo"
echo ""
