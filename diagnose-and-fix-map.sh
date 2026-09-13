#!/bin/bash
#
# Diagnose and Fix Black Map Issue
#

echo "════════════════════════════════════════════════════════════"
echo "  DIAGNOSING BLACK MAP ISSUE"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if dashboard service is running
echo "1. Checking dashboard service..."
if systemctl is-active --quiet r510-dashboard; then
    echo "   ✅ Service is running"
else
    echo "   ❌ Service is not running"
    echo "   Starting service..."
    sudo systemctl start r510-dashboard
    sleep 2
fi
echo ""

# Check if port 8421 is responding
echo "2. Checking if dashboard responds..."
if curl -s http://localhost:8421 | head -1 | grep -q "DOCTYPE"; then
    echo "   ✅ Dashboard is serving HTML"
else
    echo "   ❌ Dashboard not responding"
    exit 1
fi
echo ""

# Check if API key is in the file
echo "3. Checking API key in dashboard..."
if sudo grep -q "YOUR_GOOGLE_MAPS_API_KEY" /opt/r510-dashboard/index.html; then
    echo "   ✅ API key found in file"
else
    echo "   ❌ API key NOT found in file"
    echo "   This is the problem! Fixing..."
    
    # Copy the correct file with API key
    if [ -f ~/r510-command-center/command-center-dashboard.html ]; then
        sudo cp ~/r510-command-center/command-center-dashboard.html /opt/r510-dashboard/index.html
        sudo systemctl restart r510-dashboard
        echo "   ✅ Fixed! API key added."
        sleep 2
    else
        echo "   ❌ Source file not found"
        exit 1
    fi
fi
echo ""

# Test API key
echo "4. Testing Google Maps API key..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY")
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ API key works (HTTP 200)"
else
    echo "   ❌ API key issue (HTTP $HTTP_CODE)"
    if [ "$HTTP_CODE" = "403" ]; then
        echo "   → Maps JavaScript API not enabled"
        echo "   → Go to: https://console.cloud.google.com/apis/library"
        echo "   → Search: Maps JavaScript API"
        echo "   → Click ENABLE"
    fi
fi
echo ""

echo "5. Creating simple test dashboard..."
sudo tee /opt/r510-dashboard/index.html > /dev/null <<'HTMLEOF'
<!DOCTYPE html>
<html>
<head>
    <title>R510 Dashboard - Map Test</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #0d0518; 
            color: #4ADE80; 
            font-family: monospace;
            overflow: hidden;
        }
        #status {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            padding: 20px;
            border: 2px solid #A855F7;
            z-index: 1000;
            font-size: 14px;
        }
        #map {
            width: 100vw;
            height: 100vh;
        }
        .error { color: #EF4444; }
        .success { color: #4ADE80; }
    </style>
</head>
<body>
    <div id="status">
        <div>🔍 R510 Dashboard - Diagnostic Mode</div>
        <div id="log"></div>
    </div>
    <div id="map"></div>

    <script>
        const log = document.getElementById('log');
        
        function addLog(msg, isError = false) {
            const div = document.createElement('div');
            div.className = isError ? 'error' : 'success';
            div.textContent = msg;
            log.appendChild(div);
            console.log(msg);
        }

        addLog('Loading Google Maps...');

        function initMap() {
            try {
                addLog('✅ Google Maps API loaded');
                
                const map = new google.maps.Map(document.getElementById('map'), {
                    center: { lat: 41.2565, lng: -95.9345 },
                    zoom: 11,
                    mapTypeId: 'hybrid'
                });
                
                addLog('✅ Map initialized');
                
                // Add a test marker
                new google.maps.Marker({
                    position: { lat: 41.2565, lng: -95.9345 },
                    map: map,
                    title: 'Omaha, NE'
                });
                
                addLog('✅ Marker added');
                addLog('✅ Map is working!');
                
                setTimeout(() => {
                    document.getElementById('status').style.opacity = '0.3';
                }, 3000);
                
            } catch (error) {
                addLog('❌ Error: ' + error.message, true);
            }
        }

        window.initMap = initMap;

        // Detect load errors
        window.gm_authFailure = function() {
            addLog('❌ API key authentication failed', true);
            addLog('→ Check API key in Google Cloud Console', true);
        };
    </script>

    <script async defer
        src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY&callback=initMap"
        onerror="document.getElementById('log').innerHTML += '<div class=error>❌ Failed to load Google Maps script</div>'">
    </script>
</body>
</html>
HTMLEOF

echo "   ✅ Test dashboard created"
echo ""

# Restart service
echo "6. Restarting dashboard..."
sudo systemctl restart r510-dashboard
sleep 2

if systemctl is-active --quiet r510-dashboard; then
    echo "   ✅ Service restarted"
else
    echo "   ❌ Service failed to start"
    sudo systemctl status r510-dashboard
    exit 1
fi
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  DIAGNOSTIC TEST DEPLOYED"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Now refresh the browser on R510 monitor (F5)"
echo ""
echo "You should see:"
echo "  • Green status messages in top-left"
echo "  • Google Maps with Omaha visible"
echo "  • A marker at the center"
echo ""
echo "If you see red error messages:"
echo "  • Take a photo/screenshot"
echo "  • Tell me what the error says"
echo ""
echo "If map works, run this to restore full dashboard:"
echo "  sudo cp ~/r510-command-center/command-center-dashboard.html /opt/r510-dashboard/index.html"
echo "  sudo systemctl restart r510-dashboard"
echo ""
