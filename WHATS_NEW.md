# What's New on R510 - Live Camera Integration

## 🎯 Current State

**Your R510 monitor is currently showing:** `http://localhost:8421` (your original dashboard)

**What's new:** We added **109 live cameras** that can show feeds near each crime/police report!

---

## 📹 What You Now Have

### 1. Live Camera System
- **109 cameras** covering Omaha metro area
- **Real-time feeds** from Nebraska DOT, Iowa DOT, and WOWT
- **Auto-refresh** every 3-5 seconds
- **Geographic search** - finds cameras near any location

### 2. Crime-Camera Correlation
- For each police report/911 call in `crime.json`
- **Automatically finds nearby cameras** (within 1.5km)
- Shows **distance to each camera**
- **Live feeds** from those cameras

### 3. Three New Interfaces

#### A. Enhanced Camera Dashboard (Matrix Style)
**Features:**
- Full camera list in left sidebar (109 cameras)
- Large primary camera view in center
- 4-camera grid at bottom
- Green Matrix-style theme
- Auto-refresh every 3 seconds

**How to open:**
```bash
cd /home/matt/r510-command-center
./show-new-features.sh
# Choose option 1
```

#### B. Crime-Camera Widget
**Features:**
- Left panel: Active incidents/crimes
- Right panel: Nearby cameras for selected incident
- Click incident → see cameras → view feeds
- Can embed in your existing dashboard

**How to open:**
```bash
./show-new-features.sh
# Choose option 2 (side-by-side with your current dashboard)
```

#### C. God's Eye View (3D Globe)
**Features:**
- Photorealistic 3D Earth
- Camera markers on map
- Click marker → view live feed
- Zoom/pan/rotate
- Shows camera coverage cones

**How to open:**
```bash
./show-new-features.sh
# Choose option 3
```

---

## 🔗 How Crime-Camera Correlation Works

### Current Flow:

1. **Crime data** → `crime.json` file
   ```json
   [
     {
       "id": "2026091501234",
       "type": "ASSAULT",
       "lat": 41.259,
       "lon": -95.933,
       "timestamp": "2026-09-15T12:00:00Z"
     }
   ]
   ```

2. **Bridge API** reads crime.json
   - Loads all 109 cameras with coordinates
   - For each crime, calculates distance to every camera
   - Returns sorted list of nearby cameras

3. **Dashboard** shows correlation
   - Click on incident
   - See list of nearby cameras (sorted by distance)
   - View live feeds from those cameras

### Example API Call:

```bash
# Get cameras near downtown Omaha
curl "http://192.168.0.169:9000/api/cameras/nearby?lat=41.259&lon=-95.933&maxDistance=1500"
```

Returns:
```json
{
  "cameras": [
    {
      "id": "wowt-downtown",
      "name": "WOWT - Downtown Omaha",
      "distance": 145,
      "distance_text": "145m",
      "url": "https://webpubcontent.gray.tv/wowt/cameras/ubt.jpg"
    },
    {
      "id": "omaha-i80-13th",
      "name": "I-80 @ 13th Street",
      "distance": 892,
      "distance_text": "892m",
      "url": "https://dot511.nebraska.gov/images/vid-002080455-00.jpg"
    }
  ]
}
```

---

## 🎮 Try It Now

### Step 1: Add Some Test Crime Data

```bash
cat > /home/matt/r510-command-center/crime.json << 'EOF'
[
  {
    "id": "test-001",
    "type": "ASSAULT",
    "location": "Downtown Omaha",
    "lat": 41.259,
    "lon": -95.933,
    "timestamp": "2026-09-15T12:00:00Z",
    "priority": "high",
    "status": "active"
  },
  {
    "id": "test-002",
    "type": "TRAFFIC ACCIDENT",
    "location": "I-80 @ 72nd St",
    "lat": 41.224,
    "lon": -96.024,
    "timestamp": "2026-09-15T12:15:00Z",
    "priority": "normal",
    "status": "active"
  }
]
EOF
```

### Step 2: Open a Camera Dashboard

```bash
./show-new-features.sh
```

Choose an option:
- **1** = Enhanced Dashboard (best for camera viewing)
- **2** = Add widget to your existing dashboard
- **3** = God's Eye View (3D globe)

### Step 3: Test the Correlation

**In Enhanced Dashboard:**
1. Click "test-001" incident in left sidebar
2. See nearby cameras load
3. View live feeds from those cameras

**In Crime-Camera Widget:**
1. Click incident on left
2. Cameras appear on right with distances
3. Live feeds show below each camera name

**In God's Eye View:**
1. Look for camera markers on map
2. Click any marker
3. Feed opens in viewer panel

---

## 📊 What's Actually New on the Monitor

**Before (what you see now):**
- Original dashboard at http://localhost:8421
- No camera integration
- Manual camera checking

**After (what you can see):**
- **109 live cameras** integrated
- **Automatic camera assignment** to incidents
- **Geographic proximity search** (finds closest cameras)
- **Live feeds** refresh every 3-5 seconds
- **Multiple viewing options** (enhanced, widget, globe)

---

## 🔧 Integration with Your Existing Dashboard

If you want to add cameras to your **current dashboard at http://localhost:8421**, you have options:

### Option 1: Iframe Embed
Add to your dashboard HTML:
```html
<iframe src="file:///home/matt/r510-command-center/crime-cam-integration-widget.html"
        width="400px" height="600px"></iframe>
```

### Option 2: API Integration
Call from your dashboard JavaScript:
```javascript
// When you have a new 911 call
const call = {lat: 41.259, lon: -95.933};

// Get nearby cameras
fetch(`http://192.168.0.169:9000/api/cameras/nearby?lat=${call.lat}&lon=${call.lon}&maxDistance=1500`)
  .then(r => r.json())
  .then(data => {
    // Show cameras to dispatcher
    data.cameras.forEach(cam => {
      console.log(`${cam.name} - ${cam.distance_text} away`);
      // Display camera feed:
      // <img src="http://192.168.0.169:4173/api/cctv/frame/${cam.id}" />
    });
  });
```

### Option 3: Side-by-Side
Run both dashboards:
```bash
DISPLAY=:0 chromium-browser \
  http://localhost:8421 \
  file:///home/matt/r510-command-center/enhanced-dashboard.html &
```

---

## 📸 Screenshots of What You'll See

### Enhanced Dashboard
```
┌─────────────────────────────────────────────────┐
│  🛰️ R510 ORBITAL COMMAND CENTER                 │
│  [68 Cameras] [45 Online] [12:34:56]           │
├──────────────┬──────────────────────────────────┤
│ 📹 CAMERAS   │  [Large Camera View]             │
│              │                                   │
│ • I-80 13th  │  Currently showing:               │
│ • I-80 JFK   │  I-80 @ 13th Street              │
│ • Dodge 118  │  Downtown Omaha                  │
│ • ...        │                                   │
│              ├──────────┬──────────┬────────────┤
│              │ [Cam 1]  │ [Cam 2]  │ [Cam 3]   │
│              │          │          │            │
└──────────────┴──────────┴──────────┴────────────┘
```

### Crime-Camera Widget
```
┌──────────────┬─────────────────────┐
│ 🚨 INCIDENTS │ 📹 NEARBY CAMERAS   │
├──────────────┼─────────────────────┤
│ • ASSAULT    │ I-80 @ 13th - 145m  │
│   Downtown   │ [Live Feed Image]   │
│   12:00 PM   │                     │
│              │ WOWT Tower - 892m   │
│ • TRAFFIC    │ [Live Feed Image]   │
│   I-80/72nd  │                     │
│   12:15 PM   │                     │
└──────────────┴─────────────────────┘
```

---

## 🎯 Bottom Line

**YES!** You now have live camera feeds that appear near each police report. 

**To see it:**
1. Run `./show-new-features.sh`
2. Choose an option (1, 2, or 3)
3. The new interface replaces or supplements your current dashboard

**The correlation happens automatically:**
- Add crime to `crime.json` → Bridge API finds nearby cameras → Dashboard shows them

Currently, your monitor still shows the old dashboard. Run the script above to switch to the new camera-integrated view! 🎉
