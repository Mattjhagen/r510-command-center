#!/bin/bash
# ensure scanner-hub is running
if ! pgrep -f "scanner-hub.py" > /dev/null; then
  exec setsid nohup /home/matt/r510-whisper-venv/bin/python -u /home/matt/r510-command-center/scanner-hub.py >> /tmp/opencode/r510/scanner-hub.out 2>&1 &
fi