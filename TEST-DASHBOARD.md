# Testing the Dashboard Locally

## Quick Test (Before Deploying to R510)

### 1. Test with your existing dump1090

Your dump1090 is running at: `http://192.168.0.169:8080/`

Open `index.html` in your browser:

```bash
cd ~/r510-command-center
open index.html
# or
firefox index.html
# or
chrome index.html
```

### 2. Check Browser Console

Press F12 to open developer tools and check:
- Network tab: See if requests to dump1090 are working
- Console tab: Look for any errors

### 3. Verify Data Sources

The dashboard will try to fetch:
- **Flight data** from `http://192.168.0.169:8080/data/aircraft.json`
- **Crime data** - simulated (no API key needed for testing)

### 4. Expected Result

You should see:
- ✅ Aircraft on the map (purple X icons with tracks)
- ✅ Flight data table populated with real flights
- ✅ Crime incidents (simulated) with red pulsing markers
- ✅ All telemetry bars animating
- ✅ Live logs scrolling

### 5. Test dump1090 Endpoint

```bash
# Test if dump1090 is accessible
curl http://192.168.0.169:8080/data/aircraft.json

# Should return JSON with aircraft data
```

## CORS Issues?

If the browser blocks requests to dump1090, you have two options:

### Option A: Chrome with CORS Disabled (Testing Only)

```bash
# macOS
open -na "Google Chrome" --args --disable-web-security --user-data-dir=/tmp/chrome_dev

# Linux
google-chrome --disable-web-security --user-data-dir=/tmp/chrome_dev

# Then open: file:///path/to/index.html
```

### Option B: Run Local Web Server

```bash
cd ~/r510-command-center
python3 -m http.server 8421

# Then open: http://localhost:8421/index.html
```

## Next Step: Deploy to R510

Once local testing works:

```bash
# Copy to R510
scp -r ~/r510-command-center/ user@192.168.0.169:~/

# SSH to R510
ssh user@192.168.0.169

# Deploy
cd ~/r510-command-center
sudo ./r510-deploy-all.sh
```

Access at: `http://192.168.0.169:8421`
