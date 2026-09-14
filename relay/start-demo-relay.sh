#!/bin/bash
# Local demo radio feed: serves a synthetic dispatch-voice MP3 loop through
# the real relay -> whisper-transcribe pipeline so the dashboard populates
# without external radio access. Temp until the archon relay is live.
set -e
DEMO_MP3=/tmp/opencode/r510/stew_loop.mp3
if [ ! -f "$DEMO_MP3" ]; then
  echo "demo mp3 missing; run whisper venv generator first" >&2
  exit 1
fi
if ! pgrep -f "http.server 8831" >/dev/null 2>&1; then
  setsid nohup python3 -m http.server 8831 --bind 127.0.0.1 --directory /tmp/opencode/r510 >/tmp/opencode/r510/srvdemo.log 2>&1 &
fi
if ! pgrep -f "audio-relay.py" >/dev/null 2>&1; then
  cd /home/matt/r510-command-center
  setsid nohup env RLY_SOURCE=http://127.0.0.1:8831/stew_loop.mp3 RLY_BIND=127.0.0.1 RLY_PORT=8425 python3 relay/audio-relay.py >> /tmp/opencode/r510/relay-demo.log 2>&1 &
fi
sleep 1
curl -s -m 4 http://127.0.0.1:8425/health && echo " demo relay: OK"