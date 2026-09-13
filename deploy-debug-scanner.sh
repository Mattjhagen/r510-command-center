#!/bin/bash
set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD - DEBUG SCANNER VERSION"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo"
    exit 1
fi

echo "🐛 DEBUG IMPROVEMENTS:"
echo "  • Uses innerHTML instead of DOM manipulation"
echo "  • Transcript buffer at module level"
echo "  • Extensive console.log statements"
echo "  • Every step logged with timestamps"
echo "  • Will show EXACTLY where it crashes"
echo ""

# Deploy to port 7072
WEB_DIR="/home/matt/r510-web"
echo "1️⃣  Deploying to port 7072..."

if [ -f "$WEB_DIR/r510.html" ]; then
    cp "$WEB_DIR/r510.html" "$WEB_DIR/r510.html.backup-debug-$(date +%Y%m%d-%H%M%S)"
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
    cp "$DASHBOARD_DIR/index.html" "$DASHBOARD_DIR/index.html.backup-debug-$(date +%Y%m%d-%H%M%S)"
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
echo "🐛 DEBUGGING INSTRUCTIONS:"
echo ""
echo "1. Open browser developer console (F12)"
echo "2. Go to Console tab"
echo "3. Click PLAY button in scanner panel"
echo "4. Watch console output - you'll see:"
echo "   - 'toggleScanner() called'"
echo "   - 'Elements found: ...'"
echo "   - 'About to call startTranscription()...'"
echo "   - 'startTranscription() called'"
echo "   - 'Adding first transcript...'"
echo "   - etc."
echo ""
echo "5. THE LAST MESSAGE BEFORE IT CRASHES is where the problem is!"
echo ""
echo "6. Take a screenshot or copy the console output"
echo ""
