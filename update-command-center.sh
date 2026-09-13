#!/bin/bash
#
# Update 'command-center' to launch web dashboard
#

echo "════════════════════════════════════════════════════════════"
echo "  UPDATING COMMAND-CENTER COMMAND"
echo "════════════════════════════════════════════════════════════"
echo ""

# Backup original command-center
echo "Backing up original command-center..."
if [ -f ~/.local/bin/command-center ]; then
    sudo cp ~/.local/bin/command-center ~/.local/bin/command-center.old
    echo "✅ Original backed up to ~/.local/bin/command-center.old"
else
    echo "⚠️  Original command-center not found at ~/.local/bin/"
fi
echo ""

# Create new command-center script
echo "Creating new command-center launcher..."
sudo tee ~/.local/bin/command-center > /dev/null <<'CMDEOF'
#!/bin/bash
#
# R510 Command Center - Web Dashboard Launcher
#

# Check if dashboard service is running
if ! systemctl is-active --quiet r510-dashboard; then
    echo "Starting dashboard service..."
    sudo systemctl start r510-dashboard
    sleep 2
fi

# Check if already running
if pgrep -f "chromium.*8421" > /dev/null; then
    echo "Dashboard already running"
    exit 0
fi

# Launch browser in kiosk mode
echo "Launching R510 Command Center Web Dashboard..."
DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8421 2>/dev/null &

echo "Dashboard launched on display :0"
echo "Access at: http://localhost:8421"
CMDEOF

sudo chmod +x ~/.local/bin/command-center

echo "✅ New command-center script created"
echo ""

# Test it
echo "Testing new command..."
which command-center
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  UPDATE COMPLETE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Now 'command-center' will launch the web dashboard!"
echo ""
echo "To use:"
echo "  command-center          # Launch web dashboard"
echo "  command-center.old      # Launch old curses dashboard"
echo ""
