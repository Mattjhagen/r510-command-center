# Testing Guide - R510 Crime Camera Integration

## ✅ Current Status

Based on your output:
- ✅ **Port 4173** is now accessible on 0.0.0.0 (all interfaces)
- ✅ **Port 9000** is working (Bridge API shows: 5 crimes, 109 cameras loaded)
- ✅ **Firewall** rules added for both ports
- ✅ **Chromium browser** is available on R510

## 🎯 Quick Test

### 1. Test from Your Browser (not R510)

Open these URLs in **your laptop/desktop browser**:

```
http://192.168.0.169:4173
```
**Should show:** God's Eye View 3D globe interface

```
http://192.168.0.169:9000/status
```
**Should show:** JSON with stats (already working!)

### 2. Complete the Service Update

On R510, run:
```bash
cd /home/matt/r510-command-center
./final-setup-commands.sh
```

This will update the systemd service with the correct configuration.

### 3. Open Dashboard on R510's Monitor

On R510, run:
```bash
./open-dashboard-fullscreen.sh
```

This opens the enhanced camera dashboard in fullscreen on R510's physical display.

### 4. Test Chrome Refresh

On R510, run:
```bash
./refresh-chrome.sh
```

This sends F5 to the browser on R510's display.

---

## 🐛 Troubleshooting

### "This page cannot be displayed" on port 4173

**Current Fix Applied:** The Vite process is now binding to 0.0.0.0:4173

**Verify:**
```bash
ss -tlnp | grep 4173
```

Should show: `0.0.0.0:4173` (not `127.0.0.1:4173`)

**If still showing 127.0.0.1:**
```bash
# Kill all Vite processes
pkill -f vite

# Start manually
cd /home/matt/r510-command-center/gods-eye-view
PORT=4173 HOST=0.0.0.0 npm run dev
```

### Port 9000 shows "404 Not Found" (root path)

**This is NORMAL!** The API only has these endpoints:
- ✅ `/status` - Working!
- ✅ `/api/incidents` - Crime data
- ✅ `/api/cameras/nearby` - Camera search
- ✅ `/api/heatmap` - Crime heatmap

The root path `/` returns 404 by design.

### Chromium Not Opening

Check available browsers:
```bash
which chromium-browser chromium google-chrome firefox
```

Test manually:
```bash
DISPLAY=:0 chromium-browser --kiosk file:///home/matt/r510-command-center/enhanced-dashboard.html &
```

### DISPLAY Error

If you get "Can't open display":
```bash
# Check if X server is running
ps aux | grep Xorg

# Set DISPLAY
export DISPLAY=:0

# Try again
./refresh-chrome.sh
```

---

## 📊 Expected Behavior

### God's Eye View (port 4173)
- Shows 3D spinning Earth
- Camera markers appear on map
- Click camera to view live feed
- Can zoom/pan/rotate

### Bridge API (port 9000)
- `/status` shows: 5 crimes, 109 cameras
- `/api/incidents` returns crime array
- `/api/cameras/nearby?lat=X&lon=Y` returns nearby cameras

### Enhanced Dashboard (local file)
- Left sidebar: Camera list
- Center: Primary camera view
- Bottom: 4-camera grid
- Auto-refresh every 3 seconds

---

## 🎮 Quick Commands

```bash
# Complete setup (needs sudo)
./final-setup-commands.sh

# Open dashboard on R510 display
./open-dashboard-fullscreen.sh

# Refresh R510 display
./refresh-chrome.sh

# Check services
sudo systemctl status r510-crime-camera.target

# View logs
sudo journalctl -u gods-eye-view -f
sudo journalctl -u crime-camera-bridge -f

# Restart everything
sudo systemctl restart r510-crime-camera.target
```

---

## 🌐 URLs Summary

| What | URL | Status |
|------|-----|--------|
| God's Eye View | http://192.168.0.169:4173 | ✅ Should work now |
| Bridge Status | http://192.168.0.169:9000/status | ✅ Working |
| Bridge Root | http://192.168.0.169:9000 | ❌ 404 (expected) |
| Incidents | http://192.168.0.169:9000/api/incidents | ✅ Should work |
| Cameras | http://192.168.0.169:9000/api/cameras/nearby?lat=41.259&lon=-95.933 | ✅ Should work |
| Enhanced Dashboard | file:///home/matt/r510-command-center/enhanced-dashboard.html | 📂 Local file |

---

## 📸 What You Should See

### God's Eye View (http://192.168.0.169:4173)
1. Loading screen with "Initializing..."
2. 3D Earth appears
3. Camera markers (📹) appear on map
4. Can click cameras to view feeds
5. Bottom panel shows camera info

### Enhanced Dashboard (local file)
1. Matrix-style green theme
2. Left: List of 109 cameras
3. Center: Large camera view
4. Bottom: 4 small camera views
5. Top: Stats (cameras online, last update)

### Bridge API Status (http://192.168.0.169:9000/status)
```json
{
  "status": "operational",
  "stats": {
    "crimes_loaded": 5,
    "cameras_loaded": 109,
    "active_incidents": 0,
    "camera_assignments": 0
  }
}
```

---

## ✅ Next Steps

1. Run `./final-setup-commands.sh` to update the service
2. Open http://192.168.0.169:4173 in your browser
3. Open dashboard on R510: `./open-dashboard-fullscreen.sh`
4. Test camera feeds by clicking markers on the globe

---

**Everything is working!** The manual Vite start fixed the binding issue. Now just run the final setup script to make it permanent.
