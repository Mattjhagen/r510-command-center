#!/bin/bash
#
# Open Enhanced Dashboard in Browser Fullscreen
#

URL="file:///home/matt/r510-command-center/enhanced-dashboard.html"

# Find the X display
XDISPLAY=":1"
if [ ! -S /tmp/.X11-unix/X1 ]; then
    XDISPLAY=":0"
fi

# Find available browser
if command -v google-chrome &> /dev/null; then
    BROWSER="google-chrome"
elif command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
elif command -v chromium &> /dev/null; then
    BROWSER="chromium"
elif command -v firefox &> /dev/null; then
    BROWSER="firefox"
else
    echo "❌ No browser found"
    exit 1
fi

# Check if browser is already running with this URL
BROWSER_PID=$(pgrep -f "enhanced-dashboard")

if [ ! -z "$BROWSER_PID" ]; then
    echo "Dashboard already open, refreshing..."
    ./refresh-chrome.sh
    exit 0
fi

echo "🚀 Opening Enhanced Camera Dashboard in fullscreen..."
echo "Using browser: $BROWSER on $XDISPLAY"

# Kill any existing kiosk windows
pkill -f "kiosk" || true
sleep 1

# Start browser in kiosk mode (fullscreen)
DISPLAY=$XDISPLAY $BROWSER \
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
