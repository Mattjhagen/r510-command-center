#!/usr/bin/env python3
"""
Crime-Camera Bridge Server
Connects R510 Command Center with God's Eye View for real-time crime tracking with camera feeds
"""

import json
import asyncio
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crime-camera-bridge')

# Paths
BASE_DIR = Path(__file__).parent
CRIME_DATA_PATH = BASE_DIR / 'crime.json'
CAMERAS_DATA_PATH = BASE_DIR / 'cameras.json'

# API endpoints
GODS_EYE_API = 'http://localhost:5173/api'
COMMAND_CENTER_API = 'http://localhost:8080'


class CrimeCameraBridge:
    """Bridge between crime data and camera feeds"""

    def __init__(self):
        self.crime_data = []
        self.camera_data = []
        self.active_incidents = {}
        self.camera_assignments = {}

    async def load_data(self):
        """Load crime and camera data from files"""
        try:
            if CRIME_DATA_PATH.exists():
                with open(CRIME_DATA_PATH, 'r') as f:
                    self.crime_data = json.load(f)
                logger.info(f"Loaded {len(self.crime_data)} crime records")

            if CAMERAS_DATA_PATH.exists():
                with open(CAMERAS_DATA_PATH, 'r') as f:
                    data = json.load(f)
                    self.camera_data = data.get('cameras', [])
                logger.info(f"Loaded {len(self.camera_data)} cameras")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters (Haversine formula)"""
        from math import radians, sin, cos, sqrt, atan2

        R = 6371000  # Earth's radius in meters

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def find_nearby_cameras(self, lat: float, lon: float, max_distance: float = 1000) -> List[Dict]:
        """Find cameras within range of a location"""
        nearby = []

        for camera in self.camera_data:
            if not camera.get('lat') or not camera.get('lng'):
                continue

            distance = self.calculate_distance(
                lat, lon,
                camera['lat'], camera['lng']
            )

            if distance <= max_distance:
                camera_info = {
                    **camera,
                    'distance': round(distance, 2),
                    'distance_text': f"{round(distance)}m" if distance < 1000 else f"{round(distance / 1000, 1)}km"
                }
                nearby.append(camera_info)

        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])
        return nearby

    def assign_cameras_to_incident(self, incident_id: str, lat: float, lon: float, priority: str = 'normal'):
        """Assign best cameras to an incident based on location and priority"""
        max_distance = 2000 if priority == 'high' else 1000
        nearby = self.find_nearby_cameras(lat, lon, max_distance)

        # Prioritize cameras based on coverage
        assigned = nearby[:5]  # Assign top 5 closest cameras

        self.camera_assignments[incident_id] = {
            'incident_id': incident_id,
            'cameras': assigned,
            'assigned_at': datetime.now().isoformat(),
            'location': {'lat': lat, 'lon': lon},
            'priority': priority
        }

        logger.info(f"Assigned {len(assigned)} cameras to incident {incident_id}")
        return assigned

    def get_active_incidents(self) -> List[Dict]:
        """Get list of active incidents with camera assignments"""
        active = []

        # Filter for recent incidents (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)

        for crime in self.crime_data:
            timestamp = crime.get('timestamp')
            if timestamp:
                crime_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if crime_time < cutoff_time:
                    continue

            # Add camera assignments if available
            incident_id = crime.get('id', crime.get('case_number'))
            if incident_id in self.camera_assignments:
                crime['cameras'] = self.camera_assignments[incident_id]['cameras']

            active.append(crime)

        return active

    def generate_crime_heatmap(self) -> List[Dict]:
        """Generate heatmap data for crime visualization"""
        heatmap = []

        for crime in self.crime_data:
            if not crime.get('lat') or not crime.get('lon'):
                continue

            heatmap.append({
                'lat': crime['lat'],
                'lon': crime['lon'],
                'weight': self._get_crime_weight(crime),
                'type': crime.get('type', 'unknown'),
                'timestamp': crime.get('timestamp')
            })

        return heatmap

    def _get_crime_weight(self, crime: Dict) -> float:
        """Calculate weight/severity for heatmap"""
        # Weight based on crime type
        weights = {
            'ASSAULT': 3.0,
            'ROBBERY': 3.0,
            'BURGLARY': 2.5,
            'THEFT': 2.0,
            'VANDALISM': 1.5,
            'TRAFFIC': 1.0,
        }

        crime_type = crime.get('type', '').upper()
        base_weight = weights.get(crime_type, 1.5)

        # Boost weight for recent crimes
        timestamp = crime.get('timestamp')
        if timestamp:
            try:
                crime_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hours_ago = (datetime.now() - crime_time).total_seconds() / 3600
                if hours_ago < 1:
                    base_weight *= 2.0
                elif hours_ago < 6:
                    base_weight *= 1.5
            except:
                pass

        return base_weight


# Create bridge instance
bridge = CrimeCameraBridge()


# HTTP handlers
async def handle_status(request):
    """Health check endpoint"""
    return web.json_response({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'stats': {
            'crimes_loaded': len(bridge.crime_data),
            'cameras_loaded': len(bridge.camera_data),
            'active_incidents': len(bridge.active_incidents),
            'camera_assignments': len(bridge.camera_assignments)
        }
    })


async def handle_incidents(request):
    """Get all active incidents"""
    incidents = bridge.get_active_incidents()
    return web.json_response({
        'incidents': incidents,
        'count': len(incidents)
    })


async def handle_nearby_cameras(request):
    """Get cameras near a location"""
    try:
        lat = float(request.query.get('lat', 0))
        lon = float(request.query.get('lon', 0))
        max_distance = float(request.query.get('maxDistance', 1000))

        cameras = bridge.find_nearby_cameras(lat, lon, max_distance)

        return web.json_response({
            'location': {'lat': lat, 'lon': lon},
            'cameras': cameras,
            'count': len(cameras)
        })
    except ValueError as e:
        return web.json_response({'error': 'Invalid parameters'}, status=400)


async def handle_assign_cameras(request):
    """Assign cameras to an incident"""
    try:
        data = await request.json()
        incident_id = data.get('incident_id')
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))
        priority = data.get('priority', 'normal')

        cameras = bridge.assign_cameras_to_incident(incident_id, lat, lon, priority)

        return web.json_response({
            'incident_id': incident_id,
            'cameras_assigned': len(cameras),
            'cameras': cameras
        })
    except (ValueError, KeyError) as e:
        return web.json_response({'error': 'Invalid request data'}, status=400)


async def handle_heatmap(request):
    """Get crime heatmap data"""
    heatmap = bridge.generate_crime_heatmap()
    return web.json_response({
        'heatmap': heatmap,
        'count': len(heatmap)
    })


async def handle_camera_feed(request):
    """Proxy camera feed URL"""
    camera_id = request.match_info.get('camera_id')

    camera = next((c for c in bridge.camera_data if c.get('id') == camera_id), None)
    if not camera:
        return web.json_response({'error': 'Camera not found'}, status=404)

    return web.json_response({
        'camera': camera,
        'feed_url': camera.get('url'),
        'video_url': camera.get('video')
    })


async def on_startup(app):
    """Initialize on startup"""
    logger.info("Starting Crime-Camera Bridge Server")
    await bridge.load_data()


async def on_cleanup(app):
    """Cleanup on shutdown"""
    logger.info("Shutting down Crime-Camera Bridge Server")


def create_app():
    """Create and configure the web application"""
    app = web.Application()

    # Routes
    app.router.add_get('/status', handle_status)
    app.router.add_get('/api/incidents', handle_incidents)
    app.router.add_get('/api/cameras/nearby', handle_nearby_cameras)
    app.router.add_post('/api/cameras/assign', handle_assign_cameras)
    app.router.add_get('/api/heatmap', handle_heatmap)
    app.router.add_get('/api/camera/{camera_id}/feed', handle_camera_feed)

    # Enable CORS
    async def cors_middleware(app, handler):
        async def middleware(request):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        return middleware

    app.middlewares.append(cors_middleware)

    # Startup/cleanup
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Crime-Camera Bridge starting on http://localhost:9000")
    web.run_app(app, host='0.0.0.0', port=9000)
