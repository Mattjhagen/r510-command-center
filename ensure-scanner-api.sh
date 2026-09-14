#!/bin/bash
# ensure the R510 scanner-api (port 8898) is running
if ! pgrep -f "scanner-api.py" > /dev/null; then
  cd /home/matt/r510-command-center
  exec setsid nohup /home/matt/r510-whisper-venv/bin/python3 scanner-api.py >> /tmp/opencode/r510/scanner-api.out 2>&1 &
fi