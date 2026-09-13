#!/bin/bash
#
# Flightradar24 MCP Server Setup Script
# Sets up FR24 API MCP server for R510 dashboard
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  FLIGHTRADAR24 MCP SERVER SETUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"
echo ""

# Install FR24 MCP globally
echo "📦 Installing @flightradar24/fr24api-mcp..."
sudo npm install -g @flightradar24/fr24api-mcp

# Create MCP configuration directory
echo "📁 Creating MCP configuration..."
mkdir -p ~/.config/fr24-mcp

# Create MCP configuration file
cat > ~/.config/fr24-mcp/config.json <<EOF
{
  "port": 8000,
  "host": "localhost",
  "bounds": {
    "north": 43.5,
    "south": 40.0,
    "west": -97.5,
    "east": -94.5
  },
  "updateInterval": 3000
}
EOF

# Create systemd service
if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
    echo "⚙️  Creating systemd service..."

    sudo tee /etc/systemd/system/fr24-mcp.service > /dev/null <<EOF
[Unit]
Description=Flightradar24 MCP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
ExecStart=/usr/bin/npx @flightradar24/fr24api-mcp --port 8000
Restart=always
RestartSec=10
Environment="NODE_ENV=production"

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable fr24-mcp
    sudo systemctl start fr24-mcp

    sleep 2
    if sudo systemctl is-active --quiet fr24-mcp; then
        echo "✅ FR24 MCP service is running"
    else
        echo "⚠️  FR24 MCP service failed to start"
        sudo systemctl status fr24-mcp
    fi
else
    echo "⚠️  Not running as root - skipping systemd service creation"
    echo "To start manually: npx @flightradar24/fr24api-mcp --port 8000"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  FR24 MCP SETUP COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "MCP Server: http://localhost:8000"
echo "Test endpoint: curl http://localhost:8000/health"
echo ""
