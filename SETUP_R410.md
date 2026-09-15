# Setting Up Camera Dashboard on R410

**Goal**: Run the Enhanced Camera Dashboard on R410's monitor instead of R510.

---

## 🎯 Why R410 is Better for Cameras

- ✅ Dedicated monitor for camera viewing
- ✅ R510 can keep its original dashboard
- ✅ Separate machine = better performance
- ✅ Can access R510's camera services over network

---

## 📋 Prerequisites on R410

1. **Network Access to R510**
   - R410 must be able to reach http://192.168.0.169:4173
   - R410 must be able to reach http://192.168.0.169:9000

2. **Web Browser**
   - Chromium, Chrome, or Firefox installed
   - X Server running (for display)

3. **SSH Access** (optional)
   - For remote setup from your workstation

---

## 🚀 Quick Setup on R410

### Option 1: Open in Browser (Simplest)

On R410, open Chromium and navigate to:

**God's Eye View (3D Globe)**:
```
http://192.168.0.169:4173
```

**Enhanced Dashboard (Matrix Style)**:
```
http://192.168.0.169:4173/enhanced-dashboard.html
```

Wait, that won't work because enhanced-dashboard.html is a local file on R510...

### Option 2: Copy Dashboard to R410

**From R510**, copy the dashboard files to R410:
```bash
# On R510, copy files to R410
scp /home/matt/r510-command-center/enhanced-dashboard.html matt@r410:/home/matt/
scp /home/matt/r510-command-center/crime-cam-integration-widget.html matt@r410:/home/matt/
```

**On R410**, open the local file:
```bash
# If using X display
chromium-browser --kiosk file:///home/matt/enhanced-dashboard.html &

# Or
firefox file:///home/matt/enhanced-dashboard.html &
```

**Update the API URLs in the file** to point to R510:

Edit `/home/matt/enhanced-dashboard.html` on R410 and change:
```javascript
// OLD (won't work on R410)
const SERVER_IP = '100.103.3.35';

// NEW (use R510's IP)
const SERVER_IP = '192.168.0.169';
```

### Option 3: Just Use God's Eye View (Recommended)

The simplest solution is to use God's Eye View directly since it's already accessible over the network:

**On R410**:
```bash
chromium-browser --kiosk http://192.168.0.169:4173 &
```

This gives you:
- ✅ 3D globe with all 109 cameras
- ✅ Click cameras to view feeds
- ✅ No file copying needed
- ✅ Automatically uses R510's API

---

## 🔧 Detailed Setup Steps

### Step 1: Test Network Connectivity

**From R410**, test that you can reach R510's services:

```bash
# Test God's Eye View
curl -I http://192.168.0.169:4173

# Test Bridge API
curl http://192.168.0.169:9000/status
```

Both should return 200 OK.

### Step 2: Choose Your Dashboard

**A. God's Eye View (Easiest)** ⭐ RECOMMENDED

On R410:
```bash
# Full screen
chromium-browser --kiosk http://192.168.0.169:4173 &

# Or regular window
chromium-browser http://192.168.0.169:4173 &
```

**B. Enhanced Matrix Dashboard** (Requires file copy + edit)

1. Copy from R510 to R410:
```bash
# On R510:
scp /home/matt/r510-command-center/enhanced-dashboard.html matt@r410:/home/matt/
```

2. On R410, edit the file:
```bash
nano /home/matt/enhanced-dashboard.html
```

Find this line (around line 260):
```javascript
const SERVER_IP = '100.103.3.35';
```

Change to:
```javascript
const SERVER_IP = '192.168.0.169';  // R510's IP
```

3. Open in browser:
```bash
chromium-browser --kiosk file:///home/matt/enhanced-dashboard.html &
```

**C. Crime-Camera Widget** (For embedding in existing dashboard)

Same process as Enhanced Dashboard but use:
```bash
scp /home/matt/r510-command-center/crime-cam-integration-widget.html matt@r410:/home/matt/
```

---

## 🎨 What You'll See on R410

### God's Eye View
- 3D spinning Earth
- Camera markers (📹) on map
- Click any marker to view live feed
- Zoom/pan/rotate with mouse
- Camera info panel at bottom

### Enhanced Dashboard (if you copy/edit it)
- Green Matrix theme
- Camera list sidebar (109 cameras)
- Large primary view
- 4-camera grid
- Auto-refresh every 3 seconds

---

## 🐛 Troubleshooting

### "Connection Refused" on R410

**Problem**: Can't reach http://192.168.0.169:4173

**Solutions**:
```bash
# 1. Verify R510 services are running
ssh matt@192.168.0.169 'systemctl status r510-crime-camera.target'

# 2. Check firewall on R510
ssh matt@192.168.0.169 'sudo ufw status | grep 4173'

# 3. Test from R410
ping 192.168.0.169
curl -v http://192.168.0.169:4173
```

### Cameras Don't Load

**Problem**: Dashboard shows but no camera images

**Check**:
1. Bridge API is accessible:
   ```bash
   curl http://192.168.0.169:9000/status
   ```

2. Camera sources endpoint works:
   ```bash
   curl http://192.168.0.169:4173/api/cctv/sources
   ```

3. Browser console for errors (F12)

### Cross-Origin Issues (CORS)

If you see CORS errors in browser console:

**Problem**: Local file trying to access network API

**Solution**: Don't use `file://` protocol. Either:
- Use God's Eye View directly (http://192.168.0.169:4173)
- Serve the dashboard from R510's web server
- Enable CORS in browser (not recommended for production)

---

## 📊 Recommended Setup

**Best Configuration**:

- **R510 Monitor**: Original dashboard (http://localhost:8421)
- **R410 Monitor**: God's Eye View (http://192.168.0.169:4173)

This gives you:
- ✅ R510 keeps its working dashboard
- ✅ R410 shows live cameras on 3D globe
- ✅ No file copying needed
- ✅ No URL editing needed
- ✅ Both systems operational

---

## 🚀 One-Command Setup for R410

**Copy this entire block to R410 terminal**:

```bash
# Test connectivity
echo "Testing R510 services..."
curl -s http://192.168.0.169:9000/status | jq

# If that worked, open God's Eye View
if [ $? -eq 0 ]; then
    echo "✅ R510 is accessible"
    echo "🚀 Opening camera dashboard..."
    chromium-browser --kiosk http://192.168.0.169:4173 &
    echo "✅ Camera dashboard should now be visible on R410 monitor"
else
    echo "❌ Cannot reach R510. Check network and firewall."
fi
```

---

## 📝 Summary

**Easiest Solution**:
```bash
# On R410
chromium-browser --kiosk http://192.168.0.169:4173
```

**What you get**:
- 109 live cameras on 3D globe
- Click any camera marker to view
- Professional interface
- No file copying or editing

**Ready to try on R410?** 🎥
