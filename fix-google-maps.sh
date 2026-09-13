#!/bin/bash
#
# Fix Google Maps Display - Ensure Hybrid View Shows Streets
#

echo "════════════════════════════════════════════════════════════"
echo "  FIXING GOOGLE MAPS DISPLAY"
echo "════════════════════════════════════════════════════════════"
echo ""

# Backup current file
echo "Creating backup..."
sudo cp /opt/r510-dashboard/index.html /opt/r510-dashboard/index.html.backup-maps
echo "✅ Backup created"
echo ""

# Fix the map initialization
echo "Updating map configuration..."
sudo tee /tmp/fix-map.js > /dev/null <<'JSEOF'
        // INITIALIZE GOOGLE MAP
        function initMap() {
            map = new google.maps.Map(document.getElementById('map'), {
                center: CONFIG.MAP_CENTER,
                zoom: 11,
                mapTypeId: google.maps.MapTypeId.HYBRID, // Fixed: Use MapTypeId constant
                disableDefaultUI: false, // Enable controls temporarily to debug
                mapTypeControl: true,
                zoomControl: true,
                streetViewControl: false,
                fullscreenControl: false,
                styles: [] // Remove custom styles that might hide labels
            });

            // Force map to refresh
            google.maps.event.addListenerOnce(map, 'idle', function() {
                console.log('Map loaded successfully');
            });

            // Add infrastructure markers
            addInfrastructureMarkers();

            // Start updates
            updateData();
            setInterval(updateData, CONFIG.UPDATE_INTERVAL);
        }
JSEOF

# Apply the fix
sudo sed -i '/function initMap()/,/^        }$/c\
        // INITIALIZE GOOGLE MAP\
        function initMap() {\
            map = new google.maps.Map(document.getElementById('\''map'\''), {\
                center: CONFIG.MAP_CENTER,\
                zoom: 11,\
                mapTypeId: google.maps.MapTypeId.HYBRID,\
                disableDefaultUI: false,\
                mapTypeControl: true,\
                zoomControl: true,\
                streetViewControl: false,\
                fullscreenControl: false\
            });\
\
            google.maps.event.addListenerOnce(map, '\''idle'\'', function() {\
                console.log('\''Map loaded successfully'\'');\
            });\
\
            addInfrastructureMarkers();\
            updateData();\
            setInterval(updateData, CONFIG.UPDATE_INTERVAL);\
        }' /opt/r510-dashboard/index.html

echo "✅ Map configuration updated"
echo ""

# Restart service
echo "Restarting dashboard service..."
sudo systemctl restart r510-dashboard
sleep 2

if systemctl is-active --quiet r510-dashboard; then
    echo "✅ Service restarted successfully"
else
    echo "❌ Service failed to restart"
    sudo systemctl status r510-dashboard
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  FIX APPLIED"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Changes made:"
echo "  ✅ Enabled hybrid map mode (satellite + streets)"
echo "  ✅ Enabled map controls for debugging"
echo "  ✅ Removed custom styles that hide labels"
echo "  ✅ Service restarted"
echo ""
echo "Refresh your browser (Ctrl+Shift+R or F5)"
echo ""
echo "If still no streets:"
echo "  1. Check browser console (F12) for errors"
echo "  2. Verify API key at: https://console.cloud.google.com"
echo "  3. Ensure 'Maps JavaScript API' is enabled"
echo "  4. Check API restrictions allow localhost + 192.168.0.169"
echo ""
echo "To revert:"
echo "  sudo cp /opt/r510-dashboard/index.html.backup-maps /opt/r510-dashboard/index.html"
echo "  sudo systemctl restart r510-dashboard"
echo ""
