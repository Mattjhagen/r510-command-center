# Google Maps API Setup for R510 Dashboard

## 🗺️ Features Added

✅ **Google Maps Hybrid View** (Satellite + Labels)
✅ **Conditional Squawk Code Glow Effects**
✅ **Aircraft Markers with Rotation**
✅ **Infrastructure Reference Pins**
✅ **Dark Command Center Theme**

---

## 🔑 Get Google Maps API Key (5 Minutes)

### 1. Create Google Cloud Project

1. Go to: https://console.cloud.google.com/
2. Click "Select a Project" → "New Project"
3. Name: `r510-command-center`
4. Click "Create"

### 2. Enable Maps JavaScript API

1. In the search bar, type: `Maps JavaScript API`
2. Click on "Maps JavaScript API"
3. Click "ENABLE"

### 3. Create API Key

1. Navigate to: "APIs & Services" → "Credentials"
2. Click "+ CREATE CREDENTIALS" → "API key"
3. Copy the API key (looks like: `AIzaSyD...`)
4. Click "RESTRICT KEY" (recommended)

### 4. Restrict API Key (Recommended)

**Application Restrictions:**
- Choose "HTTP referrers"
- Add: `http://192.168.0.169:8421/*`
- Add: `http://localhost:8421/*`

**API Restrictions:**
- Choose "Restrict key"
- Select: "Maps JavaScript API"

Click "SAVE"

---

## 📝 Configure Dashboard

### Option A: Direct Edit (Quick)

```bash
# Edit the HTML file
nano ~/r510-command-center/command-center-dashboard.html

# Find this line:
GOOGLE_MAPS_API_KEY: 'YOUR_GOOGLE_MAPS_API_KEY',

# Replace with your key:
GOOGLE_MAPS_API_KEY: 'AIzaSyD...',

# Also find at the bottom:
src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY&callback=initMap"

# Replace with:
src="https://maps.googleapis.com/maps/api/js?key=AIzaSyD...&callback=initMap"
```

### Option B: Using sed (Automated)

```bash
cd ~/r510-command-center

# Set your API key
API_KEY="AIzaSyD..."

# Replace in file
sed -i "s/YOUR_GOOGLE_MAPS_API_KEY/${API_KEY}/g" command-center-dashboard.html
```

---

## 🚀 Deploy to R510

```bash
# Copy updated file to R510
scp command-center-dashboard.html user@192.168.0.169:~/r510-command-center/

# SSH to R510
ssh user@192.168.0.169

# Deploy
cd ~/r510-command-center
sudo cp command-center-dashboard.html /opt/r510-dashboard/index.html
sudo systemctl restart r510-dashboard
```

---

## 🎨 Squawk Code Colors

The dashboard now highlights squawk codes with color-coded glows:

| Squawk Code | Color | Meaning | Effect |
|-------------|-------|---------|--------|
| **7500** | 🔴 Crimson | Hijacking | Pulsing glow |
| **7600** | 🔴 Crimson | Radio Failure | Pulsing glow |
| **7700** | 🔴 Crimson | Emergency | Pulsing glow |
| **75xx, 76xx** | 🟠 Orange | Intercepted/Controlled | Solid glow |
| **1200** | 🔵 Blue | VFR | Solid glow |
| **Other** | 🟢 Green | Standard | Solid glow |

---

## 🏢 Infrastructure Markers

Pre-configured reference points:

- **OPD Central HQ** (cyan marker)
- **Fire Station 1** (red marker)

### Add More Markers

Edit `addInfrastructureMarkers()` function:

```javascript
const locations = [
    { pos: { lat: 41.2587, lng: -95.9378 }, title: 'OPD Central HQ', color: '#06b6d4' },
    { pos: { lat: 41.2620, lng: -95.9420 }, title: 'Fire Station 1', color: '#EF4444' },
    // Add your own:
    { pos: { lat: 41.XXXX, lng: -95.XXXX }, title: 'Your Location', color: '#4ADE80' }
];
```

---

## 🧪 Test Locally

```bash
cd ~/r510-command-center
python3 -m http.server 8421

# Open in browser:
# http://localhost:8421/command-center-dashboard.html
```

**Expected Result:**
- Google Maps hybrid view centered on Omaha
- Live aircraft markers from dump1090
- Squawk codes with color-coded glow effects
- Infrastructure reference markers visible

---

## 🐛 Troubleshooting

### Map shows "For development purposes only"

**Cause:** API key not configured or restricted

**Fix:**
1. Verify API key is in the HTML file (2 places)
2. Check API restrictions allow your domain
3. Verify "Maps JavaScript API" is enabled

### No aircraft appearing

**Cause:** dump1090 not reachable

**Fix:**
```bash
# Test dump1090
curl http://192.168.0.169:8080/data/aircraft.json

# Should return JSON with aircraft array
```

### CORS errors in browser console

**Cause:** Browser blocking dump1090 requests

**Fix:**
- Deploy to R510 (same origin as dump1090)
- Or configure dump1090 to send CORS headers

### Map not loading

**Cause:** API key invalid or quota exceeded

**Fix:**
1. Check browser console for errors
2. Verify API key at: https://console.cloud.google.com/apis/credentials
3. Check quota: https://console.cloud.google.com/apis/api/maps-backend.googleapis.com/quotas

---

## 💰 Google Maps Pricing

**Free Tier:**
- $200 free credit per month
- Enough for ~28,000 map loads/month
- R510 dashboard uses ~1 load per page refresh

**For dashboard usage:** Stay well within free tier limits

---

## 🔒 Security Best Practices

1. **Restrict API Key:**
   - Use HTTP referrer restrictions
   - Only allow your dashboard domains

2. **Keep Key Private:**
   - Don't commit to public repositories
   - Use environment variables for production

3. **Monitor Usage:**
   - Set up billing alerts
   - Review usage at: https://console.cloud.google.com/apis/dashboard

---

## 📊 Map Customization

### Change Map Type

```javascript
mapTypeId: 'hybrid',  // Satellite + labels (current)
// Or:
mapTypeId: 'satellite',  // Satellite only
mapTypeId: 'roadmap',    // Standard road map
mapTypeId: 'terrain',    // Terrain map
```

### Adjust Zoom Level

```javascript
zoom: 11,  // Current (city-wide)
// Increase for closer view, decrease for wider area
```

### Change Center Point

```javascript
center: { lat: 41.2565, lng: -95.9345 },  // Omaha, NE
// Replace with your coordinates
```

---

## 🎯 Next Steps

After deploying with Google Maps:

1. ✅ Verify map loads and displays correctly
2. ✅ Check aircraft markers appear with rotation
3. ✅ Verify squawk code glow effects work
4. ✅ Test infrastructure markers are visible
5. ✅ Add SpotCrime API for crime incident overlays
6. ✅ Configure Broadcastify when approved

---

## 📚 Resources

- **Google Maps API Docs:** https://developers.google.com/maps/documentation/javascript
- **Maps Console:** https://console.cloud.google.com/google/maps-apis
- **API Key Best Practices:** https://developers.google.com/maps/api-security-best-practices

---

## 🔄 Revert to Original (Canvas Map)

If you need to revert to the canvas-based map:

```bash
cd ~/r510-command-center
cp command-center-dashboard-original.html command-center-dashboard.html
sudo cp command-center-dashboard.html /opt/r510-dashboard/index.html
sudo systemctl restart r510-dashboard
```

---

**Files:**
- `command-center-dashboard.html` - Google Maps version (current)
- `command-center-dashboard-original.html` - Canvas version (backup)
- `command-center-dashboard-gmaps.html` - Google Maps source

**Support:** Open an issue on GitHub with screenshots if you encounter problems
