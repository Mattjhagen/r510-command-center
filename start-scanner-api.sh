#!/bin/bash
# Start R510 Scanner API Server

cd "$(dirname "$0")"

PID_FILE="/tmp/scanner-api.pid"
LOG_FILE="$HOME/r510-command-center/scanner-api.log"
VENV="$HOME/r510-whisper-venv/bin/python3"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Scanner API already running (PID $OLD_PID)"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

echo "Starting R510 Scanner API on port 8898..."
nohup "$VENV" scanner-api.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

sleep 2

if kill -0 "$NEW_PID" 2>/dev/null; then
    echo "✓ Scanner API started (PID $NEW_PID)"
    echo "  Logs: $LOG_FILE"
    echo "  Health: http://127.0.0.1:8898/health"
    echo "  API: http://127.0.0.1:8898/api/scanner/recent"
else
    echo "✗ Failed to start"
    cat "$LOG_FILE"
    exit 1
fi
