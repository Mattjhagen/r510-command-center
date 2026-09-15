#!/bin/bash
#
# Simple Script to Switch to Camera Dashboard
#

# Get the environment from the running chromium process
CHROMIUM_PID=$(pgrep -f "chromium.*8421" | head -1)

if [ -z "$CHROMIUM_PID" ]; then
    echo "❌ No chromium process found. Is your dashboard running?"
    exit 1
fi

echo "Found chromium PID: $CHROMIUM_PID"

# Extract environment variables
DISPLAY_VAR=$(cat /proc/$CHROMIUM_PID/environ | tr '\0' '\n' | grep "^DISPLAY=" | cut -d= -f2)
XAUTHORITY_VAR=$(cat /proc/$CHROMIUM_PID/environ | tr '\0' '\n' | grep "^XAUTHORITY=" | cut -d= -f2)

echo "Using DISPLAY=$DISPLAY_VAR"
echo "Using XAUTHORITY=$XAUTHORITY_VAR"

# Kill old chromium
echo "Stopping old dashboard..."
kill $CHROMIUM_PID
sleep 2

# Launch new dashboard with same environment
echo "Starting Enhanced Camera Dashboard..."
DISPLAY=$DISPLAY_VAR XAUTHORITY=$XAUTHORITY_VAR chromium-browser --kiosk \
    --no-sandbox \
    --disable-infobars \
    --no-first-run \
    --disable-notifications \
    file:///home/matt/r510-command-center/enhanced-dashboard.html &

echo "✅ Camera dashboard should now be visible on your R510 monitor"
echo ""
echo "To go back to your original dashboard:"
echo "  pkill chromium"
echo "  DISPLAY=$DISPLAY_VAR XAUTHORITY=$XAUTHORITY_VAR chromium-browser --kiosk http://localhost:8421 &"
