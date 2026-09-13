#!/bin/bash
#
# Switch R510 Physical Terminal to Web Dashboard
# Replaces the old curses dashboard with the new web dashboard
#

set -e

echo "════════════════════════════════════════════════════════════"
echo "  SWITCH R510 TO WEB DASHBOARD"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if running as regular user
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run as regular user (not sudo)"
    echo "   Run: ./switch-to-web-dashboard.sh"
    exit 1
fi

# Step 1: Install Chromium
echo "Step 1: Installing Chromium browser..."
sudo apt update -qq
sudo apt install -y chromium-browser

if ! command -v chromium-browser &> /dev/null; then
    echo "❌ Chromium installation failed"
    exit 1
fi
echo "✅ Chromium installed"
echo ""

# Step 2: Backup bashrc
echo "Step 2: Backing up ~/.bashrc..."
cp ~/.bashrc ~/.bashrc.backup-$(date +%Y%m%d-%H%M%S)
echo "✅ Backup created"
echo ""

# Step 3: Update bashrc
echo "Step 3: Updating ~/.bashrc autostart..."

# Remove old autostart block if it exists
sed -i '/# BEGIN r510-command-center TTY1 autostart/,/# END r510-command-center TTY1 autostart/d' ~/.bashrc

# Add new web dashboard autostart
cat >> ~/.bashrc <<'BASHRC_EOF'
# BEGIN r510-web-dashboard TTY1 autostart
if [[ $- == *i* ]] \
  && [[ "$(tty)" == "/dev/tty1" ]] \
  && [[ -z "${SSH_CONNECTION:-}" ]] \
  && [[ -n "${TERM:-}" ]] \
  && [[ -z "${R510_DASHBOARD_RUNNING:-}" ]]; then
  export R510_DASHBOARD_RUNNING=1
  # Wait for dashboard service to be ready
  for i in {1..10}; do
    if curl -s http://localhost:8421 > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  # Launch web dashboard in fullscreen
  DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8421 2>/dev/null &
fi
# END r510-web-dashboard TTY1 autostart
BASHRC_EOF

echo "✅ ~/.bashrc updated"
echo ""

# Step 4: Kill old dashboard if running
echo "Step 4: Checking for old dashboard..."
if pgrep -f "command_center" > /dev/null; then
    echo "Found old dashboard running"
    read -p "Kill old dashboard now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "command_center" || true
        echo "✅ Old dashboard stopped"
    fi
else
    echo "No old dashboard running"
fi
echo ""

# Step 5: Launch web dashboard now
echo "Step 5: Launching web dashboard..."
read -p "Launch web dashboard on monitor now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if dashboard service is running
    if ! curl -s http://localhost:8421 > /dev/null 2>&1; then
        echo "⚠️  Dashboard service not responding on port 8421"
        echo "   Starting service..."
        sudo systemctl start r510-dashboard
        sleep 2
    fi
    
    # Launch browser
    echo "Launching browser in fullscreen..."
    DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8421 &
    sleep 2
    echo "✅ Web dashboard launched!"
else
    echo "Skipped launch"
fi
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "What changed:"
echo "  ✅ Chromium browser installed"
echo "  ✅ ~/.bashrc updated for TTY1 autostart"
echo "  ✅ Old curses dashboard replaced"
echo ""
echo "Next boot:"
echo "  • On TTY1 (physical terminal): Web dashboard auto-launches"
echo "  • On SSH: Normal shell prompt"
echo ""
echo "Manual commands:"
echo "  • Launch now:  DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8421 &"
echo "  • Stop:        pkill chromium"
echo "  • Old curses:  command-center"
echo ""
echo "To revert to old dashboard:"
echo "  cp ~/.bashrc.backup-* ~/.bashrc"
echo ""
echo "Dashboard URL: http://localhost:8421"
echo "════════════════════════════════════════════════════════════"
