#!/bin/bash
#
# Deploy CRASH-PROOF Dashboard
# Fixes police scanner panel crash
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD - CRASH-PROOF DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo"
    exit 1
fi

echo "🛡️  CRASH-PROOF IMPROVEMENTS:"
echo "  • Police scanner: Fixed interval management"
echo "  • Proper cleanup when paused/restarted"
echo "  • Safe DOM access with validation"
echo "  • No duplicate intervals"
echo "  • Global toggle function"
echo "  • Auto-start delayed to 5 seconds"
echo "  • Transcript text: DOUBLE SIZE (16px)"
echo "  • Newest at BOTTOM, auto-scrolls"
echo ""

# Deploy to port 7072 (stable Chrome kiosk)
WEB_DIR="/home/matt/r510-web"
echo "1️⃣  Deploying to port 7072..."

if [ -f "$WEB_DIR/r510.html" ]; then
    cp "$WEB_DIR/r510.html" "$WEB_DIR/r510.html.backup-crashfix-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi

cp /home/matt/r510-command-center/index.html "$WEB_DIR/r510.html"
cp /home/matt/r510-command-center/favicon.svg "$WEB_DIR/favicon.svg" 2>/dev/null || true
chown matt:matt "$WEB_DIR/r510.html" "$WEB_DIR/favicon.svg" 2>/dev/null || true
chmod 644 "$WEB_DIR/r510.html"
echo "   ✅ Deployed"

# Deploy to port 8421 (secondary)
DASHBOARD_DIR="/opt/r510-dashboard"
echo ""
echo "2️⃣  Deploying to port 8421..."

if [ -f "$DASHBOARD_DIR/index.html" ]; then
    cp "$DASHBOARD_DIR/index.html" "$DASHBOARD_DIR/index.html.backup-crashfix-$(date +%Y%m%d-%H%M%S)"
fi

cp /home/matt/r510-command-center/index.html "$DASHBOARD_DIR/"
cp /home/matt/r510-command-center/favicon.svg "$DASHBOARD_DIR/favicon.svg" 2>/dev/null || true
chmod 644 "$DASHBOARD_DIR/index.html"
echo "   ✅ Deployed"

# Restart services
echo ""
echo "3️⃣  Restarting services..."
systemctl restart r510-web r510-dashboard
sleep 2

if systemctl is-active --quiet r510-web && systemctl is-active --quiet r510-dashboard; then
    echo "   ✅ Services ACTIVE"
else
    echo "   ⚠️  Service check:"
    systemctl is-active r510-web && echo "      r510-web: OK" || echo "      r510-web: FAILED"
    systemctl is-active r510-dashboard && echo "      r510-dashboard: OK" || echo "      r510-dashboard: FAILED"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Test at: http://192.168.0.169:7072"
echo ""
echo "Testing checklist:"
echo "  1. Page loads without errors"
echo "  2. Scanner auto-starts after 5 seconds"
echo "  3. Transcripts appear at bottom"
echo "  4. Transcripts are DOUBLE SIZE (readable)"
echo "  5. Refresh page 5+ times - NO CRASHES"
echo "  6. Press PAUSE then PLAY - works correctly"
echo "  7. Keyboard shortcuts work (T, L, J, ESC)"
echo ""
echo "To restart Chrome kiosk:"
echo "  sudo pkill chrome"
echo "  sudo -u matt DISPLAY=:0 chromium-browser --kiosk --no-sandbox --app=http://localhost:7072 &"
echo ""
