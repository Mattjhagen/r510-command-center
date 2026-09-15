# 🌅 Tomorrow's Tasks - R410 Camera Dashboard

## ✅ What's Done

- R510: God's Eye View server running on port 4173 ✅
- R510: Bridge API running on port 9000 ✅
- R510: Services auto-start on boot ✅
- R410: Desktop environment installed ✅
- R410: GDM login screen showing ✅
- R410: Chromium browser installed ✅

---

## 🎯 Quick Start (5 Minutes)

### Step 1: Login to R410
**At R410's physical monitor:**
- Click username: `matt`
- Enter password
- Press Enter

### Step 2: Open Terminal
- Press `Ctrl+Alt+T`

### Step 3: Launch Camera Dashboard
**Paste this command:**
```bash
chromium-browser --kiosk http://100.103.3.35:4173 &
```

**Done!** You should see the 3D globe with all 109 cameras.

---

## 📹 What You'll See

- **3D Cesium globe** spinning
- **Camera markers (📹)** across Omaha metro area
- **Click any camera** to view live feed
- **Camera info panel** at bottom with details

### Camera Locations Include:
- I-80 @ 13th St, 42nd St, 60th St, 72nd St, 84th St, 132nd St
- I-480 @ West Dodge, 72nd St
- I-680 @ West Dodge, Maple St
- Dodge St @ 132nd St
- 120th & L St

---

## 🔧 Optional: Auto-Start on Boot

If you want the camera dashboard to open automatically every time R410 boots:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/camera-dashboard.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Camera Dashboard
Exec=chromium-browser --kiosk http://100.103.3.35:4173
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```

---

## 🎮 Controls

- **Mouse wheel**: Zoom in/out
- **Left click + drag**: Rotate globe
- **Right click + drag**: Pan camera
- **Click camera marker**: View live feed
- **F11**: Toggle fullscreen (if not in kiosk mode)
- **Alt+F4**: Close window

---

## 📊 Final Setup

**R510 (100.103.3.35 tailscale, 192.168.0.169 local)**:
- Original dashboard on monitor → http://localhost:8421
- Backend services running → ports 4173, 9000

**R410 (100.65.34.60 tailscale, 192.168.0.180 local)**:
- Camera dashboard on monitor → http://100.103.3.35:4173
- Dedicated viewing station

---

## 🐛 Troubleshooting

### Can't connect to R510?
```bash
# Test connectivity
curl http://100.103.3.35:4173

# If that fails, try local IP
chromium-browser --kiosk http://192.168.0.169:4173 &
```

### Wrong display?
```bash
# Check which display is active
echo $DISPLAY

# Try specific display
DISPLAY=:0 chromium-browser --kiosk http://100.103.3.35:4173 &
```

### Cameras not loading?
- Check that R510 services are running:
  ```bash
  ssh matt@100.103.3.35
  systemctl status gods-eye-view.service
  systemctl status crime-camera-bridge.service
  ```

---

## 📚 Full Documentation

- `/home/matt/r510-command-center/SETUP_R410.md` - Complete setup guide
- `/home/matt/r510-command-center/AGENT.md` - Full project history
- GitHub: https://github.com/Mattjhagen/r510-command-center

---

**That's it! See you tomorrow! 🚀📹**
