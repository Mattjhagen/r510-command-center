# Crime Camera Integration for R510 Command Center

**Real-time crime tracking with live camera feeds powered by God's Eye View**

This integration connects the R510 Command Center with God's Eye View to provide real-time visualization of 911 calls and crime incidents alongside live traffic camera feeds from the Omaha metro area.

## Architecture

```
┌─────────────────────────┐
│  R510 Command Center    │
│  (HTML Dashboard)       │
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐       ┌──────────────────────┐
│ Crime-Camera Bridge     │←─────→│  crime.json          │
│ (Python Server)         │       │  cameras.json        │
│ Port 9000               │       └──────────────────────┘
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐       ┌──────────────────────┐
│  God's Eye View         │←─────→│  config/             │
│  (3D Globe + CCTV)      │       │  cctv_sources.*.json │
│  Port 5173              │       └──────────────────────┘
└─────────────────────────┘
```

## Features

### 🎯 Crime Tracking
- **Real-time 911 call mapping** - Plot active incidents on the 3D globe
- **Crime heatmaps** - Visualize crime density across the metro area
- **Incident classification** - Color-coded by type and severity
- **Historical trends** - Track crime patterns over time

### 📹 Camera Integration
- **32 Omaha/Council Bluffs traffic cameras** from Nebraska DOT 511
- **60+ Iowa DOT cameras** covering Council Bluffs metro
- **WOWT news cameras** for downtown Omaha coverage
- **Automatic camera assignment** - Finds nearest cameras to each incident
- **Live feeds** - Real-time JPEG snapshots (3-5 second refresh)

### 🌐 God's Eye View Features
- **3D photorealistic globe** powered by Cesium
- **CCTV projection overlays** - See camera coverage areas
- **Click-to-view** - Click any camera marker for live feed
- **Multi-camera view** - Monitor multiple feeds simultaneously
- **Voice control** - Hands-free navigation and camera selection

## Quick Start

### 1. Prerequisites

```bash
# Node.js 24+ or 26+
node --version

# Python 3.8+
python3 --version

# Install Python dependencies
pip3 install aiohttp
```

### 2. Start the Crime-Camera Bridge

```bash
cd /home/matt/r510-command-center
python3 crime-camera-bridge.py
```

The bridge server will start on `http://localhost:9000`

### 3. Start God's Eye View

```bash
cd /home/matt/r510-command-center/gods-eye-view
npm install  # First time only
npm run dev
```

God's Eye View will start on `http://localhost:5173`

### 4. Load the Command Center Dashboard

Open in your browser:
```
http://localhost:8080
```

Or for local file access:
```
file:///home/matt/r510-command-center/index.html
```

## API Endpoints

### Crime-Camera Bridge (Port 9000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Health check and statistics |
| `/api/incidents` | GET | List all active 911 incidents |
| `/api/cameras/nearby?lat=X&lon=Y&maxDistance=M` | GET | Find cameras near a location |
| `/api/cameras/assign` | POST | Assign cameras to an incident |
| `/api/heatmap` | GET | Crime heatmap data |
| `/api/camera/{id}/feed` | GET | Camera feed info |

### God's Eye View (Port 5173)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cctv/sources` | GET | List all camera sources |
| `/api/cctv/health` | GET | Camera health/status |
| `/api/cctv/stream/{id}` | GET | Stream info for a camera |
| `/api/cctv/frame/{id}` | GET | Single frame with fallback |
| `/api/crime/incidents` | GET | Crime incidents |
| `/api/crime/nearby/{id}` | GET | Cameras near an incident |
| `/api/crime/heatmap` | GET | Crime heatmap |
| `/api/crime/stats` | GET | Crime statistics |

## Camera Sources

### Nebraska DOT 511 Cameras
- **Coverage**: 552 cameras statewide, 32 in Omaha metro
- **Format**: JPEG snapshots (updated every 3-5 seconds)
- **URL Pattern**: `https://dot511.nebraska.gov/images/vid-{CODE}-00.jpg`
- **License**: Public domain, no authentication required

Key Omaha locations:
- I-80 @ 13th Street (downtown)
- I-80 @ JFK/I-480 interchange
- Dodge St @ 118th St
- I-680 corridor
- Nebraska-Iowa Memorial Bridge

### Iowa DOT Cameras
- **Coverage**: 60+ cameras in Council Bluffs metro
- **Format**: JPEG snapshots + HLS video streams
- **Snapshot URL**: `https://atmsqf.iowadot.gov/SNAPSHOTS/PUBLIC/Metro/{camera}.jpeg`
- **Video URL**: `https://video2.iowadot.gov:8888/councilbluffs/{camera}/playlist.m3u8`
- **License**: Public domain

### WOWT News Cameras
- **Coverage**: Downtown Omaha, Blackstone district
- **Format**: JPEG snapshots
- **Update frequency**: ~30 seconds
- **License**: Public domain

## Configuration Files

### Camera Sources
Located in `gods-eye-view/config/`:
- `cctv_sources.omaha.json` - Omaha metro cameras (new)
- `cctv_sources.austin.json` - Austin, TX cameras
- `cctv_sources.tallinn.json` - Tallinn, Estonia cameras
- `cctv_sources.shinjuku.json` - Tokyo, Japan cameras

### Camera Data
`cameras.json` - Complete camera registry with coordinates:
```json
{
  "generated": "2026-09-13",
  "sources": ["NDOT", "IADOT", "WOWT"],
  "cameras": [
    {
      "id": "omaha-i80-13th",
      "name": "I-80 @ 13th Street",
      "lat": 41.23004840858447,
      "lng": -95.9335226739476,
      "url": "https://dot511.nebraska.gov/images/vid-002080455-00.jpg",
      "src": "NDOT"
    }
  ]
}
```

### Crime Data
`crime.json` - 911 call and crime incident data:
```json
[
  {
    "id": "2026091401234",
    "type": "ASSAULT",
    "lat": 41.2588,
    "lon": -95.9302,
    "timestamp": "2026-09-14T12:34:56Z",
    "priority": "high",
    "status": "active",
    "description": "Assault in progress"
  }
]
```

## Usage Examples

### Find Cameras Near an Incident

```bash
# Using the bridge API
curl "http://localhost:9000/api/cameras/nearby?lat=41.259&lon=-95.933&maxDistance=1000"
```

Response:
```json
{
  "location": {"lat": 41.259, "lon": -95.933},
  "cameras": [
    {
      "id": "wowt-downtown",
      "name": "WOWT - Downtown Omaha",
      "distance": 145.2,
      "distance_text": "145m",
      "url": "https://webpubcontent.gray.tv/wowt/cameras/ubt.jpg"
    }
  ],
  "count": 1
}
```

### Assign Cameras to an Incident

```bash
curl -X POST http://localhost:9000/api/cameras/assign \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "2026091401234",
    "lat": 41.259,
    "lon": -95.933,
    "priority": "high"
  }'
```

### Get Crime Heatmap

```bash
curl http://localhost:9000/api/heatmap
```

## Integration with External Systems

### 911 Command Center App
Repository: https://github.com/Mattjhagen/911-Command-Center-App

Integration points:
1. **Incident feed** - Export active calls to `crime.json`
2. **Camera dispatch** - Automatically assign cameras to incidents
3. **Live view** - Embed God's Eye View iframe for dispatchers

### CrimeStopper Web
Repository: https://github.com/Mattjhagen/CrimeStopper-web

Integration points:
1. **Crime mapping** - Import crime.json for public crime maps
2. **Tip submission** - Link camera footage to tip submissions
3. **Public CCTV viewer** - Embed safe-for-public camera feeds

## Development

### Adding New Camera Sources

1. Create a new config file in `gods-eye-view/config/`:

```json
// cctv_sources.mycity.json
[
  {
    "id": "unique-camera-id",
    "name": "Camera Name",
    "city": "City Name",
    "cityId": "city-slug",
    "provider": "Provider Name",
    "lat": 40.7128,
    "lon": -74.0060,
    "headingDeg": 90,
    "headingConfidence": "estimated",
    "pitchDeg": -5,
    "fovDeg": 70,
    "rangeM": 150,
    "mountHeightM": 8,
    "groundElevationM": 10,
    "feedType": "image",
    "url": "https://example.com/camera.jpg",
    "sourceKind": "configured",
    "poseSource": "manual",
    "license": "public-domain",
    "credit": "Provider Name"
  }
]
```

2. The cameras will be automatically loaded on next startup

### Extending the Bridge Server

Add new endpoints in `crime-camera-bridge.py`:

```python
async def handle_custom(request):
    """Custom endpoint"""
    return web.json_response({'status': 'ok'})

# Add to app routes
app.router.add_get('/api/custom', handle_custom)
```

## Troubleshooting

### Bridge Server Won't Start
```bash
# Check if port 9000 is already in use
lsof -i :9000

# Kill existing process
kill $(lsof -t -i :9000)
```

### God's Eye View Not Loading Cameras
```bash
# Check if config file exists
ls gods-eye-view/config/cctv_sources.omaha.json

# Check Vite dev server logs
npm run dev
```

### Cameras Showing "Synthetic" Fallback
- The upstream camera URL may be down
- Check the camera URL directly in a browser
- Verify network connectivity
- Check API rate limits

### Crime Data Not Updating
```bash
# Check crime.json file
cat crime.json | jq '.[] | select(.timestamp > "2026-09-14")'

# Verify bridge server is reading the file
curl http://localhost:9000/status
```

## Performance Optimization

### Cache Configuration
The bridge server caches crime data for 30 seconds:
```python
CACHE_TTL_MS = 30000  # Adjust in crime-camera-bridge.py
```

### Camera Polling
Cameras auto-refresh every 3-5 seconds. To adjust:
```javascript
// In God's Eye View CCTV layer
const REFRESH_INTERVAL = 5000; // milliseconds
```

### Distance Calculations
Camera search radius defaults to 1km. For high-priority incidents:
```python
max_distance = 2000 if priority == 'high' else 1000
```

## Security Considerations

### Public Data Only
All camera feeds use public, unauthenticated URLs:
- Nebraska DOT 511 (public domain)
- Iowa DOT (public domain)
- WOWT (public broadcast)

**DO NOT** add cameras that require authentication or are not public.

### Crime Data Privacy
- `crime.json` should contain only public data
- Remove PII (names, addresses, phone numbers)
- Use case numbers instead of victim identifiers

### CORS Configuration
The bridge server enables CORS for local development. For production:
```python
# Restrict to specific origins
response.headers['Access-Control-Allow-Origin'] = 'https://yourdomain.com'
```

## Deployment

### Production Checklist
- [ ] Set up process manager (systemd/PM2)
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Enable HTTPS
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Set up monitoring/alerts
- [ ] Document incident response procedures

### Systemd Service Example
```ini
[Unit]
Description=Crime-Camera Bridge Server
After=network.target

[Service]
Type=simple
User=matt
WorkingDirectory=/home/matt/r510-command-center
ExecStart=/usr/bin/python3 crime-camera-bridge.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

This integration uses public domain data sources. Attribution:
- Nebraska DOT 511 cameras
- Iowa DOT cameras  
- WOWT News cameras
- God's Eye View (MIT License)

## Credits

- **God's Eye View** by Bilawal Sidhu
- **Nebraska DOT** - Public traffic cameras
- **Iowa DOT** - Public traffic cameras
- **WOWT** - Public news cameras
- **R510 Command Center** integration

## Support

For issues or questions:
- God's Eye View: https://github.com/bilawalsidhu/gods-eye-view
- 911 Command Center: https://github.com/Mattjhagen/911-Command-Center-App
- CrimeStopper: https://github.com/Mattjhagen/CrimeStopper-web
