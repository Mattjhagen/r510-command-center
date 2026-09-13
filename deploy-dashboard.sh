#!/bin/bash
#
# R510 Command Center Dashboard Deployment Script
# Deploys the web dashboard to R510 server
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  R510 COMMAND CENTER DASHBOARD DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Configuration
DASHBOARD_DIR="/opt/r510-dashboard"
DASHBOARD_PORT=8421
SERVICE_NAME="r510-dashboard"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Create dashboard directory
echo "📁 Creating dashboard directory..."
mkdir -p $DASHBOARD_DIR
cp index.html $DASHBOARD_DIR/
chmod 644 $DASHBOARD_DIR/index.html

# Create systemd service for HTTP server
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=R510 Command Center Dashboard
After=network.target ollama.service

[Service]
Type=simple
User=www-data
WorkingDirectory=$DASHBOARD_DIR
ExecStart=/usr/bin/python3 -m http.server $DASHBOARD_PORT
Restart=always
RestartSec=10
Environment="SPOTCRIME_API_KEY="

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable and start service
echo "🚀 Starting dashboard service..."
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

# Check status
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "✅ Dashboard service is running"
    echo ""
    echo "Dashboard URL: http://$(hostname -I | awk '{print $1}'):${DASHBOARD_PORT}"
    echo ""
else
    echo "❌ Failed to start dashboard service"
    systemctl status ${SERVICE_NAME}
    exit 1
fi

# Configure firewall if ufw is active
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    echo "🔥 Configuring firewall..."
    ufw allow ${DASHBOARD_PORT}/tcp
    echo "✅ Firewall rule added for port ${DASHBOARD_PORT}"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Set SpotCrime API key:"
echo "     sudo systemctl edit ${SERVICE_NAME}"
echo "     Add: Environment=\"SPOTCRIME_API_KEY=your_key_here\""
echo ""
echo "  2. Install Flightradar24 MCP (optional):"
echo "     npm install -g @flightradar24/fr24api-mcp"
echo ""
echo "  3. Configure dump1090 endpoint in index.html if needed"
echo ""
echo "Access the dashboard at:"
echo "  http://$(hostname -I | awk '{print $1}'):${DASHBOARD_PORT}"
echo ""
