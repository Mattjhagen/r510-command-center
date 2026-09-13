#!/bin/bash
#
# R510 Complete Dashboard Deployment
# Master script to deploy all components
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 COMMAND CENTER - COMPLETE DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Make all scripts executable
chmod +x *.sh

echo "This script will install and configure:"
echo "  1. R510 Dashboard Web UI (port 8421)"
echo "  2. Flightradar24 MCP Server (port 8000)"
echo "  3. dump1090 ADS-B Receiver (port 8080)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Step 1: Deploy dashboard
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  STEP 1: DEPLOYING DASHBOARD"
echo "═══════════════════════════════════════════════════════════"
./deploy-dashboard.sh

# Step 2: Setup FR24 MCP
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  STEP 2: SETTING UP FLIGHTRADAR24 MCP"
echo "═══════════════════════════════════════════════════════════"
read -p "Install FR24 MCP? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo -u $SUDO_USER ./setup-fr24-mcp.sh
fi

# Step 3: Setup dump1090
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  STEP 3: SETTING UP DUMP1090 ADS-B RECEIVER"
echo "═══════════════════════════════════════════════════════════"
read -p "Install dump1090? (Requires RTL-SDR) (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./setup-dump1090.sh
fi

# Step 4: Configure SpotCrime API
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  STEP 4: CONFIGURE SPOTCRIME API"
echo "═══════════════════════════════════════════════════════════"
read -p "Do you have a SpotCrime API key? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter SpotCrime API key: " SPOTCRIME_KEY
    mkdir -p /etc/systemd/system/r510-dashboard.service.d
    cat > /etc/systemd/system/r510-dashboard.service.d/override.conf <<EOF
[Service]
Environment="SPOTCRIME_API_KEY=$SPOTCRIME_KEY"
EOF
    systemctl daemon-reload
    systemctl restart r510-dashboard
    echo "✅ SpotCrime API key configured"
fi

# Display summary
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE - SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Services Status:"
systemctl is-active --quiet r510-dashboard && echo "  ✅ r510-dashboard" || echo "  ❌ r510-dashboard"
systemctl is-active --quiet fr24-mcp && echo "  ✅ fr24-mcp" || echo "  ⚠️  fr24-mcp (not installed)"
systemctl is-active --quiet dump1090 && echo "  ✅ dump1090" || echo "  ⚠️  dump1090 (not installed)"
echo ""

IP_ADDR=$(hostname -I | awk '{print $1}')
echo "Access Dashboard:"
echo "  http://${IP_ADDR}:8421"
echo "  http://localhost:8421"
echo ""

echo "Service Management:"
echo "  sudo systemctl status r510-dashboard"
echo "  sudo systemctl restart r510-dashboard"
echo "  sudo journalctl -u r510-dashboard -f"
echo ""

echo "Configuration Files:"
echo "  Dashboard: /opt/r510-dashboard/index.html"
echo "  Service: /etc/systemd/system/r510-dashboard.service"
echo ""

echo "Next Steps:"
echo "  1. Open dashboard in browser"
echo "  2. Verify flight data is loading"
echo "  3. Check crime data feed"
echo "  4. Monitor system logs"
echo ""
