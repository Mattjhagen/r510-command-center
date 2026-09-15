# Chrome Control from SSH Terminal on R510

Quick reference for controlling Chrome browser on R510 from SSH.

## Prerequisites

```bash
# Install xdotool if not already installed
sudo apt install xdotool
```

## Basic Commands

### Refresh Chrome
```bash
cd /home/matt/r510-command-center
./refresh-chrome.sh
```

Or manually:
```bash
# Find Chrome window
CHROME_WINDOW=$(xdotool search --class "chrome" | head -1)

# Send F5 to refresh
DISPLAY=:0 xdotool key --window $CHROME_WINDOW F5
```

### Open URL in Chrome
```bash
DISPLAY=:0 google-chrome "http://192.168.0.169:8421/" &
```

### Open in Fullscreen/Kiosk Mode
```bash
DISPLAY=:0 google-chrome --kiosk "http://192.168.0.169:8421/" &
```

### Open Enhanced Dashboard
```bash
cd /home/matt/r510-command-center
./open-dashboard-fullscreen.sh
```

## Advanced Chrome Control

### Close Chrome
```bash
pkill chrome
# Or kill specific window:
CHROME_WINDOW=$(xdotool search --class "chrome" | head -1)
DISPLAY=:0 xdotool windowkill $CHROME_WINDOW
```

### Close Fullscreen/Kiosk Chrome
```bash
pkill -f "chrome.*kiosk"
```

### Switch Tabs
```bash
# Next tab
DISPLAY=:0 xdotool key ctrl+Tab

# Previous tab
DISPLAY=:0 xdotool key ctrl+shift+Tab

# Close tab
DISPLAY=:0 xdotool key ctrl+w
```

### Zoom In/Out
```bash
# Zoom in
DISPLAY=:0 xdotool key ctrl+plus

# Zoom out
DISPLAY=:0 xdotool key ctrl+minus

# Reset zoom
DISPLAY=:0 xdotool key ctrl+0
```

### Navigate
```bash
# Back
DISPLAY=:0 xdotool key alt+Left

# Forward
DISPLAY=:0 xdotool key alt+Right

# Home
DISPLAY=:0 xdotool key alt+Home
```

### Enter Full Screen
```bash
DISPLAY=:0 xdotool key F11
```

### Exit Full Screen
```bash
DISPLAY=:0 xdotool key F11
# Or
DISPLAY=:0 xdotool key Escape
```

## Launch URLs with Options

### With Cache Disabled
```bash
DISPLAY=:0 google-chrome \
    --disable-cache \
    "http://192.168.0.169:8421/" &
```

### With DevTools Open
```bash
DISPLAY=:0 google-chrome \
    --auto-open-devtools-for-tabs \
    "http://192.168.0.169:8421/" &
```

### Incognito Mode
```bash
DISPLAY=:0 google-chrome \
    --incognito \
    "http://192.168.0.169:8421/" &
```

### Multiple URLs in Tabs
```bash
DISPLAY=:0 google-chrome \
    "http://192.168.0.169:8421/" \
    "http://100.103.3.35:4173" \
    "file:///home/matt/r510-command-center/enhanced-dashboard.html" &
```

## Auto-Refresh Setup

### Create Auto-Refresh Script
```bash
cat > /home/matt/r510-command-center/auto-refresh-chrome.sh << 'EOF'
#!/bin/bash
while true; do
    sleep 30  # Refresh every 30 seconds
    CHROME_WINDOW=$(xdotool search --class "chrome" | head -1)
    if [ ! -z "$CHROME_WINDOW" ]; then
        DISPLAY=:0 xdotool key --window $CHROME_WINDOW F5
        echo "Refreshed at $(date)"
    fi
done
EOF
chmod +x /home/matt/r510-command-center/auto-refresh-chrome.sh
```

### Run in Background
```bash
nohup ./auto-refresh-chrome.sh > /dev/null 2>&1 &
```

### Stop Auto-Refresh
```bash
pkill -f "auto-refresh-chrome"
```

## Remote Control via SSH

### From Another Machine
```bash
# SSH into R510
ssh matt@100.103.3.35

# Refresh Chrome on R510's display
DISPLAY=:0 xdotool search --class "chrome" | head -1 | xargs -I {} xdotool key --window {} F5
```

### One-Liner Refresh via SSH
```bash
ssh matt@100.103.3.35 'DISPLAY=:0 xdotool search --class "chrome" | head -1 | xargs -I {} xdotool key --window {} F5'
```

## Integration Examples

### Refresh When File Changes
```bash
# Watch crime.json and refresh Chrome when it changes
while true; do
    inotifywait -e modify /home/matt/r510-command-center/crime.json
    ./refresh-chrome.sh
done
```

### Refresh on Service Restart
Add to systemd service:
```ini
[Service]
ExecStartPost=/home/matt/r510-command-center/refresh-chrome.sh
```

### Scheduled Refresh via Cron
```bash
# Edit crontab
crontab -e

# Add line to refresh every 5 minutes
*/5 * * * * DISPLAY=:0 xdotool search --class "chrome" | head -1 | xargs -I {} xdotool key --window {} F5
```

## Troubleshooting

### Chrome Not Found
```bash
# Check if Chrome is running
ps aux | grep chrome

# List all windows
DISPLAY=:0 xdotool search --class ""
```

### Display Not Found
```bash
# Check DISPLAY variable
echo $DISPLAY

# List displays
ls /tmp/.X11-unix/
```

### Permission Issues
```bash
# Add user to video group
sudo usermod -aG video matt

# Allow X access
xhost +local:
```

## Quick Reference Card

```bash
# Refresh Chrome
./refresh-chrome.sh

# Open Enhanced Dashboard Fullscreen
./open-dashboard-fullscreen.sh

# Close Fullscreen Chrome
pkill -f "chrome.*kiosk"

# Open URL
DISPLAY=:0 google-chrome "http://URL" &

# Send Key to Chrome
CHROME_WIN=$(xdotool search --class "chrome" | head -1)
DISPLAY=:0 xdotool key --window $CHROME_WIN KEY

# Common Keys:
# F5 = Refresh
# F11 = Fullscreen
# ctrl+t = New tab
# ctrl+w = Close tab
# ctrl+Tab = Next tab
```

## External App Integration

To integrate with http://192.168.0.169:8421/:

```bash
# View integration options
./integrate-with-external-app.sh

# Open both side-by-side
DISPLAY=:0 google-chrome \
    "http://192.168.0.169:8421/" \
    "file:///home/matt/r510-command-center/crime-cam-integration-widget.html" &
```
