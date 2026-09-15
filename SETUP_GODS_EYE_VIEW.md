# Setting Up God's Eye View

God's Eye View is a separate open-source project that provides the 3D globe interface for live camera viewing.

## Installation

```bash
cd /home/matt/r510-command-center

# Clone God's Eye View
git clone https://github.com/bilawalsidhu/gods-eye-view.git

# Install dependencies
cd gods-eye-view
npm install

# Copy Omaha camera configuration
cp ../gods-eye-view/config/cctv_sources.omaha.json config/

# The integration has already updated the server providers
# No additional configuration needed!
```

## What Was Integrated

The r510-command-center integration has added:

1. **Omaha CCTV Configuration**
   - `config/cctv_sources.omaha.json` - 12 cameras covering Omaha metro

2. **Crime Tracking Provider**
   - `server/providers/crime.js` - Crime-camera correlation API
   - Integrated into `server/providers/local.js`

3. **Network Configuration**
   - Updated `server/standalone/vite.config.js` to bind to 0.0.0.0
   - Set port to 4173 for R510 deployment

## Running

God's Eye View is managed by systemd:

```bash
# Start
sudo systemctl start gods-eye-view.service

# Stop
sudo systemctl stop gods-eye-view.service

# Status
sudo systemctl status gods-eye-view.service

# Logs
sudo journalctl -u gods-eye-view -f
```

Or use the integrated scripts:

```bash
cd /home/matt/r510-command-center
./start-crime-camera-integration.sh
```

## Access

Once running:
- **Web Interface**: http://100.103.3.35:4173
- **CCTV API**: http://100.103.3.35:4173/api/cctv/sources
- **Crime API**: http://100.103.3.35:4173/api/crime/incidents

## Updates

To update God's Eye View to the latest version:

```bash
cd /home/matt/r510-command-center/gods-eye-view

# Pull latest changes
git pull origin main

# Reinstall dependencies
npm install

# Rebuild
npm run build

# Restart service
sudo systemctl restart gods-eye-view.service
```

## More Information

- **Project Homepage**: https://github.com/bilawalsidhu/gods-eye-view
- **Documentation**: See the gods-eye-view/README.md file
- **License**: MIT

## Note

God's Eye View is maintained as a separate git repository and is not included in the r510-command-center git history. The configuration files and integration code are part of r510-command-center, but the main application code remains in its own repository.
