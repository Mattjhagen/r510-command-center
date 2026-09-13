#!/bin/bash
echo "════════════════════════════════════════════════════════════"
echo "  CONFIGURE GOOGLE MAPS API KEY"
echo "════════════════════════════════════════════════════════════"
echo ""

read -p "Enter your Google Maps API key: " API_KEY

if [ -z "$API_KEY" ]; then
    echo "❌ No API key provided"
    exit 1
fi

echo ""
echo "Configuring command-center-dashboard.html..."

# Replace API key in both places
sed -i.bak "s/YOUR_GOOGLE_MAPS_API_KEY/${API_KEY}/g" command-center-dashboard.html

if [ $? -eq 0 ]; then
    echo "✅ API key configured successfully"
    echo ""
    echo "Files ready:"
    echo "  • index.html (Canvas map - no API key)"
    echo "  • command-center-dashboard.html (Google Maps - API key set)"
    echo ""
else
    echo "❌ Configuration failed"
    exit 1
fi
