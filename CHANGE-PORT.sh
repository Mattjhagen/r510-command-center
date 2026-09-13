#!/bin/bash
# Change dashboard port from 8421 to 8421

NEW_PORT=8421

echo "Updating dashboard port to ${NEW_PORT}..."

# Update deploy script
sed -i '' "s/DASHBOARD_PORT=8421/DASHBOARD_PORT=${NEW_PORT}/g" deploy-dashboard.sh
sed -i '' "s/:8421/:${NEW_PORT}/g" deploy-dashboard.sh

# Update all documentation
for file in *.md *.txt *.sh; do
    if [ -f "$file" ]; then
        sed -i '' "s/:8421/:${NEW_PORT}/g" "$file" 2>/dev/null
        sed -i '' "s/8421/${NEW_PORT}/g" "$file" 2>/dev/null
    fi
done

echo "✅ Port updated to ${NEW_PORT}"
echo ""
echo "Dashboard will now run on: http://192.168.0.169:${NEW_PORT}"
