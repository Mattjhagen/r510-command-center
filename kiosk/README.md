# R510 Kiosk Display

Chrome kiosk mode dashboard for r510 server monitoring and training visualization.

## Files

- **server.py** - FastAPI server serving the dashboard (port 7072)
- **r510.html** - Main dashboard HTML with embedded CSS and JavaScript

## Features

### Orbital Animation
- Visual representation of system (YOU ↔ SHAGGOTH)
- Animated particles showing system activity

### Training Monitor (Bottom Overlay)
Two-column live training progress display:

**Left Column - Training Metrics:**
- Step number and progress percentage
- Loss value with quality indicators
- Color-coded status (Excellent/Good/Learning/Early)

**Right Column - AI Commentary:**
- Self-narrating AI describes its own learning
- Context-aware comments based on training progress
- Milestone celebrations
- Conversational, friendly tone

### System Status Panels
- Infrastructure metrics (CPU, RAM, temp, uptime)
- Active model and Ollama status
- Network statistics
- Event log
- Top processes

## API Endpoints

### /api/tty
System metrics including:
- CPU, memory, disk, swap usage
- Temperature
- Uptime and load average
- Process list
- Network stats
- Ollama status

### /api/training
Training progress from ~/train_nightly.log:
- Recent steps (last 10)
- Step number and loss value
- Running status

## Running

### Start Server
```bash
cd ~/r510-web
python3 server.py
```

Server runs on http://localhost:7072

### Start Chrome Kiosk
```bash
DISPLAY=:0 chromium --kiosk --no-sandbox --app=http://localhost:7072
```

## Updates (Sept 13, 2026)

- Added real-time training monitor overlay
- Two-column layout with AI self-narration
- Ollama status detection
- Training API endpoint
- Automatic updates every 3 seconds
- Fade animations for text
- Bottom-up scroll (newest at bottom)

## Dependencies

- Python 3.12+
- FastAPI
- Uvicorn
- psutil
- requests (for Ollama checks)
