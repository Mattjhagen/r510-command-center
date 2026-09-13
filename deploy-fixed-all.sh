#!/bin/bash
#
# Deploy Fixed Dashboard to ALL Locations
# Fixes panel crashes and reorganizes layout
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD - DEPLOY FIXED VERSION"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

echo "📦 Changes in this update:"
echo "  • Police scanner moved to RIGHT panel"
echo "  • Active incident moved to CENTER-BOTTOM panel"
echo "  • Added error handling to prevent crashes"
echo "  • Wrapped all functions in try-catch blocks"
echo ""

# Backup and deploy to port 8421 location
echo "1️⃣  Deploying to r510-dashboard (port 8421)..."
DASHBOARD_DIR="/opt/r510-dashboard"
if [ -f "$DASHBOARD_DIR/index.html" ]; then
    cp "$DASHBOARD_DIR/index.html" "$DASHBOARD_DIR/index.html.backup-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi
cp /home/matt/r510-command-center/index.html "$DASHBOARD_DIR/"
chmod 644 "$DASHBOARD_DIR/index.html"
echo "   ✅ Deployed to $DASHBOARD_DIR/index.html"
if [ -f /home/matt/r510-command-center/crime.json ]; then
    cp /home/matt/r510-command-center/crime.json "$DASHBOARD_DIR/crime.json"
    chmod 644 "$DASHBOARD_DIR/crime.json"
    echo "   ✅ crime.json deployed to $DASHBOARD_DIR/"
fi

# Backup and deploy to port 7072 location (where Chrome kiosk is pointed)
echo ""
echo "2️⃣  Deploying to r510-web (port 7072 - Chrome kiosk)..."
WEB_DIR="/home/matt/r510-web"
if [ -f "$WEB_DIR/r510.html" ]; then
    cp "$WEB_DIR/r510.html" "$WEB_DIR/r510.html.backup-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi
cp /home/matt/r510-command-center/index.html "$WEB_DIR/r510.html"
chown matt:matt "$WEB_DIR/r510.html"
chmod 644 "$WEB_DIR/r510.html"
echo "   ✅ Deployed to $WEB_DIR/r510.html"
if [ -f /home/matt/r510-command-center/crime.json ]; then
    cp /home/matt/r510-command-center/crime.json "$WEB_DIR/crime.json"
    chown matt:matt "$WEB_DIR/crime.json"
    chmod 644 "$WEB_DIR/crime.json"
    echo "   ✅ crime.json deployed to $WEB_DIR/"
fi

# Restart services
echo ""
echo "3️⃣  Restarting services..."
systemctl restart r510-dashboard
echo "   ✅ r510-dashboard restarted"
systemctl restart r510-web
echo "   ✅ r510-web restarted"

# Verify services
sleep 2
if systemctl is-active --quiet r510-dashboard && systemctl is-active --quiet r510-web; then
    echo "   ✅ All services running"
else
    echo "   ⚠️  Service status:"
    systemctl status r510-dashboard r510-web --no-pager | grep "Active:"
fi

# Restart Chrome kiosk to reload page
echo ""
echo "4️⃣  Restarting Chrome kiosk..."
CHROME_PID=$(pgrep -u matt chrome | head -1)
if [ ! -z "$CHROME_PID" ]; then
    echo "   Found Chrome (PID: $CHROME_PID)"
    su - matt -c "DISPLAY=:0 pkill chrome"
    sleep 2
    echo "   ✅ Chrome stopped"

    # Restart Chrome in kiosk mode
    su - matt -c "DISPLAY=:0 chromium-browser --kiosk --no-sandbox --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --app=http://localhost:7072 &"
    sleep 3
    echo "   ✅ Chrome restarted in kiosk mode"
else
    echo "   ℹ️  Chrome not running, skipping restart"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Dashboard URLs:"
echo "  • Port 7072 (Chrome kiosk): http://192.168.0.169:7072"
echo "  • Port 8421 (secondary):    http://192.168.0.169:8421"
echo ""
echo "Service status:"
systemctl is-active r510-dashboard && echo "  ✅ r510-dashboard: ACTIVE" || echo "  ❌ r510-dashboard: INACTIVE"
systemctl is-active r510-web && echo "  ✅ r510-web: ACTIVE" || echo "  ❌ r510-web: INACTIVE"
echo ""
echo "Autostart status (survives reboots):"
systemctl is-enabled r510-dashboard &>/dev/null && echo "  ✅ r510-dashboard: ENABLED" || echo "  ❌ r510-dashboard: DISABLED"
systemctl is-enabled r510-web &>/dev/null && echo "  ✅ r510-web: ENABLED" || echo "  ❌ r510-web: DISABLED"
echo ""
