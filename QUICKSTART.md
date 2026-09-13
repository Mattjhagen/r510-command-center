# R510 Command Center Dashboard - Quick Start

## 🚀 Deploy to R510 Server (5 Minutes)

### 1. Transfer Files to R510

```bash
# From your local machine
scp -r r510-command-center/ user@r510-server:~/
```

### 2. Run One-Command Deploy

```bash
# SSH into R510
ssh user@r510-server

# Navigate to directory
cd ~/r510-command-center

# Run deployment (requires sudo)
sudo ./r510-deploy-all.sh
```

The script will prompt you for:
- FR24 MCP installation (Y/n)
- dump1090 installation (Y/n)  
- SpotCrime API key (optional)

### 3. Access Dashboard

Open in your browser:
```
http://YOUR_R510_IP:8421
```

**Done!** 🎉

---

## What You Get

### Dashboard Features (All Enabled)

✅ **Live Air Traffic**
- Real-time flight data from FR24 or local ADS-B
- Interactive map with aircraft positions
- Flight data table (callsign, altitude, speed, track)

✅ **Crime & CAD Feed**
- SpotCrime API integration (optional)
- Real-time incident markers on map
- Severity-based color coding

✅ **Shaggoth-A1 Metrics**
- Training loss curve
- System telemetry (CPU, Memory, Network)
- Service status indicators

✅ **Broadcastify Integration (Ready)**
- Douglas County P25 feed (pending approval)
- Call log table with transcripts
- SDR hardware detection

✅ **CIA Reading Room Feed**
- Simulated intelligence document extracts
- Redacted/unredacted text highlighting

✅ **System Logs**
- Real-time server log feed
- Service health monitoring

---

## Data Sources Priority

The dashboard tries to fetch data in this order:

### Flight Data:
1. **FR24 MCP** (`http://localhost:8000`) - Preferred
2. **Local dump1090** (`http://192.168.0.4:8080`) - Fallback
3. **Simulated data** - Final fallback

### Crime Data:
1. **SpotCrime API** (if API key set)
2. **Simulated CAD data** - Fallback

---

## Quick Configuration

### Enable/Disable Features

Edit `/opt/r510-dashboard/index.html`:

```javascript
const CONFIG = {
    FR24_ENABLED: true,              // Use Flightradar24
    DUMP1090_ENABLED: true,          // Use local ADS-B
    SDR_HARDWARE_CONNECTED: true,    // RTL-SDR present
    // ...
};
```

Restart after changes:
```bash
sudo systemctl restart r510-dashboard
```

### Add SpotCrime API Key

```bash
sudo systemctl edit r510-dashboard
```

Add:
```ini
[Service]
Environment="SPOTCRIME_API_KEY=your_key_here"
```

Save and restart:
```bash
sudo systemctl restart r510-dashboard
```

---

## Hardware Requirements

### Minimum (Dashboard Only)
- R510 server with Ubuntu 24.04
- 512MB RAM
- Network connectivity

### Recommended (Full Features)
- RTL-SDR USB dongle for ADS-B reception
- Antenna for 1090MHz
- Direct internet access for APIs

---

## Verify Installation

### Check Services

```bash
# All services status
systemctl status r510-dashboard fr24-mcp dump1090

# Dashboard logs
sudo journalctl -u r510-dashboard -f
```

### Test Endpoints

```bash
# Dashboard
curl http://localhost:8421

# FR24 MCP
curl http://localhost:8000/health

# dump1090
curl http://localhost:8080/data/aircraft.json
```

### Test in Browser

1. Open `http://YOUR_R510_IP:8421`
2. Check browser console (F12) for errors
3. Verify data is loading in all panels
4. Check map for aircraft icons

---

## Common Issues

### Dashboard shows "Loading..."
- Check service: `sudo systemctl status r510-dashboard`
- Check logs: `sudo journalctl -u r510-dashboard -n 50`

### No aircraft on map
- Verify FR24 or dump1090 is running
- Check endpoints with `curl` commands above
- Confirm RTL-SDR is connected: `lsusb | grep RTL`

### Port 8421 not accessible
- Check firewall: `sudo ufw status`
- Allow port: `sudo ufw allow 8421/tcp`

---

## Next Steps

1. **Monitor Performance**
   ```bash
   sudo journalctl -u r510-dashboard -f
   ```

2. **Integrate with Python Dashboard**
   - Add web dashboard hotkey to curses interface
   - See `DEPLOYMENT.md` for integration code

3. **Configure for Production**
   - Set up reverse proxy (nginx)
   - Enable HTTPS with Let's Encrypt
   - Configure authentication

4. **Optimize Data Sources**
   - Tune update intervals
   - Configure map bounds for your area
   - Add custom telemetry sources

---

## Resources

- **Full Deployment Guide:** `DEPLOYMENT.md`
- **Dashboard README:** `DASHBOARD_README.md`
- **Main Project:** `README.md`
- **GitHub:** https://github.com/Mattjhagen/r510-command-center

---

## Support

Questions or issues? 

1. Check `DEPLOYMENT.md` for troubleshooting
2. Review service logs with `journalctl`
3. Open a GitHub issue with logs attached
