#!/bin/bash
#
# Refresh Chrome/Chromium Browser on R510 from SSH Terminal
#

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
else
    echo "❌ No browser found (tried: google-chrome, chromium-browser, chromium)"
    exit 1
fi

# Get the browser window ID
CHROME_WINDOW=$(DISPLAY=$XDISPLAY xdotool search --class "chrom" 2>/dev/null | head -1)

if [ -z "$CHROME_WINDOW" ]; then
    echo "❌ Browser window not found"
    echo "Starting $BROWSER..."
    DISPLAY=$XDISPLAY $BROWSER --start-fullscreen http://192.168.0.169:8421/ &
    sleep 3
    exit 0
fi

echo "🔄 Refreshing Browser (Window ID: $CHROME_WINDOW on $XDISPLAY)"

# Activate Chrome window
DISPLAY=$XDISPLAY xdotool windowactivate $CHROME_WINDOW

# Send F5 (refresh)
DISPLAY=$XDISPLAY xdotool key --window $CHROME_WINDOW F5

echo "✅ Browser refreshed"
