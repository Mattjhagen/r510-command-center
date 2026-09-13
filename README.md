# R510 Command Center

**Full-screen surveillance dashboard for R510 Alpha Node - Omaha Operations**

![Status](https://img.shields.io/badge/status-operational-success)
![Version](https://img.shields.io/badge/version-2.0-blue)

## Features

- 🛩️ **Aircraft Tracking** - Real-time ADS-B via OpenSky Network
- 🚨 **Crime Surveillance** - Priority-based incident tracking  
- 📻 **Police Scanner** - Live Broadcastify with transcription
- 📰 **News Feed** - r/Omaha + local news RSS
- 🗺️ **Dark Mode Map** - OpenStreetMap (no API keys)

## Quick Deploy

```bash
# On R510
sudo cp /tmp/dashboard.html /opt/r510-dashboard/index.html
sudo systemctl restart r510-dashboard
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| r510-dashboard | 8421 | Main dashboard |
| r510-aircraft-proxy | 8080 | OpenSky Network proxy |
| r510-rss-proxy | 8423 | RSS aggregator |

## Design Highlights

### Ergonomic Colors
Muted palette (#6eb3c4, #c96c6c, #d4a574) reduces eye strain for 24/7 monitoring.

### Auto-Start Everything
Police scanner + all services start automatically (no keyboard/mouse needed).

### Smart Map Panning
Only moves on new high-priority crimes (not auto-cycling).

## Future Enhancements

- Real Whisper transcription for police scanner
- Nebraska 511 traffic cameras (URLs blocked)
- FlightRadar24 local receiver integration
- SpotCrime API for real crime data

See [TODO.md](TODO.md) for details.

---

**Status**: ✅ Deployed and Operational
