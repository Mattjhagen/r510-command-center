#!/bin/bash
#
# Install R510 Crime Camera systemd services
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root (use sudo)"
    exit 1
fi

log "Installing R510 Crime Camera systemd services..."

# Create log directory
mkdir -p /var/log
touch /var/log/crime-camera-bridge.log
touch /var/log/gods-eye-view.log
chown matt:matt /var/log/crime-camera-bridge.log
chown matt:matt /var/log/gods-eye-view.log
success "Log files created"

# Copy service files
log "Installing service files..."
cp "$SCRIPT_DIR/crime-camera-bridge.service" /etc/systemd/system/
cp "$SCRIPT_DIR/gods-eye-view.service" /etc/systemd/system/
cp "$SCRIPT_DIR/r510-crime-camera.target" /etc/systemd/system/
success "Service files installed"

# Set permissions
chmod 644 /etc/systemd/system/crime-camera-bridge.service
chmod 644 /etc/systemd/system/gods-eye-view.service
chmod 644 /etc/systemd/system/r510-crime-camera.target

# Reload systemd
log "Reloading systemd daemon..."
systemctl daemon-reload
success "Systemd reloaded"

# Enable services
log "Enabling services..."
systemctl enable crime-camera-bridge.service
systemctl enable gods-eye-view.service
systemctl enable r510-crime-camera.target
success "Services enabled"

# Start services
log "Starting services..."
systemctl start r510-crime-camera.target
sleep 3

# Check status
echo ""
log "Service Status:"
echo ""

systemctl status crime-camera-bridge.service --no-pager -l || true
echo ""
systemctl status gods-eye-view.service --no-pager -l || true
echo ""

# Check if services are running
if systemctl is-active --quiet crime-camera-bridge.service; then
    success "Crime-Camera Bridge is running"
else
    error "Crime-Camera Bridge failed to start"
    journalctl -u crime-camera-bridge.service -n 20 --no-pager
fi

if systemctl is-active --quiet gods-eye-view.service; then
    success "God's Eye View is running"
else
    error "God's Eye View failed to start"
    journalctl -u gods-eye-view.service -n 20 --no-pager
fi

# Display URLs
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     R510 Crime Camera Services Installed              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Services:${NC}"
echo -e "  🔗 Crime-Camera Bridge: ${GREEN}http://localhost:9000${NC}"
echo -e "  🌐 God's Eye View:     ${GREEN}http://localhost:4173${NC}"
echo ""
echo -e "${CYAN}Management Commands:${NC}"
echo -e "  Start all:     ${YELLOW}sudo systemctl start r510-crime-camera.target${NC}"
echo -e "  Stop all:      ${YELLOW}sudo systemctl stop r510-crime-camera.target${NC}"
echo -e "  Restart all:   ${YELLOW}sudo systemctl restart r510-crime-camera.target${NC}"
echo -e "  Status:        ${YELLOW}sudo systemctl status r510-crime-camera.target${NC}"
echo ""
echo -e "${CYAN}Individual Service Commands:${NC}"
echo -e "  Bridge status:  ${YELLOW}sudo systemctl status crime-camera-bridge${NC}"
echo -e "  Bridge logs:    ${YELLOW}sudo journalctl -u crime-camera-bridge -f${NC}"
echo -e "  GEV status:     ${YELLOW}sudo systemctl status gods-eye-view${NC}"
echo -e "  GEV logs:       ${YELLOW}sudo journalctl -u gods-eye-view -f${NC}"
echo ""
echo -e "${CYAN}Both services will now start automatically on boot.${NC}"
echo ""
