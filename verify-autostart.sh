#!/bin/bash
#
# Verify R510 Dashboard Autostart Configuration
# Checks that all services will start on boot
#

echo "═══════════════════════════════════════════════════════════"
echo "  R510 DASHBOARD AUTOSTART VERIFICATION"
echo "═══════════════════════════════════════════════════════════"
echo ""

SERVICES=("r510-dashboard" "fr24-mcp" "dump1090")

echo "Checking systemd services..."
echo ""

for service in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^${service}.service"; then
        echo "📋 Service: ${service}"

        # Check if enabled
        if systemctl is-enabled --quiet ${service} 2>/dev/null; then
            echo "   ✅ ENABLED for autostart"
        else
            echo "   ❌ NOT ENABLED for autostart"
            echo "   Fix: sudo systemctl enable ${service}"
        fi

        # Check if currently active
        if systemctl is-active --quiet ${service}; then
            echo "   ✅ Currently RUNNING"
        else
            echo "   ⚠️  Currently STOPPED"
            echo "   Fix: sudo systemctl start ${service}"
        fi

        # Show wants/required-by
        echo "   Target: $(systemctl show -p WantedBy ${service} --value)"
        echo ""
    else
        echo "⚠️  Service ${service} not found"
        echo ""
    fi
done

echo "═══════════════════════════════════════════════════════════"
echo "  REBOOT TEST INSTRUCTIONS"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "To verify services survive reboot:"
echo ""
echo "1. Check current state:"
echo "   systemctl status r510-dashboard fr24-mcp dump1090"
echo ""
echo "2. Reboot the server:"
echo "   sudo reboot"
echo ""
echo "3. After reboot, verify services started:"
echo "   systemctl status r510-dashboard fr24-mcp dump1090"
echo ""
echo "4. Check dashboard is accessible:"
echo "   curl http://localhost:8421"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "  AUTOSTART SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""

enabled_count=0
for service in "${SERVICES[@]}"; do
    if systemctl is-enabled --quiet ${service} 2>/dev/null; then
        ((enabled_count++))
    fi
done

echo "Services enabled for autostart: ${enabled_count}/${#SERVICES[@]}"
echo ""

if [ $enabled_count -eq ${#SERVICES[@]} ]; then
    echo "✅ All services configured for autostart"
    echo "   Dashboard will survive reboots!"
else
    echo "⚠️  Some services not configured for autostart"
    echo ""
    echo "To enable all services:"
    for service in "${SERVICES[@]}"; do
        if ! systemctl is-enabled --quiet ${service} 2>/dev/null; then
            echo "  sudo systemctl enable ${service}"
        fi
    done
fi

echo ""
