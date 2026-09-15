#!/bin/bash
#
# Open Camera Dashboard - Clean Start (No First-Run Dialogs)
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
CHROMIUM_EXE=$(readlink -f /proc/$CHROMIUM_PID/exe)

echo "🚀 Opening Enhanced Camera Dashboard..."

# Open with flags to skip all first-run stuff
DISPLAY=$DISPLAY_VAR XAUTHORITY=$XAUTHORITY_VAR \
    "$CHROMIUM_EXE" \
    --new-window \
    --no-sandbox \
    --no-first-run \
    --no-default-browser-check \
    --disable-default-apps \
    --disable-sync \
    --disable-translate \
    --disable-notifications \
    --disable-infobars \
    file:///home/matt/r510-command-center/enhanced-dashboard.html &

sleep 2

echo "✅ Camera dashboard should now be visible!"
echo ""
echo "What you should see:"
echo "  • Green Matrix-style interface"
echo "  • '🛰️ R510 ORBITAL COMMAND CENTER' header"
echo "  • Camera list on left side (109 cameras)"
echo "  • Large camera view in center"
echo ""
echo "If you still see your old dashboard, press Alt+Tab to switch windows"
