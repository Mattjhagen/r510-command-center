#!/bin/bash
#
# Open Camera Dashboard in New Chromium Window
# This works alongside your existing dashboard
#

# Get environment from running chromium
CHROMIUM_PID=$(pgrep -f "chromium.*8421" | head -1)

if [ -z "$CHROMIUM_PID" ]; then
    echo "❌ No chromium process found"
    exit 1
fi

# Extract environment
DISPLAY_VAR=$(cat /proc/$CHROMIUM_PID/environ | tr '\0' '\n' | grep "^DISPLAY=" | cut -d= -f2)
XAUTHORITY_VAR=$(cat /proc/$CHROMIUM_PID/environ | tr '\0' '\n' | grep "^XAUTHORITY=" | cut -d= -f2)

echo "🚀 Opening Enhanced Camera Dashboard in new window..."
echo "   (Your original dashboard will stay open too)"

# Get chromium executable path from running process
CHROMIUM_EXE=$(readlink -f /proc/$CHROMIUM_PID/exe)

# Open in new window using same executable
DISPLAY=$DISPLAY_VAR XAUTHORITY=$XAUTHORITY_VAR \
    "$CHROMIUM_EXE" \
    --new-window \
    --no-sandbox \
    file:///home/matt/r510-command-center/enhanced-dashboard.html &

echo "✅ New window opening..."
echo ""
echo "You should now see TWO chromium windows on your R510 monitor:"
echo "  1. Original dashboard (localhost:8421)"
echo "  2. Enhanced Camera Dashboard (new window)"
echo ""
echo "Use Alt+Tab to switch between them"
echo "Or close one with Alt+F4"
