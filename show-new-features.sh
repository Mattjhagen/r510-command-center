#!/bin/bash
#
# Show New Camera Features on R510 Monitor
#

echo "═══════════════════════════════════════════════════════"
echo "🎯 NEW FEATURES AVAILABLE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "You now have 3 ways to view live cameras with crimes:"
echo ""
echo "OPTION 1: Enhanced Camera Dashboard (Recommended)"
echo "──────────────────────────────────────────────────────"
echo "Full-screen camera viewer with crime correlation"
echo ""
echo "  DISPLAY=:0 chromium-browser --kiosk \\"
echo "    file:///home/matt/r510-command-center/enhanced-dashboard.html &"
echo ""
echo "Features:"
echo "  • 109 live cameras in sidebar"
echo "  • Large primary camera view"
echo "  • 4-camera grid at bottom"
echo "  • Matrix-style interface"
echo ""
echo ""
echo "OPTION 2: Add Widget to Your Existing Dashboard"
echo "──────────────────────────────────────────────────────"
echo "Keep your current dashboard at http://localhost:8421"
echo "Add crime-camera widget as iframe or side-by-side"
echo ""
echo "Side-by-side view:"
echo "  DISPLAY=:0 chromium-browser \\"
echo "    http://localhost:8421 \\"
echo "    file:///home/matt/r510-command-center/crime-cam-integration-widget.html &"
echo ""
echo ""
echo "OPTION 3: God's Eye View (3D Globe)"
echo "──────────────────────────────────────────────────────"
echo "3D Earth with camera markers and live feeds"
echo ""
echo "  DISPLAY=:0 chromium-browser --kiosk http://192.168.0.169:4173 &"
echo ""
echo "Features:"
echo "  • Photorealistic 3D globe"
echo "  • Click cameras to view feeds"
echo "  • Zoom/pan/rotate"
echo "  • Shows camera coverage cones"
echo ""
echo ""
echo "═══════════════════════════════════════════════════════"
echo "📹 HOW IT WORKS"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "1. Crime data in crime.json gets loaded by bridge API"
echo "2. For each crime, API finds nearest cameras (up to 1.5km)"
echo "3. Dashboard shows crimes with nearby camera feeds"
echo "4. Click incident → see cameras → view live feeds"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "🎮 QUICK START"
echo "═══════════════════════════════════════════════════════"
echo ""
read -p "Which would you like to try? (1=Enhanced, 2=Widget, 3=Globe, 0=Cancel): " choice
echo ""

case $choice in
    1)
        echo "🚀 Opening Enhanced Camera Dashboard..."
        pkill -f "chromium.*8421"
        sleep 1
        DISPLAY=:1 chromium-browser --kiosk \
            --no-sandbox \
            --disable-infobars \
            file:///home/matt/r510-command-center/enhanced-dashboard.html &
        echo "✅ Enhanced dashboard opened in fullscreen"
        echo "   Press Alt+F4 to close"
        ;;
    2)
        echo "🚀 Opening side-by-side view..."
        pkill -f "chromium.*8421"
        sleep 1
        DISPLAY=:1 chromium-browser \
            --no-sandbox \
            --new-window http://localhost:8421 \
            --new-window file:///home/matt/r510-command-center/crime-cam-integration-widget.html &
        echo "✅ Opened both dashboards"
        echo "   Your original dashboard + crime-camera widget"
        ;;
    3)
        echo "🚀 Opening God's Eye View..."
        pkill -f "chromium.*8421"
        sleep 1
        DISPLAY=:1 chromium-browser --kiosk \
            --no-sandbox \
            --disable-infobars \
            http://192.168.0.169:4173 &
        echo "✅ God's Eye View opened"
        echo "   Click camera markers to view feeds"
        ;;
    *)
        echo "Cancelled. Your original dashboard is still running."
        ;;
esac
echo ""
