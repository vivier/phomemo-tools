#!/bin/bash
#
# Install Phomemo Bluetooth helper for CUPS printing on macOS
#
# This installs:
# - The helper daemon (runs as user with Bluetooth permissions)
# - The CUPS backend (connects to helper via socket)
# - LaunchAgent to auto-start helper on login
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUPPORT_DIR="$HOME/Library/Application Support/Phomemo"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "Installing Phomemo Bluetooth helper..."

# Check for PyObjC
if ! python3 -c "import objc; from IOBluetooth import IOBluetoothDevice" 2>/dev/null; then
    echo "PyObjC is required. Installing..."
    pip3 install pyobjc-framework-IOBluetooth || {
        echo "Error: Could not install PyObjC. Please install manually:"
        echo "  pip3 install pyobjc-framework-IOBluetooth"
        exit 1
    }
fi

# Create directories
mkdir -p "$SUPPORT_DIR"
mkdir -p "$LAUNCH_AGENTS"

# Install helper daemon
echo "Installing helper daemon..."
cp "$SCRIPT_DIR/phomemo-bt-helper.py" "$SUPPORT_DIR/"
chmod 755 "$SUPPORT_DIR/phomemo-bt-helper.py"

# Find Python path with PyObjC
PYTHON_PATH=$(python3 -c "import sys; print(sys.executable)")
echo "Using Python: $PYTHON_PATH"

# Install LaunchAgent (with expanded paths)
echo "Installing LaunchAgent..."
cat > "$LAUNCH_AGENTS/com.phomemo.bt-helper.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.phomemo.bt-helper</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$SUPPORT_DIR/phomemo-bt-helper.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/phomemo-bt-helper.log</string>
    <key>StandardOutPath</key>
    <string>/tmp/phomemo-bt-helper.log</string>
</dict>
</plist>
EOF

# Install CUPS backend
echo "Installing CUPS backend..."
sudo cp "$SCRIPT_DIR/../cups/backend/phomemo-bt-socket" /usr/libexec/cups/backend/phomemo-bt
sudo chmod 755 /usr/libexec/cups/backend/phomemo-bt
sudo chown root:wheel /usr/libexec/cups/backend/phomemo-bt

# Stop existing helper if running
launchctl unload "$LAUNCH_AGENTS/com.phomemo.bt-helper.plist" 2>/dev/null || true

# Start helper
echo "Starting helper daemon..."
launchctl load "$LAUNCH_AGENTS/com.phomemo.bt-helper.plist"

# Wait for socket
sleep 2
if [ -S /tmp/phomemo-bt.sock ]; then
    echo "Helper is running!"
else
    echo "Warning: Helper socket not found. Check /tmp/phomemo-bt-helper.log"
fi

echo ""
echo "Installation complete!"
echo ""
echo "To add a Bluetooth printer:"
echo "  1. Pair the printer in System Settings > Bluetooth"
echo "  2. Open System Settings > Printers & Scanners"
echo "  3. Click '+' to add a printer"
echo "  4. Your Phomemo printer should appear with 'phomemo-bt://' URI"
echo ""
echo "If the printer doesn't appear, you may need to grant Bluetooth access:"
echo "  System Settings > Privacy & Security > Bluetooth"
echo "  Add 'Terminal' or the app running this helper"
