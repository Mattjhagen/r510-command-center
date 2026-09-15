#!/bin/bash
#
# Stop Crime-Camera Integration
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Crime-Camera Integration..."

# Stop bridge server
if [ -f bridge.pid ]; then
    PID=$(cat bridge.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping Crime-Camera Bridge (PID: $PID)..."
        kill $PID
    fi
    rm -f bridge.pid
fi

# Stop God's Eye View
if [ -f gods-eye.pid ]; then
    PID=$(cat gods-eye.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping God's Eye View (PID: $PID)..."
        kill $PID
    fi
    rm -f gods-eye.pid
fi

# Fallback: kill by process name
pkill -f "crime-camera-bridge.py" || true
pkill -f "vite.*gods-eye-view" || true

# Wait for processes to stop
sleep 2

# Check if ports are freed
if lsof -Pi :9000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Warning: Port 9000 is still in use"
else
    echo "✓ Port 9000 freed"
fi

if lsof -Pi :4173 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Warning: Port 4173 is still in use"
else
    echo "✓ Port 4173 freed"
fi

echo "Crime-Camera Integration stopped"
