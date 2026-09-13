# R510 Command Center Dashboard - Deployment Guide

## Quick Deploy

### One-Command Deployment (R510 Server)

```bash
sudo ./r510-deploy-all.sh
```

This master script will:
1. Deploy the dashboard web UI on port 8421
2. Install and configure Flightradar24 MCP server
3. Install and configure dump1090 ADS-B receiver
4. Configure all systemd services
5. Set up firewall rules

---

## Manual Step-by-Step Deployment

### 1. Deploy Dashboard

```bash
sudo ./deploy-dashboard.sh
```

**What it does:**
- Copies `index.html` to `/opt/r510-dashboard/`
- Creates systemd service on port 8421
- Configures firewall rules
- Starts the dashboard service

**Access:** `http://YOUR_R510_IP:8421`

### 2. Install Flightradar24 MCP (Optional)

```bash
./setup-fr24-mcp.sh
```

**What it does:**
- Installs Node.js if needed
- Installs `@flightradar24/fr24api-mcp` globally
- Creates systemd service on port 8000
- Configures for Omaha airspace bounds

**Test:** `curl http://localhost:8000/health`

### 3. Install dump1090 ADS-B Receiver (Optional)

**Requirements:** RTL-SDR USB dongle

```bash
sudo ./setup-dump1090.sh
```

**What it does:**
- Installs RTL-SDR drivers
- Builds dump1090 from source
- Creates systemd service on port 8080
- Blacklists conflicting DVB-T drivers

**Test:** `curl http://localhost:8080/data/aircraft.json`

### 4. Configure SpotCrime API

Edit the systemd service to add your API key:

```bash
sudo systemctl edit r510-dashboard
```

Add:
```ini
[Service]
Environment="SPOTCRIME_API_KEY=your_key_here"
```

Restart:
```bash
sudo systemctl restart r510-dashboard
```

---

## Service Management

### Dashboard Service

```bash
# Status
sudo systemctl status r510-dashboard

# Start/Stop/Restart
sudo systemctl start r510-dashboard
sudo systemctl stop r510-dashboard
sudo systemctl restart r510-dashboard

# View logs
sudo journalctl -u r510-dashboard -f

# Enable/Disable autostart
sudo systemctl enable r510-dashboard
sudo systemctl disable r510-dashboard
```

### FR24 MCP Service

```bash
sudo systemctl status fr24-mcp
sudo journalctl -u fr24-mcp -f
```

### dump1090 Service

```bash
sudo systemctl status dump1090
sudo journalctl -u dump1090 -f
```

---

## Configuration

### Dashboard Configuration

Edit `/opt/r510-dashboard/index.html` and modify the CONFIG section:

```javascript
const CONFIG = {
    // Enable/disable features
    FR24_ENABLED: true,
    DUMP1090_ENABLED: true,
    SDR_HARDWARE_CONNECTED: true,

    // API endpoints
    FR24_MCP_ENDPOINT: 'http://localhost:8000/fr24',
    DUMP1090_ENDPOINT: 'http://192.168.0.4/data/aircraft.json',

    // Map center (Omaha, NE)
    MAP_CENTER_LAT: 41.2565,
    MAP_CENTER_LON: -95.9345,

    // Update intervals (milliseconds)
    FLIGHT_UPDATE_INTERVAL: 3000,
    UPDATE_INTERVAL: 30000
};
```

After editing, restart the service:
```bash
sudo systemctl restart r510-dashboard
```

### FR24 MCP Configuration

Edit `~/.config/fr24-mcp/config.json`:

```json
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
```

---

## Ports Reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Dashboard | 8421 | HTTP | Main web interface |
| FR24 MCP | 8000 | HTTP | Flightradar24 API proxy |
| dump1090 | 8080 | HTTP | ADS-B aircraft data |
| Broadcastify | 8080 | WebSocket | Public safety radio (future) |

---

## Firewall Configuration

If using UFW:

```bash
# Dashboard
sudo ufw allow 8421/tcp

# FR24 MCP (if accessing remotely)
sudo ufw allow 8000/tcp

# dump1090 (if accessing remotely)
sudo ufw allow 8080/tcp

# Check status
sudo ufw status
```

---

## Troubleshooting

### Dashboard not loading

```bash
# Check service status
sudo systemctl status r510-dashboard

# Check if port is listening
sudo netstat -tulpn | grep 8421

# View logs
sudo journalctl -u r510-dashboard -n 50
```

### No flight data appearing

1. Check FR24 MCP:
   ```bash
   curl http://localhost:8000/health
   sudo systemctl status fr24-mcp
   ```

2. Check dump1090:
   ```bash
   curl http://localhost:8080/data/aircraft.json
   sudo systemctl status dump1090
   ```

3. Check RTL-SDR device:
   ```bash
   rtl_test
   lsusb | grep RTL
   ```

### Crime data not loading

1. Verify API key is set:
   ```bash
   sudo systemctl show r510-dashboard | grep SPOTCRIME
   ```

2. Check browser console for API errors

3. Test API manually:
   ```bash
   curl "https://api.spotcrime.com/crimes.json?lat=41.2565&lon=-95.9345&radius=0.05&key=YOUR_KEY"
   ```

### RTL-SDR not detected

```bash
# Check USB connection
lsusb | grep -i rtl

# Test device
rtl_test

# Check blacklisted modules
lsmod | grep dvb

# Reboot if drivers were just installed
sudo reboot
```

---

## Integration with Existing Command Center

To integrate with the Python curses dashboard:

Edit `command_center/app.py`:

```python
def open_web_dashboard(self):
    """Open web dashboard in browser"""
    import webbrowser
    webbrowser.open('http://localhost:8421')
```

Add hotkey in main loop:
```python
elif key == ord('W'):
    self.open_web_dashboard()
```

---

## Updating the Dashboard

```bash
cd ~/r510-command-center

# Pull latest changes
git pull

# Redeploy
sudo ./deploy-dashboard.sh
```

---

## Uninstall

```bash
# Stop and disable services
sudo systemctl stop r510-dashboard fr24-mcp dump1090
sudo systemctl disable r510-dashboard fr24-mcp dump1090

# Remove service files
sudo rm /etc/systemd/system/r510-dashboard.service
sudo rm /etc/systemd/system/fr24-mcp.service
sudo rm /etc/systemd/system/dump1090.service

# Remove dashboard files
sudo rm -rf /opt/r510-dashboard

# Remove FR24 MCP
sudo npm uninstall -g @flightradar24/fr24api-mcp

# Remove dump1090
sudo rm -rf /opt/dump1090

# Reload systemd
sudo systemctl daemon-reload
```

---

## Production Checklist

- [ ] Dashboard service running and accessible
- [ ] FR24 MCP or dump1090 providing flight data
- [ ] SpotCrime API key configured (optional)
- [ ] Firewall rules configured
- [ ] Services set to start on boot
- [ ] Logs being monitored
- [ ] RTL-SDR device connected and working (if using)
- [ ] Dashboard accessible from network
- [ ] All panels showing data

---

## Support

- GitHub: https://github.com/Mattjhagen/r510-command-center
- Issues: Open an issue with the `dashboard` label
- Logs: Always include `journalctl` output when reporting issues
