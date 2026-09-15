#!/bin/bash
#
# Start Crime-Camera Integration
# Launches God's Eye View + Crime-Camera Bridge + Command Center
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check Node.js
    if ! command -v node &> /dev/null; then
        error "Node.js is not installed. Please install Node.js 24+ or 26+"
        exit 1
    fi

    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VERSION" -lt 24 ]; then
        error "Node.js version $NODE_VERSION is too old. Please upgrade to 24+ or 26+"
        exit 1
    fi
    success "Node.js $(node -v) detected"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi
    success "Python $(python3 --version) detected"

    # Check Python dependencies
    if ! python3 -c "import aiohttp" &> /dev/null; then
        warn "aiohttp not found. Installing..."
        pip3 install aiohttp
    fi
    success "Python dependencies OK"

    # Check data files
    if [ ! -f "$SCRIPT_DIR/crime.json" ]; then
        warn "crime.json not found. Creating empty file..."
        echo "[]" > "$SCRIPT_DIR/crime.json"
    fi

    if [ ! -f "$SCRIPT_DIR/cameras.json" ]; then
        error "cameras.json not found. Cannot proceed."
        exit 1
    fi
    success "Data files OK"
}

# Check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 1
    else
        return 0
    fi
}

# Kill existing processes
cleanup() {
    log "Cleaning up existing processes..."

    # Kill existing bridge server
    pkill -f "crime-camera-bridge.py" || true

    # Kill existing Vite dev server
    pkill -f "vite.*gods-eye-view" || true

    # Wait for ports to be released
    sleep 2

    success "Cleanup complete"
}

# Start Crime-Camera Bridge
start_bridge() {
    log "Starting Crime-Camera Bridge on port 9000..."

    if ! check_port 9000; then
        error "Port 9000 is already in use"
        exit 1
    fi

    cd "$SCRIPT_DIR"
    nohup python3 crime-camera-bridge.py > bridge.log 2>&1 &
    BRIDGE_PID=$!

    # Wait for bridge to start
    sleep 3

    if ! ps -p $BRIDGE_PID > /dev/null; then
        error "Bridge server failed to start. Check bridge.log for details."
        tail -n 20 bridge.log
        exit 1
    fi

    success "Crime-Camera Bridge started (PID: $BRIDGE_PID)"
    echo $BRIDGE_PID > bridge.pid
}

# Start God's Eye View
start_gods_eye() {
    log "Starting God's Eye View on port 4173..."

    if ! check_port 4173; then
        error "Port 4173 is already in use"
        exit 1
    fi

    cd "$SCRIPT_DIR/gods-eye-view"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        log "Installing npm dependencies (first time only)..."
        npm install
    fi

    # Start Vite dev server in background with port 4173
    PORT=4173 nohup npm run dev > ../gods-eye.log 2>&1 &
    GODS_EYE_PID=$!

    # Wait for server to start
    log "Waiting for God's Eye View to start..."
    for i in {1..30}; do
        if curl -s http://localhost:4173 > /dev/null; then
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:4173 > /dev/null; then
        error "God's Eye View failed to start. Check gods-eye.log for details."
        tail -n 20 ../gods-eye.log
        exit 1
    fi

    success "God's Eye View started (PID: $GODS_EYE_PID)"
    echo $GODS_EYE_PID > ../gods-eye.pid
    cd "$SCRIPT_DIR"
}

# Display status
show_status() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     Crime-Camera Integration Started Successfully     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Services:${NC}"
    echo -e "  🌐 God's Eye View:     ${GREEN}http://localhost:4173${NC}"
    echo -e "  🔗 Crime-Camera Bridge: ${GREEN}http://localhost:9000${NC}"
    echo -e "  📊 Bridge Status:      ${GREEN}http://localhost:9000/status${NC}"
    echo -e "  📹 CCTV Sources:       ${GREEN}http://localhost:4173/api/cctv/sources${NC}"
    echo -e "  🚨 Crime Incidents:    ${GREEN}http://localhost:9000/api/incidents${NC}"
    echo ""
    echo -e "${CYAN}Log Files:${NC}"
    echo -e "  Bridge: $SCRIPT_DIR/bridge.log"
    echo -e "  God's Eye View: $SCRIPT_DIR/gods-eye.log"
    echo ""
    echo -e "${CYAN}Camera Sources:${NC}"
    CAMERA_COUNT=$(jq '.cameras | length' cameras.json 2>/dev/null || echo "unknown")
    echo -e "  Total cameras: ${GREEN}$CAMERA_COUNT${NC}"
    echo ""
    echo -e "${CYAN}To stop all services:${NC}"
    echo -e "  ./stop-crime-camera-integration.sh"
    echo ""
}

# Main execution
main() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║    R510 Crime-Camera Integration Startup           ║"
    echo "║    God's Eye View + Crime Tracking                 ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    check_prerequisites
    cleanup
    start_bridge
    start_gods_eye
    show_status

    # Keep script running and show logs
    log "Press Ctrl+C to stop all services"

    trap 'echo ""; log "Shutting down..."; cleanup; exit 0' INT TERM

    # Follow logs
    tail -f bridge.log gods-eye.log
}

main "$@"
