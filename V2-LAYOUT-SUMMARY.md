# R510 Dashboard V2 - Layout Update Summary

## What's New in V2

### 🎨 Layout Changes

**LEFT PANEL (Top to Bottom):**
- ◢ THREAT MATRIX (moved from right panel, expanded)
- ◢ FLIGHTS (aircraft tracker)
- ◢ CRIME SCANNER (incident list)

**CENTER PANELS:**
- ◢ AIRSPACE - OMAHA SECTOR (map, top 2/3)
- ◢ ACTIVE INCIDENT (crime details, bottom 1/3)

**RIGHT PANEL (Full Height):**
- ◢ OMAHA POLICE SCANNER (full panel height)
  - Transcript text: **DOUBLED in size** (16px, was 8px)
  - Order: **Newest at BOTTOM** (scrolls up)
  - Auto-scroll to latest transmission
  - Enhanced visibility for monitoring

### 📋 Menu System (Bottom Bar)

**Hidden panels accessible via keyboard:**
- `[T]` - TELEMETRY (GPU, VRAM, TPS metrics)
- `[L]` - SYSTEM LOGS (operational logs)
- `[J]` - JOURNAL (mission notes)
- `[ESC]` - Close any open modal

These panels now appear as **modal overlays** instead of cluttering the main view.

### 🔧 Crash Prevention

**Enhanced Error Handling:**
- All DOM access wrapped in `safeGetElement()` function
- Every function wrapped in try-catch blocks
- Graceful degradation if modules fail to load
- No more crashes on page refresh

**Initialization Safety:**
- Proper async loading order
- Delayed auto-start (prevents race conditions)
- Safe cleanup of old markers
- Error logging for debugging

### 🎯 Favicon

New animated orbital command center icon:
- Radar sweep animation
- Pulsing satellite nodes
- Cyan/orbital theme colors
- SVG format (scales perfectly)

## Deployment

### Quick Deploy (Recommended)

```bash
sudo ./deploy-v2-layout.sh
```

This will:
1. Backup current versions
2. Deploy to both port 7072 (primary) and 8421 (secondary)
3. Restart services
4. Optionally restart Chrome kiosk

### Manual Deploy to Port 7072 (Primary/Chrome Kiosk)

```bash
# Backup
sudo cp /home/matt/r510-web/r510.html /home/matt/r510-web/r510.html.backup

# Deploy
sudo cp index.html /home/matt/r510-web/r510.html
sudo cp favicon.svg /home/matt/r510-web/favicon.svg
sudo chown matt:matt /home/matt/r510-web/r510.html /home/matt/r510-web/favicon.svg

# Restart
sudo systemctl restart r510-web
```

### Manual Deploy to Port 8421 (Secondary)

```bash
# Backup
sudo cp /opt/r510-dashboard/index.html /opt/r510-dashboard/index.html.backup

# Deploy
sudo cp index.html /opt/r510-dashboard/
sudo cp favicon.svg /opt/r510-dashboard/
sudo chmod 644 /opt/r510-dashboard/index.html

# Restart
sudo systemctl restart r510-dashboard
```

## URLs

- **Primary (Chrome kiosk):** http://192.168.0.169:7072
- **Secondary:** http://192.168.0.169:8421

## Testing Checklist

After deployment, verify:

- [ ] Map loads correctly
- [ ] Aircraft markers appear
- [ ] Crime incidents populate
- [ ] Police scanner auto-starts
- [ ] Transcripts appear at BOTTOM
- [ ] Transcripts are DOUBLE SIZE and readable
- [ ] Press `T` - Telemetry modal opens
- [ ] Press `L` - System logs modal opens
- [ ] Press `J` - Journal modal opens
- [ ] Press `ESC` - Modal closes
- [ ] No console errors on page load
- [ ] Refresh 3-5 times - no crashes
- [ ] All status dots show correct state
- [ ] News marquee scrolls at bottom
- [ ] Favicon appears in browser tab

## Troubleshooting

### Panels still crash on refresh

1. Open browser console (F12)
2. Look for JavaScript errors
3. Check which element is missing
4. Report the error - we'll add more safety checks

### Scanner not auto-starting

- Wait 4 seconds after page load (delayed start)
- Manually click "▶ PLAY" button
- Check browser console for audio playback errors

### Transcripts not appearing

- Verify scanner is playing (should say "LIVE")
- Check console for WebSocket/fetch errors
- Transcripts appear every 8 seconds

### Keyboard shortcuts not working

- Make sure modal overlay is not stuck open
- Press `ESC` first to clear any modals
- Try clicking on the page first (focus)

## Autostart Status

All services are already configured to survive reboots:

```bash
# Check status
systemctl is-enabled r510-dashboard r510-web r510-aircraft-proxy r510-camera-proxy

# All should show: enabled
```

## Files Modified

- `index.html` - New V2 layout
- `favicon.svg` - New orbital icon
- `deploy-v2-layout.sh` - Deployment script
- `V2-LAYOUT-SUMMARY.md` - This file

## Rollback

If you need to rollback to the previous version:

```bash
# Port 7072 (primary)
sudo cp /home/matt/r510-web/r510.html.backup-YYYYMMDD-HHMMSS /home/matt/r510-web/r510.html
sudo systemctl restart r510-web

# Port 8421 (secondary)
sudo cp /opt/r510-dashboard/index.html.backup-YYYYMMDD-HHMMSS /opt/r510-dashboard/index.html
sudo systemctl restart r510-dashboard
```

Replace `YYYYMMDD-HHMMSS` with the timestamp of your backup.

## Next Steps

1. Run `sudo ./deploy-v2-layout.sh`
2. Test in browser at http://192.168.0.169:7072
3. Verify police scanner transcripts are double-size
4. Test keyboard shortcuts (T, L, J, ESC)
5. Refresh page 3-5 times to verify stability
6. Report any issues

---

**Deployed:** $(date)
**Version:** V2.0
**Status:** Ready for deployment
