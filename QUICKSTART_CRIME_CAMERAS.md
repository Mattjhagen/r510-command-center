# Quick Start: Crime Camera Integration

**Get live cameras working with crime tracking in 5 minutes**

## 1. Install Dependencies

```bash
cd /home/matt/r510-command-center

# Install Python dependency
pip3 install aiohttp

# Install Node.js dependencies for God's Eye View (first time only)
cd gods-eye-view
npm install
cd ..
```

## 2. Start Everything

### Option A: All-in-One Script (Recommended)

```bash
./start-crime-camera-integration.sh
```

This will:
- ✅ Check prerequisites
- ✅ Start Crime-Camera Bridge (port 9000)
- ✅ Start God's Eye View (port 5173)
- ✅ Show status and logs

### Option B: Manual Start

```bash
# Terminal 1: Start the bridge
python3 crime-camera-bridge.py

# Terminal 2: Start God's Eye View
cd gods-eye-view
npm run dev

# Terminal 3: Monitor logs
tail -f bridge.log gods-eye.log
```

## 3. Open the Dashboard

Open in your browser:
```
http://localhost:5173
```

Or use the integrated dashboard:
```
file:///home/matt/r510-command-center/crime-camera-dashboard.html
```

## 4. Verify Everything Works

### Check Status Endpoints

```bash
# Bridge status
curl http://localhost:9000/status

# Camera sources
curl http://localhost:5173/api/cctv/sources | jq '.sources | length'

# Active incidents
curl http://localhost:9000/api/incidents | jq '.incidents | length'

# Crime heatmap
curl http://localhost:9000/api/heatmap | jq '.heatmap | length'
```

### Expected Output

```json
{
  "status": "operational",
  "stats": {
    "crimes_loaded": 0,
    "cameras_loaded": 68,
    "active_incidents": 0,
    "camera_assignments": 0
  }
}
```

## 5. Test Camera Assignment

```bash
# Find cameras near a location (downtown Omaha)
curl "http://localhost:9000/api/cameras/nearby?lat=41.259&lon=-95.933&maxDistance=1000" | jq

# Assign cameras to an incident
curl -X POST http://localhost:9000/api/cameras/assign \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "test-001",
    "lat": 41.259,
    "lon": -95.933,
    "priority": "high"
  }' | jq
```

## 6. Stop Everything

```bash
./stop-crime-camera-integration.sh
```

## Troubleshooting

### "Port 9000 already in use"

```bash
# Find and kill the process
lsof -ti :9000 | xargs kill -9
```

### "Bridge server failed to start"

```bash
# Check the log
tail -n 50 bridge.log

# Verify Python dependencies
python3 -c "import aiohttp; print('OK')"
```

### "God's Eye View not loading"

```bash
# Check the log
tail -n 50 gods-eye.log

# Verify Node.js version
node --version  # Should be 24+ or 26+

# Reinstall dependencies
cd gods-eye-view
rm -rf node_modules package-lock.json
npm install
```

### "No cameras showing up"

```bash
# Verify camera config exists
ls gods-eye-view/config/cctv_sources.omaha.json

# Check camera data
jq '.cameras | length' cameras.json

# Test a camera URL directly
curl -I "https://dot511.nebraska.gov/images/vid-002080455-00.jpg"
```

## What's Next?

### Add Crime Data

Edit `crime.json` to add incidents:

```json
[
  {
    "id": "2026091501",
    "type": "ASSAULT",
    "lat": 41.259,
    "lon": -95.933,
    "timestamp": "2026-09-15T12:00:00Z",
    "priority": "high",
    "status": "active",
    "description": "Assault reported"
  }
]
```

Refresh the dashboard to see the incident and auto-assigned cameras.

### Integrate with 911 System

Connect your 911 CAD system to export to `crime.json`:

```python
import json
from datetime import datetime

def export_incident(incident):
    with open('crime.json', 'r+') as f:
        data = json.load(f)
        data.append({
            'id': incident.case_number,
            'type': incident.call_type,
            'lat': incident.latitude,
            'lon': incident.longitude,
            'timestamp': datetime.now().isoformat(),
            'priority': incident.priority,
            'status': 'active'
        })
        f.seek(0)
        json.dump(data, f, indent=2)
```

### Add More Cameras

Create a new config in `gods-eye-view/config/cctv_sources.mycity.json`:

```json
[
  {
    "id": "unique-id",
    "name": "Camera Name",
    "city": "City",
    "cityId": "city-slug",
    "lat": 40.7128,
    "lon": -74.0060,
    "url": "https://example.com/camera.jpg",
    "feedType": "image",
    "provider": "Provider Name"
  }
]
```

The cameras will be automatically loaded.

## Camera Sources Available

- **32 Nebraska DOT cameras** in Omaha
- **60+ Iowa DOT cameras** in Council Bluffs
- **6 WOWT news cameras** in Omaha downtown

All cameras are live, public domain, and update every 3-5 seconds.

## Key Features

### 🌐 God's Eye View
- 3D photorealistic globe
- Live camera markers with coverage cones
- Click any camera to view live feed
- Zoom, pan, rotate with mouse/keyboard
- Voice control (optional)

### 🚨 Crime Tracking
- Real-time incident mapping
- Crime heatmaps
- Automatic camera assignment
- Historical trend analysis

### 📹 Camera Management
- 68 cameras across Omaha metro
- Health monitoring
- Automatic fallback to Street View
- Multi-camera viewing

## Learn More

- **Full Documentation**: [CRIME_CAMERA_INTEGRATION.md](CRIME_CAMERA_INTEGRATION.md)
- **God's Eye View**: [gods-eye-view/README.md](gods-eye-view/README.md)
- **Live Cameras List**: [LIVE_CAMERAS_OMAHA.md](LIVE_CAMERAS_OMAHA.md)

## Support

Issues or questions?
- Check logs: `bridge.log` and `gods-eye.log`
- Review docs: `CRIME_CAMERA_INTEGRATION.md`
- God's Eye View issues: https://github.com/bilawalsidhu/gods-eye-view/issues
