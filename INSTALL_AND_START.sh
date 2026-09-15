#!/bin/bash
#
# R510 Crime Camera Integration - One-Step Install and Start
#

echo "╔════════════════════════════════════════════════════════╗"
echo "║   R510 Crime Camera Integration - Installation         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "❌ Don't run this script as root. Run without sudo."
   echo "   The script will ask for sudo when needed."
   exit 1
fi

cd /home/matt/r510-command-center

echo "📦 Step 1: Installing Python dependencies..."
pip3 install aiohttp
echo "✅ Python dependencies installed"
echo ""

echo "📦 Step 2: Installing Node.js dependencies (this may take a few minutes)..."
cd gods-eye-view
npm install
cd ..
echo "✅ Node.js dependencies installed"
echo ""

echo "🔧 Step 3: Installing systemd services (requires sudo)..."
sudo ./install-systemd-services.sh

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ INSTALLATION COMPLETE!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "🌐 Access URLs:"
echo "   God's Eye View:     http://r510:4173"
echo "   Bridge API:         http://r510:9000"
echo "   Dashboard:          file:///home/matt/r510-command-center/crime-camera-dashboard.html"
echo ""
echo "📖 Documentation:"
echo "   Quick Start:        cat QUICKSTART_CRIME_CAMERAS.md"
echo "   Full Docs:          cat CRIME_CAMERA_INTEGRATION.md"
echo "   Service Management: cat SYSTEMD_SETUP.md"
echo ""
echo "🎮 Quick Commands:"
echo "   Start services:     sudo systemctl start r510-crime-camera.target"
echo "   Stop services:      sudo systemctl stop r510-crime-camera.target"
echo "   Check status:       sudo systemctl status r510-crime-camera.target"
echo "   View logs:          sudo journalctl -u crime-camera-bridge -u gods-eye-view -f"
echo ""
echo "✨ Services are now running and will auto-start on boot!"
echo ""
