#!/bin/bash
#
# Fix Network Access for R510 Crime Camera Integration
#

echo "🔧 Fixing network accessibility..."

# Stop the conflicting Vite process
echo "Stopping conflicting Vite processes..."
pkill -f "vite.*gods-eye-view" || true
sleep 2

# Copy updated service file
echo "Updating systemd service..."
sudo cp /home/matt/r510-command-center/gods-eye-view.service /etc/systemd/system/
sudo systemctl daemon-reload

# Restart services
echo "Restarting services..."
sudo systemctl restart gods-eye-view.service
sudo systemctl restart crime-camera-bridge.service

echo "Waiting for services to start..."
sleep 5

# Check status
echo ""
echo "═══════════════════════════════════════════"
echo "Checking network bindings..."
echo "═══════════════════════════════════════════"
ss -tlnp | grep -E ":(4173|9000)"

echo ""
echo "═══════════════════════════════════════════"
echo "Service Status:"
echo "═══════════════════════════════════════════"
sudo systemctl status gods-eye-view.service --no-pager -l | head -15
echo ""
sudo systemctl status crime-camera-bridge.service --no-pager -l | head -15

echo ""
echo "═══════════════════════════════════════════"
echo "Testing URLs..."
echo "═══════════════════════════════════════════"

# Test locally
echo -n "Bridge (local): "
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/status
echo ""

echo -n "God's Eye View (local): "
curl -s -o /dev/null -w "%{http_code}" http://localhost:4173
echo ""

# Get the external IP
EXTERNAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "Your server IP: $EXTERNAL_IP"
echo ""
echo "✅ Access URLs:"
echo "   God's Eye View:     http://$EXTERNAL_IP:4173"
echo "   Crime-Camera Bridge: http://$EXTERNAL_IP:9000"
echo "   Bridge Status:      http://$EXTERNAL_IP:9000/status"
echo ""
echo "If you still can't access, check your firewall:"
echo "   sudo ufw allow 4173"
echo "   sudo ufw allow 9000"
echo ""
