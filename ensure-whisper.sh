#!/bin/bash
# Ensure the R510 whisper server is running (cron keepalive / @reboot).
LOCK=/tmp/r510-whisper.lock
(
  flock -n 9 || exit 0
  if ! pgrep -f "uvicorn whisper[-]server" >/dev/null 2>&1; then
    cd /home/matt/r510-command-center
    if [ -f whisper.env ]; then set -a; . ./whisper.env; set +a; fi
    setsid /home/matt/r510-whisper-venv/bin/uvicorn whisper-server:app --host 0.0.0.0 --port 8424 >> whisper-server.log 2>&1 &
  fi
) 9>"$LOCK"
exit 0