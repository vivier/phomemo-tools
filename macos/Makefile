# Phomemo Tools - macOS Build and Installation
#
# This Makefile handles building and installing Phomemo printer drivers
# for macOS with USB support only.
#
# Usage:
#   make check      - Check dependencies
#   make install    - Install drivers (requires sudo)
#   make uninstall  - Remove drivers (requires sudo)
#   make test       - Test USB device detection
#

SHELL := /bin/bash

# Directories
PROJECT_DIR := $(shell dirname $(CURDIR))
CUPS_FILTER_DIR := /usr/local/libexec/cups/filter
CUPS_BACKEND_DIR := /usr/local/libexec/cups/backend
CUPS_PPD_DIR := /Library/Printers/PPDs/Contents/Resources/Phomemo
SHARE_DIR := /usr/local/share/phomemo

.PHONY: all check install uninstall test clean help

all: check
	@echo "Run 'sudo make install' to install the drivers"

help:
	@echo "Phomemo Tools - macOS USB Build"
	@echo ""
	@echo "Targets:"
	@echo "  check     - Check dependencies"
	@echo "  install   - Install drivers (requires sudo)"
	@echo "  uninstall - Remove drivers (requires sudo)"
	@echo "  test      - Test USB device detection"
	@echo ""

check:
	@echo "Checking dependencies..."
	@echo ""
	@echo "Python 3:"
	@python3 --version || (echo "ERROR: Python 3 not found"; exit 1)
	@echo ""
	@echo "Python packages:"
	@python3 -c "import PIL; print('  Pillow:', PIL.__version__)" 2>/dev/null || echo "  Pillow: NOT INSTALLED (pip3 install Pillow)"
	@python3 -c "import usb; print('  PyUSB: OK')" 2>/dev/null || echo "  PyUSB: NOT INSTALLED (pip3 install pyusb)"
	@echo ""
	@echo "libusb (via Homebrew):"
	@brew list libusb >/dev/null 2>&1 && echo "  libusb: OK" || echo "  libusb: NOT INSTALLED (brew install libusb)"
	@echo ""

install:
	@if [ "$$(id -u)" != "0" ]; then \
		echo "Error: This target requires root privileges. Use 'sudo make install'"; \
		exit 1; \
	fi
	@echo "Installing Phomemo USB drivers for macOS..."
	@mkdir -p $(CUPS_FILTER_DIR)
	@mkdir -p $(CUPS_BACKEND_DIR)
	@mkdir -p $(CUPS_PPD_DIR)
	@mkdir -p $(SHARE_DIR)
	@echo "  Installing filters..."
	@install -m 755 $(PROJECT_DIR)/cups/filter/rastertopm02_t02.py $(CUPS_FILTER_DIR)/rastertopm02_t02
	@install -m 755 $(PROJECT_DIR)/cups/filter/rastertopm110.py $(CUPS_FILTER_DIR)/rastertopm110
	@install -m 755 $(PROJECT_DIR)/cups/filter/rastertopd30.py $(CUPS_FILTER_DIR)/rastertopd30
	@echo "  Installing USB backend..."
	@install -m 755 backend/phomemo-usb.py $(CUPS_BACKEND_DIR)/phomemo
	@echo "  Installing tools..."
	@install -m 755 $(PROJECT_DIR)/tools/phomemo-filter.py $(SHARE_DIR)/phomemo-filter.py
	@install -m 644 $(PROJECT_DIR)/README.md $(SHARE_DIR)/ 2>/dev/null || true
	@install -m 644 $(PROJECT_DIR)/LICENSE $(SHARE_DIR)/ 2>/dev/null || true
	@if [ -d "$(PROJECT_DIR)/cups/ppd" ]; then \
		echo "  Installing PPD files..."; \
		for ppd in $(PROJECT_DIR)/cups/ppd/*.ppd.gz; do \
			[ -f "$$ppd" ] && install -m 644 "$$ppd" $(CUPS_PPD_DIR)/; \
		done; \
	else \
		echo "  Warning: PPD files not found. Build them first with 'make -C ../cups'"; \
	fi
	@echo "  Restarting CUPS..."
	@launchctl stop org.cups.cupsd 2>/dev/null || true
	@launchctl start org.cups.cupsd 2>/dev/null || true
	@echo ""
	@echo "Installation complete!"
	@echo "Connect your Phomemo printer via USB and add it in System Preferences."

uninstall:
	@if [ "$$(id -u)" != "0" ]; then \
		echo "Error: This target requires root privileges. Use 'sudo make uninstall'"; \
		exit 1; \
	fi
	@echo "Removing Phomemo drivers..."
	@rm -f $(CUPS_FILTER_DIR)/rastertopm02_t02
	@rm -f $(CUPS_FILTER_DIR)/rastertopm110
	@rm -f $(CUPS_FILTER_DIR)/rastertopd30
	@rm -f $(CUPS_BACKEND_DIR)/phomemo
	@rm -rf $(CUPS_PPD_DIR)
	@rm -rf $(SHARE_DIR)
	@launchctl stop org.cups.cupsd 2>/dev/null || true
	@launchctl start org.cups.cupsd 2>/dev/null || true
	@echo "Uninstall complete."

test:
	@echo "Testing USB device detection..."
	@echo ""
	@python3 backend/phomemo-usb.py || echo "No devices found or error occurred"

clean:
	@echo "Nothing to clean for macOS build"
