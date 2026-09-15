#!/bin/bash
#
# Open Enhanced Dashboard in Chrome Fullscreen
#

URL="file:///home/matt/r510-command-center/enhanced-dashboard.html"

# Check if Chrome is already running with this URL
CHROME_PID=$(pgrep -f "chrome.*enhanced-dashboard")

if [ ! -z "$CHROME_PID" ]; then
    echo "Dashboard already open, refreshing..."
    ./refresh-chrome.sh
    exit 0
fi

echo "🚀 Opening Enhanced Camera Dashboard in fullscreen..."

# Kill any existing Chrome windows
pkill -f "chrome.*kiosk" || true
sleep 1

# Start Chrome in kiosk mode (fullscreen)
DISPLAY=:0 google-chrome \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-notifications \
    --disable-popup-blocking \
    "$URL" &

echo "✅ Dashboard opened in fullscreen"
echo "   Press Alt+F4 to close"
echo "   Or run: pkill -f 'chrome.*kiosk'"
