#!/bin/bash
#
# dump1090 Setup Script for RTL-SDR ADS-B Reception
# Sets up local ADS-B receiver for R510 dashboard
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  DUMP1090 ADS-B RECEIVER SETUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update
apt-get install -y \
    rtl-sdr \
    librtlsdr-dev \
    libusb-1.0-0-dev \
    pkg-config \
    build-essential \
    git

# Blacklist DVB-T drivers that conflict with RTL-SDR
echo "🚫 Blacklisting DVB-T drivers..."
cat > /etc/modprobe.d/blacklist-rtl-sdr.conf <<EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

# Clone and build dump1090
echo "🔨 Building dump1090..."
cd /opt
if [ -d "dump1090" ]; then
    rm -rf dump1090
fi

git clone https://github.com/flightaware/dump1090.git
cd dump1090
make

# Create systemd service
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/dump1090.service <<EOF
[Unit]
Description=dump1090 ADS-B Receiver
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dump1090
ExecStart=/opt/dump1090/dump1090 --net --quiet --gain -10 --lat 41.2565 --lon -95.9345
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable dump1090
systemctl start dump1090

# Wait and check status
sleep 3
if systemctl is-active --quiet dump1090; then
    echo "✅ dump1090 service is running"
else
    echo "⚠️  dump1090 service failed to start"
    echo "This is normal if no RTL-SDR device is connected"
    systemctl status dump1090
fi

# Configure nginx proxy (optional)
if command -v nginx &> /dev/null; then
    echo "🌐 Configuring nginx proxy..."

    cat > /etc/nginx/sites-available/dump1090 <<EOF
server {
    listen 8081;
    server_name _;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    location /data/ {
        alias /run/dump1090-fa/;
        add_header Access-Control-Allow-Origin *;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/dump1090 /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    echo "✅ nginx proxy configured on port 8081"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DUMP1090 SETUP COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Aircraft data: http://localhost:8080/data/aircraft.json"
echo "Web interface: http://localhost:8080/"
echo ""
echo "⚠️  Note: Requires RTL-SDR USB dongle to be connected"
echo ""
echo "To test RTL-SDR device:"
echo "  rtl_test"
echo ""
