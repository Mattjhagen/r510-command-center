#!/bin/bash
# Bootstrap the R510 audio relay on 911-console (run as root).
# Picks a reachable Broadcastify CDN host, installs the relay as a systemd
# service bound to this machine's Tailscale IP on port 8425.
set -e

echo "==> picking Broadcastify CDN source reachable from here..."
SRC=""
for host in cdnstream1 cdnstream2 cdnstream3; do
  out=$(curl -s -o /dev/null -w "%{http_code} %{content_type}" -m 20 -A "Mozilla/5.0" "https://$host.broadcastify.com/25460" || echo "000 -")
  echo "   $host -> $out"
  code=$(echo "$out" | awk '{print $1}')
  ctype=$(echo "$out" | awk '{print $2}')
  if [ "$code" = "200" ] && echo "$ctype" | grep -qiE "audio|mpeg|octet"; then
    SRC="https://$host.broadcastify.com/25460"
    break
  fi
done
if [ -z "$SRC" ]; then
  echo "   none of the cdnstream hosts returned audio; trying pull-style broadcastify.com URLs..."
  for u in "https://www.broadcastify.com/listen/feed/25460" "https://audio.broadcastify.com/25460.mp3"; do
    out=$(curl -s -o /dev/null -w "%{http_code} %{content_type}" -m 20 -A "Mozilla/5.0" "$u" || echo "000 -")
    echo "   $u -> $out"
    code=$(echo "$out" | awk '{print $1}')
    ctype=$(echo "$out" | awk '{print $2}')
    if [ "$code" = "200" ] && echo "$ctype" | grep -qiE "audio|mpeg|octet"; then
      SRC="$u"
      break
    fi
  done
fi
[ -n "$SRC" ] || { echo "!! no reachable CDN source found -- stopping"; exit 1; }
echo "=> using $SRC"

mkdir -p /opt/r510-relay
curl -s -o /opt/r510-relay/audio-relay.py "http://100.103.3.35:8899/audio-relay.py"
python3 -m py_compile /opt/r510-relay/audio-relay.py || { echo "!! relay download/compile failed"; exit 1; }

MYIP=$(tailscale ip -4 | grep -v fd | head -1)
cat > /etc/systemd/system/r510-relay.service <<EOF
[Unit]
Description=R510 audio relay (Broadcastify -> tailnet)
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/r510-relay/audio-relay.py
Environment=RLY_SOURCE=$SRC
Environment=RLY_BIND=$MYIP
Environment=RLY_PORT=8425
Environment=RLY_TAIL_BYTES=24576
Environment=RLY_STALL=15
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now r510-relay 2>/dev/null || systemctl restart r510-relay
sleep 4
echo "==> relay health:"
curl -s -m 6 "http://127.0.0.1:8425/health"; echo
echo "DONE -> relay at http://$MYIP:8425/"