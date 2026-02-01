# Phomemo CUPS Driver Makefile
# Supports both Linux and macOS (including Apple Silicon)

# Platform detection
UNAME := $(shell uname)
ARCH := $(shell uname -m)

# Platform-specific paths
ifeq ($(UNAME), Darwin)
    # macOS paths (using /usr/local to avoid SIP restrictions)
    CUPS_BACKEND_DIR = /usr/local/lib/cups/backend
    CUPS_FILTER_DIR = /usr/local/lib/cups/filter
    CUPS_PPD_DIR = /Library/Printers/PPDs/Contents/Resources/Phomemo
    CUPS_DRV_DIR = /Library/Printers/PPDs/Contents/Resources
    # macOS install command (doesn't support -D flag)
    INSTALL = install
    INSTALL_DIR = install -d
else
    # Linux paths (default)
    CUPS_BACKEND_DIR = $(DESTDIR)/usr/lib/cups/backend
    CUPS_FILTER_DIR = $(DESTDIR)/usr/lib/cups/filter
    CUPS_PPD_DIR = $(DESTDIR)/usr/share/cups/model/Phomemo
    CUPS_DRV_DIR = $(DESTDIR)/usr/share/cups/drv
    # Linux install command
    INSTALL = install -D
    INSTALL_DIR = install -d
endif

# Python module directories (relative to backend)
BLUETOOTH_DIR = $(CUPS_BACKEND_DIR)/bluetooth
USB_DIR = $(CUPS_BACKEND_DIR)/usb

.PHONY: all ppds filters install install-linux install-darwin install-common clean

all: ppds filters

ppds:
	LC_ALL=C ppdc -z drv/*

# Compile C filters (required for macOS due to Python sandbox restrictions)
filters:
ifeq ($(UNAME), Darwin)
	gcc -o filter/rastertopm110 filter/rastertopm110.c -lcups -lcupsimage
endif

# Filter installation (platform-specific)
install-filters:
	$(INSTALL_DIR) $(CUPS_FILTER_DIR)
ifeq ($(UNAME), Darwin)
	# macOS: Use compiled C filter (Python blocked by sandbox)
	$(INSTALL) -m 755 filter/rastertopm110 /usr/libexec/cups/filter/rastertopm110
else
	# Linux: Use Python filters
	$(INSTALL) -m 755 filter/rastertopm02_t02.py $(CUPS_FILTER_DIR)/rastertopm02_t02
	$(INSTALL) -m 755 filter/rastertopm110.py $(CUPS_FILTER_DIR)/rastertopm110
	$(INSTALL) -m 755 filter/rastertopd30.py $(CUPS_FILTER_DIR)/rastertopd30
endif

# Backend and Python modules installation
install-backend:
	$(INSTALL_DIR) $(CUPS_BACKEND_DIR)
	$(INSTALL_DIR) $(BLUETOOTH_DIR)
	$(INSTALL_DIR) $(USB_DIR)
	$(INSTALL) -m 755 backend/phomemo.py $(CUPS_BACKEND_DIR)/phomemo
	$(INSTALL) -m 644 backend/platform.py $(CUPS_BACKEND_DIR)/platform.py
	$(INSTALL) -m 644 backend/bluetooth/__init__.py $(BLUETOOTH_DIR)/__init__.py
	$(INSTALL) -m 644 backend/bluetooth/base.py $(BLUETOOTH_DIR)/base.py
	$(INSTALL) -m 644 backend/bluetooth/linux.py $(BLUETOOTH_DIR)/linux.py
	$(INSTALL) -m 644 backend/bluetooth/darwin.py $(BLUETOOTH_DIR)/darwin.py
	$(INSTALL) -m 644 backend/usb/__init__.py $(USB_DIR)/__init__.py
	$(INSTALL) -m 644 backend/usb/base.py $(USB_DIR)/base.py
	$(INSTALL) -m 644 backend/usb/linux.py $(USB_DIR)/linux.py
	$(INSTALL) -m 644 backend/usb/darwin.py $(USB_DIR)/darwin.py

# PPD files installation
install-ppds:
	$(INSTALL_DIR) $(CUPS_PPD_DIR)
	$(INSTALL) -m 644 ppd/Phomemo-M02.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-M02Pro.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-T02.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-D30.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-M110.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-M220.ppd $(CUPS_PPD_DIR)/
	$(INSTALL) -m 644 ppd/Phomemo-M421.ppd $(CUPS_PPD_DIR)/

# Linux-specific installation (includes DRV files)
install-linux: install-filters install-backend install-ppds
	$(INSTALL_DIR) $(CUPS_DRV_DIR)
	$(INSTALL) -m 644 drv/phomemo-m02_t02.drv $(CUPS_DRV_DIR)/
	$(INSTALL) -m 644 drv/phomemo-m02pro.drv $(CUPS_DRV_DIR)/
	$(INSTALL) -m 644 drv/phomemo-m110.drv $(CUPS_DRV_DIR)/
	$(INSTALL) -m 644 drv/phomemo-m220.drv $(CUPS_DRV_DIR)/
	$(INSTALL) -m 644 drv/phomemo-d30.drv $(CUPS_DRV_DIR)/
	$(INSTALL) -m 644 drv/phomemo-m421.drv $(CUPS_DRV_DIR)/

# macOS Bluetooth backend installation
install-bt-backend:
	$(INSTALL) -m 755 backend/phomemo-bt-socket /usr/libexec/cups/backend/phomemo-bt

# macOS-specific installation
install-darwin: install-filters install-ppds install-bt-backend
	@echo ""
	@echo "=== macOS Installation Complete ==="
	@echo ""
	@echo "The C filter has been installed to /usr/libexec/cups/filter/"
	@echo "The Bluetooth backend has been installed to /usr/libexec/cups/backend/"
	@echo ""
	@echo "For Bluetooth printing, also run:"
	@echo "    cd ../macos && ./install-bt-helper.sh"
	@echo ""
	@echo "Restart CUPS to apply changes:"
	@echo "    sudo launchctl stop org.cups.cupsd"
	@echo "    sudo launchctl start org.cups.cupsd"
	@echo ""

# Platform-aware install target
install:
ifeq ($(UNAME), Darwin)
	$(MAKE) install-darwin
else
	$(MAKE) install-linux
endif

clean:
	rm -f ppd/*.ppd.gz
	rm -f filter/rastertopm110
