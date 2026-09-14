#!/bin/bash
# ensure the Broadcastify calls-poller is running
if ! pgrep -f "calls-poller.py" > /dev/null; then
  exec setsid nohup /home/matt/r510-whisper-venv/bin/python -u /home/matt/r510-command-center/calls-poller.py >> /tmp/opencode/r510/calls-poller.out 2>&1 &
fi