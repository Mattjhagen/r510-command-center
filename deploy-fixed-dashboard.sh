#!/bin/bash
#
# Deploy Fixed R510 Dashboard
# Fixes panel layout and crash issues
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYING FIXED R510 DASHBOARD"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Configuration
DASHBOARD_DIR="/opt/r510-dashboard"
SERVICE_NAME="r510-dashboard"

# Copy new dashboard
echo "📁 Deploying fixed dashboard..."
cp index.html $DASHBOARD_DIR/
chmod 644 $DASHBOARD_DIR/index.html

# Restart service
echo "🔄 Restarting dashboard service..."
systemctl restart ${SERVICE_NAME}

# Check status
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "✅ Dashboard service restarted successfully"
    echo ""
    echo "Changes applied:"
    echo "  • Police scanner moved to right panel"
    echo "  • Active incident moved to center-bottom panel"
    echo "  • Added error handling to prevent crashes"
    echo ""
    echo "Dashboard URL: http://$(hostname -I | awk '{print $1}'):8421"
else
    echo "❌ Failed to restart dashboard service"
    systemctl status ${SERVICE_NAME}
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
