#!/bin/bash
#
# Refresh Chrome Browser on R510 from SSH Terminal
#

# Get the Chrome window ID
CHROME_WINDOW=$(xdotool search --class "chrome" | head -1)

if [ -z "$CHROME_WINDOW" ]; then
    echo "❌ Chrome window not found"
    echo "Starting Chrome..."
    DISPLAY=:0 google-chrome --start-fullscreen http://192.168.0.169:8421/ &
    sleep 3
    exit 0
fi

echo "🔄 Refreshing Chrome (Window ID: $CHROME_WINDOW)"

# Activate Chrome window
DISPLAY=:0 xdotool windowactivate $CHROME_WINDOW

# Send F5 (refresh)
DISPLAY=:0 xdotool key --window $CHROME_WINDOW F5

echo "✅ Chrome refreshed"
