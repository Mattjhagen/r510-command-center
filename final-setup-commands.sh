#!/bin/bash
#
# Final Setup Commands - Run these to complete installation
#

echo "═══════════════════════════════════════════════════════"
echo "Final Setup for R510 Crime Camera Integration"
echo "═══════════════════════════════════════════════════════"
echo ""

# Update systemd service
echo "1️⃣  Updating systemd service..."
sudo cp /home/matt/r510-command-center/gods-eye-view.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart gods-eye-view.service
echo "✅ Service updated"
echo ""

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 5

# Check port binding
echo "2️⃣  Checking network binding..."
ss -tlnp | grep 4173
echo ""

# Test URLs
echo "3️⃣  Testing URLs..."
echo -n "   God's Eye View: "
curl -s -o /dev/null -w "%{http_code}" http://192.168.0.169:4173
echo ""

echo -n "   Bridge API: "
curl -s -o /dev/null -w "%{http_code}" http://192.168.0.169:9000/status
echo ""
echo ""

# Get IP address
IP=$(hostname -I | awk '{print $1}')

echo "═══════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETE!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "🌐 Access URLs (use these in your browser):"
echo "   God's Eye View:     http://$IP:4173"
echo "   Bridge API Status:  http://$IP:9000/status"
echo "   Enhanced Dashboard: file:///home/matt/r510-command-center/enhanced-dashboard.html"
echo ""
echo "📹 To open camera dashboard on R510's display:"
echo "   ./open-dashboard-fullscreen.sh"
echo ""
echo "🔄 To refresh browser on R510's display:"
echo "   ./refresh-chrome.sh"
echo ""
echo "📖 Documentation:"
echo "   cat QUICKSTART_CRIME_CAMERAS.md"
echo ""
