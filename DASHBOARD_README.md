# R510 Command Center Dashboard

A full-screen, high-density command center interface designed for monitoring AI operations, public safety incidents, air traffic, and intelligence feeds.

## Features

### Current Implementation

The dashboard (`index.html`) currently displays:

1. **Shaggoth-A1 Training Metrics**
   - Real-time loss curve visualization
   - Training statistics (Loss, Context Window, GPU temp)
   - GitHub scraper status

2. **Live Unified SIGINT & Incident Map**
   - Simulated air traffic with heading indicators
   - Crime incident markers with pulsing effects
   - Grid overlay with center crosshair
   - **Center Coordinates**: LAT 41.2565, LON -95.9345 (Omaha, NE)

3. **Broadcastify Calls Feed**
   - P25 dispatch stream simulation
   - Talkgroup, frequency, unit, and transcript data
   - Real-time timestamp updates

4. **SpotCrime / Neighborhood CAD Feed**
   - Live crime incident table
   - Severity-based color coding (Critical/High/Medium/Low)
   - Flashing alerts for critical incidents (SHOTS FIRED, ARMED ROBBERY)

5. **CIA.gov Leak Feed**
   - Simulated intelligence document extracts
   - Redacted/unredacted text highlighting

6. **Server System Logs**
   - Real-time log feed
   - Service health monitoring

7. **System Telemetry**
   - CPU, Memory, Network, Disk I/O monitoring
   - Animated progress bars

## Usage

### Quick Start

Simply open `index.html` in a modern web browser:

```bash
open index.html
# or
firefox index.html
# or
chromium-browser --kiosk index.html  # For fullscreen kiosk mode
```

### Fullscreen Kiosk Mode (Recommended)

For a true command center experience on a dedicated monitor:

```bash
# Chrome/Chromium
chromium-browser --kiosk --app=file:///path/to/r510-command-center/index.html

# Firefox
firefox --kiosk file:///path/to/r510-command-center/index.html
```

## API Integration

### Flightradar24 Integration

To integrate real Flightradar24 data, you'll need to:

1. **Install the Flightradar24 MCP Server**:
   ```bash
   npm install -g @flightradar24/fr24api-mcp
   ```

2. **Update the JavaScript in `index.html`**:
   ```javascript
   async function fetchFlightData() {
       try {
           const response = await fetch('http://localhost:3000/api/flights', {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify({
                   bounds: {
                       north: 43.5,
                       south: 40.0,
                       west: -97.5,
                       east: -94.5
                   }
               })
           });
           const data = await response.json();
           state.flights = data.flights.map(f => ({
               id: f.callsign,
               lat: f.latitude,
               lon: f.longitude,
               alt: f.altitude,
               speed: f.ground_speed,
               track: f.heading
           }));
       } catch (error) {
           console.error('FR24 API error:', error);
           generateFlightData(); // Fallback to simulated data
       }
   }
   ```

3. **Fallback to Local dump1090**:
   If you have a local ADS-B receiver running dump1090:
   ```javascript
   const response = await fetch('http://192.168.0.4/data/aircraft.json');
   const data = await response.json();
   state.flights = data.aircraft.map(a => ({
       id: a.flight || a.hex,
       lat: a.lat,
       lon: a.lon,
       alt: a.altitude,
       speed: a.gs,
       track: a.track
   }));
   ```

### SpotCrime API Integration

1. **Get an API Key** from [SpotCrime](https://spotcrime.com/api.html)

2. **Update Configuration**:
   ```javascript
   const CONFIG = {
       CRIME_API_KEY: 'YOUR_API_KEY_HERE',
       OMAHA_LAT: 41.2565,
       OMAHA_LON: -95.9345,
       CRIME_RADIUS: 0.05,
       UPDATE_INTERVAL: 60000
   };
   ```

3. The dashboard will automatically switch to real API data when `CRIME_API_KEY` is set.

### Broadcastify Integration

For real public safety radio streams:

1. **Install Broadcastify Calls API client**
2. **Configure WebSocket or REST endpoint**:
   ```javascript
   const ws = new WebSocket('ws://localhost:8080/broadcastify');
   ws.onmessage = (event) => {
       const call = JSON.parse(event.data);
       state.bcfyCalls.unshift(call);
       updateBroadcastifyFeed();
   };
   ```

### Shaggoth-A1 Training Metrics

To display real training data:

1. **Expose training metrics via HTTP endpoint** in your training script
2. **Poll the endpoint**:
   ```javascript
   async function fetchTrainingMetrics() {
       const response = await fetch('http://localhost:8421/metrics');
       const data = await response.json();
       // Update metric graph with real data
       drawMetricGraph(data.loss_history);
   }
   ```

## Customization

### Color Scheme

Edit the CSS variables in `index.html`:

```css
body {
    background: #040406;  /* Deep black */
}

/* Accent colors */
border: 1px solid #5B21B6;  /* Kali purple */
color: #4ADE80;  /* Terminal green */
color: #EF4444;  /* Crimson red */
```

### Map Center & Range

Update the configuration object:

```javascript
const CONFIG = {
    MAP_CENTER_LAT: 41.2565,  // Your latitude
    MAP_CENTER_LON: -95.9345,  // Your longitude
    // ... other config
};
```

### Update Intervals

Adjust polling frequencies:

```javascript
const CONFIG = {
    UPDATE_INTERVAL: 60000,  // Crime data (60s)
    // ...
};

// In initialization:
setInterval(fetchCrimeData, 30000);  // Every 30 seconds
setInterval(generateBroadcastifyData, 10000);  // Every 10 seconds
```

## Deployment

### Option 1: Static Web Server

```bash
# Using Python
cd r510-command-center
python3 -m http.server 8080

# Using Node.js
npx http-server -p 8080
```

Then navigate to `http://localhost:8080/index.html`

### Option 2: Nginx

```nginx
server {
    listen 80;
    server_name command-center.local;
    
    root /path/to/r510-command-center;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Option 3: Embed in R510 Terminal Dashboard

Integrate with the existing Python curses dashboard:

```python
# In command_center/app.py
import webbrowser

def launch_web_dashboard():
    webbrowser.open('file:///path/to/index.html')
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    index.html                       │
│  ┌──────────────────────────────────────────────┐  │
│  │              JavaScript Core                 │  │
│  │  ┌────────────┐  ┌────────────┐             │  │
│  │  │ State Mgmt │  │ API Client │             │  │
│  │  └────────────┘  └────────────┘             │  │
│  │         │                │                   │  │
│  │         ▼                ▼                   │  │
│  │  ┌────────────┐  ┌────────────┐             │  │
│  │  │  Canvas    │  │ DOM Update │             │  │
│  │  │  Renderer  │  │  Engine    │             │  │
│  │  └────────────┘  └────────────┘             │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │          External Data Sources               │  │
│  │  - Flightradar24 MCP                         │  │
│  │  - SpotCrime API                             │  │
│  │  - Broadcastify WebSocket                    │  │
│  │  - Shaggoth Training Endpoint                │  │
│  │  - CIA Scraper Feed                          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Performance

- **Canvas Rendering**: 20 FPS (50ms interval) for smooth animations
- **Data Updates**: 1-60 seconds depending on source
- **Memory**: ~50MB typical usage
- **CPU**: <5% on modern hardware

## Browser Compatibility

Tested on:
- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+

**Note**: Kiosk mode works best in Chrome/Chromium.

## Troubleshooting

### Map not rendering
- Check browser console for errors
- Ensure canvas is not blocked by ad blockers

### API errors
- Verify API keys are correct
- Check CORS settings on API endpoints
- Confirm network connectivity

### Performance issues
- Reduce update intervals
- Decrease number of rendered objects on map
- Use Chrome's hardware acceleration

## Screenshots

The dashboard displays:
- 3-column layout with left sidebar for metrics
- Large central map with overlays
- Multiple data tables for incidents and logs
- Real-time updates with smooth animations

## Future Enhancements

- [ ] WebSocket support for real-time data
- [ ] Historical data playback
- [ ] Alert sound notifications
- [ ] Data export functionality
- [ ] Mobile-responsive layout
- [ ] Multi-monitor support
- [ ] Authentication/access control

## License

MIT - See main repository LICENSE file

## Support

For issues or questions:
- GitHub: https://github.com/Mattjhagen/r510-command-center
- Open an issue with the `dashboard` label
