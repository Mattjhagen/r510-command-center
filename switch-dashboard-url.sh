#!/bin/bash
#
# Switch the URL in the running Chromium browser
# This changes the page without restarting the browser
#

# Find the chromium window
CHROMIUM_PID=$(pgrep -f "chromium.*8421" | head -1)

if [ -z "$CHROMIUM_PID" ]; then
    echo "❌ No chromium process found running on port 8421"
    exit 1
fi

echo "Found chromium PID: $CHROMIUM_PID"

# Get the DISPLAY from the running process
DISPLAY_VAR=$(cat /proc/$CHROMIUM_PID/environ | tr '\0' '\n' | grep "^DISPLAY=" | cut -d= -f2)
echo "Using DISPLAY=$DISPLAY_VAR"

# Find the chromium window
WINDOW_ID=$(DISPLAY=$DISPLAY_VAR xdotool search --pid $CHROMIUM_PID | head -1)

if [ -z "$WINDOW_ID" ]; then
    echo "❌ Could not find chromium window"
    exit 1
fi

echo "Found window ID: $WINDOW_ID"

# Activate the window
DISPLAY=$DISPLAY_VAR xdotool windowactivate $WINDOW_ID
sleep 0.5

# Press Ctrl+L to focus address bar
DISPLAY=$DISPLAY_VAR xdotool key --window $WINDOW_ID ctrl+l
sleep 0.3

# Type the new URL
DISPLAY=$DISPLAY_VAR xdotool type --window $WINDOW_ID "file:///home/matt/r510-command-center/enhanced-dashboard.html"
sleep 0.3

# Press Enter
DISPLAY=$DISPLAY_VAR xdotool key --window $WINDOW_ID Return

echo "✅ Switched to Enhanced Camera Dashboard"
echo ""
echo "The URL has been changed in the existing browser window."
echo "Press F11 to toggle fullscreen if needed."
