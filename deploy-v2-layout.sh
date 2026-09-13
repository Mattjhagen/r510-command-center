#!/bin/bash
#
# Deploy V2 Layout - New Design with Menu System
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD V2 - NEW LAYOUT DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

echo "📦 NEW FEATURES IN V2:"
echo "  • Police scanner: Right panel (full height)"
echo "  • Transcript text: DOUBLED in size (16px)"
echo "  • Transcript order: Newest at BOTTOM going UP"
echo "  • Threat Matrix: Moved to left panel top"
echo "  • Menu system: [T] Telemetry [L] Logs [J] Journal [ESC] Close"
echo "  • Enhanced error handling: Prevents module crashes"
echo "  • Favicon: Orbital command center icon"
echo ""

# Deploy to port 7072 (stable/Chrome kiosk location)
WEB_DIR="/home/matt/r510-web"
echo "1️⃣  Deploying to port 7072 (Chrome kiosk)..."

if [ -f "$WEB_DIR/r510.html" ]; then
    cp "$WEB_DIR/r510.html" "$WEB_DIR/r510.html.backup-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi

cp /home/matt/r510-command-center/index.html "$WEB_DIR/r510.html"
cp /home/matt/r510-command-center/favicon.svg "$WEB_DIR/favicon.svg" 2>/dev/null || echo "   ⚠️  No favicon found (optional)"
chown matt:matt "$WEB_DIR/r510.html" "$WEB_DIR/favicon.svg" 2>/dev/null || true
chmod 644 "$WEB_DIR/r510.html"
echo "   ✅ Deployed to $WEB_DIR/r510.html"

# Deploy to port 8421 (secondary location)
DASHBOARD_DIR="/opt/r510-dashboard"
echo ""
echo "2️⃣  Deploying to port 8421 (secondary)..."

if [ -f "$DASHBOARD_DIR/index.html" ]; then
    cp "$DASHBOARD_DIR/index.html" "$DASHBOARD_DIR/index.html.backup-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi

cp /home/matt/r510-command-center/index.html "$DASHBOARD_DIR/"
cp /home/matt/r510-command-center/favicon.svg "$DASHBOARD_DIR/favicon.svg" 2>/dev/null || true
chmod 644 "$DASHBOARD_DIR/index.html"
echo "   ✅ Deployed to $DASHBOARD_DIR/index.html"

# Restart services
echo ""
echo "3️⃣  Restarting services..."
systemctl restart r510-web
echo "   ✅ r510-web restarted"
systemctl restart r510-dashboard
echo "   ✅ r510-dashboard restarted"

# Verify services
sleep 2
echo ""
echo "4️⃣  Verifying services..."
if systemctl is-active --quiet r510-web && systemctl is-active --quiet r510-dashboard; then
    echo "   ✅ All services ACTIVE"
else
    echo "   ⚠️  Service check:"
    systemctl is-active r510-web && echo "      r510-web: OK" || echo "      r510-web: FAILED"
    systemctl is-active r510-dashboard && echo "      r510-dashboard: OK" || echo "      r510-dashboard: FAILED"
fi

# Optional: Restart Chrome
echo ""
read -p "Restart Chrome kiosk to load new version? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "5️⃣  Restarting Chrome..."
    su - matt -c "DISPLAY=:0 pkill chrome" 2>/dev/null || true
    sleep 2
    su - matt -c "DISPLAY=:0 chromium-browser --kiosk --no-sandbox --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --app=http://localhost:7072 &" 2>/dev/null &
    sleep 3
    echo "   ✅ Chrome restarted"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Dashboard URLs:"
echo "  • http://192.168.0.169:7072 (PRIMARY - Chrome kiosk)"
echo "  • http://192.168.0.169:8421 (SECONDARY)"
echo ""
echo "Keyboard shortcuts:"
echo "  • [T] - Show Telemetry"
echo "  • [L] - Show System Logs"
echo "  • [J] - Show Journal"
echo "  • [ESC] - Close modal"
echo ""
