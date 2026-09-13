#!/bin/bash
#
# Restart Chrome Kiosk from SSH
# Run this to reload the dashboard on the R510 display
#

echo "🔄 Restarting Chrome kiosk on R510 display..."

# Kill existing Chrome
pkill -u matt chrome 2>/dev/null
sleep 2

# Start Chrome in kiosk mode on the local display
DISPLAY=:0 chromium-browser \
    --kiosk \
    --no-sandbox \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-features=TranslateUI \
    --autoplay-policy=no-user-gesture-required \
    --app=http://localhost:7072 \
    > /dev/null 2>&1 &

sleep 3

if pgrep -u matt chrome > /dev/null; then
    echo "✅ Chrome restarted successfully"
    echo "   Dashboard URL: http://localhost:7072"
    echo "   View on R510 display :0"
else
    echo "❌ Chrome failed to start"
    exit 1
fi
