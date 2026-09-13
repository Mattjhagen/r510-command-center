#!/bin/bash
set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD - MANUAL SCANNER START"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo"
    exit 1
fi

echo "🔧 CHANGES:"
echo "  • Scanner auto-start DISABLED"
echo "  • Press PLAY button manually to start"
echo "  • More defensive error handling"
echo "  • Helps isolate crash cause"
echo ""

# Deploy to port 7072
WEB_DIR="/home/matt/r510-web"
echo "1️⃣  Deploying to port 7072..."

if [ -f "$WEB_DIR/r510.html" ]; then
    cp "$WEB_DIR/r510.html" "$WEB_DIR/r510.html.backup-manual-$(date +%Y%m%d-%H%M%S)"
    echo "   ✅ Backup created"
fi

cp /home/matt/r510-command-center/index.html "$WEB_DIR/r510.html"
cp /home/matt/r510-command-center/favicon.svg "$WEB_DIR/favicon.svg" 2>/dev/null || true
chown matt:matt "$WEB_DIR/r510.html" "$WEB_DIR/favicon.svg" 2>/dev/null || true
chmod 644 "$WEB_DIR/r510.html"
echo "   ✅ Deployed"

# Deploy to port 8421
DASHBOARD_DIR="/opt/r510-dashboard"
echo ""
echo "2️⃣  Deploying to port 8421..."

if [ -f "$DASHBOARD_DIR/index.html" ]; then
    cp "$DASHBOARD_DIR/index.html" "$DASHBOARD_DIR/index.html.backup-manual-$(date +%Y%m%d-%H%M%S)"
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
echo "   ✅ Services restarted"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Test at: http://192.168.0.169:7072"
echo ""
echo "⚠️  SCANNER AUTO-START IS DISABLED"
echo ""
echo "Testing steps:"
echo "  1. Page loads - right panel should show 'PRESS PLAY' message"
echo "  2. All other panels should work (map, flights, crime)"
echo "  3. Manually click PLAY button in scanner panel"
echo "  4. Transcripts should start appearing"
echo "  5. If it crashes on PLAY - we know the issue is in scanner code"
echo "  6. If it doesn't crash - we know the issue was timing/auto-start"
echo ""
