#!/bin/bash
# One-shot deploy of the R510 audio relay onto archon-fly-gateway.
# Run ON archon (as root / sudo). Usage:
#   RLY_SOURCE='https://broadcastify.cdnstream1.com/25460' \
#   RLY_BIND=100.82.142.55 RLY_PORT=8425 ./deploy-archon.sh
set -e

RLY_SOURCE="${RLY_SOURCE:-}"
RLY_BIND="${RLY_BIND:-100.82.142.55}"
RLY_PORT="${RLY_PORT:-8425}"

if [ -z "$RLY_SOURCE" ]; then
  echo "error: RLY_SOURCE is required" >&2
  exit 1
fi

echo "==> checking source reachability from archon..."
code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 -A "Mozilla/5.0" "$RLY_SOURCE" || echo 000)
echo "    source HTTP $code"
if [ "$code" = "200" ] || [ "$code" = "206" ] || [ "$code" = "302" ]; then
  echo "    source reachable"
else
  echo "    WARNING: source returned $code; deploy anyway? Ctrl-C to abort (5s)" >&2
  sleep 5
fi

echo "==> installing relay..."
mkdir -p /opt/r510-relay
install -m 755 "$(dirname "$0")/audio-relay.py" /opt/r510-relay/audio-relay.py

echo "==> writing systemd unit..."
cat > /etc/systemd/system/r510-relay.service <<EOF
[Unit]
Description=R510 audio relay (Broadcastify -> Tailscale)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/r510-relay/audio-relay.py
Environment=RLY_SOURCE=$RLY_SOURCE
Environment=RLY_BIND=$RLY_BIND
Environment=RLY_PORT=$RLY_PORT
Environment=RLY_TAIL_BYTES=24576
Environment=RLY_STALL=15
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now r510-relay
sleep 3
echo "==> relay health:"
curl -s -m 5 "http://127.0.0.1:$RLY_PORT/health" ; echo
systemctl status r510-relay --no-pager -l | head -8