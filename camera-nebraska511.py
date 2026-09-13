#!/usr/bin/env python3
"""
Nebraska 511 Camera Proxy for R510 Command Center
Serves real traffic camera images from Nebraska 511
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import time

PORT = 8422

# Nebraska 511 cameras in Omaha metro area
# Camera IDs from https://511.nebraska.gov
OMAHA_CAMERAS = {
    '109': {'name': 'I-80 @ 72nd St', 'lat': 41.2147, 'lng': -96.0166},
    '110': {'name': 'I-480 @ Dodge St', 'lat': 41.25977, 'lng': -95.95377},
    '111': {'name': 'I-680 @ Dodge St', 'lat': 41.2634, 'lng': -96.0947},
    '112': {'name': 'Dodge St @ 90th', 'lat': 41.2625, 'lng': -96.0535},
    '113': {'name': 'I-480 @ Pacific', 'lat': 41.2501, 'lng': -95.9485},
    '114': {'name': 'I-80 @ 84th St', 'lat': 41.2147, 'lng': -96.0345},
    '115': {'name': 'West Dodge @ I-680', 'lat': 41.2686, 'lng': -96.1053},
    '116': {'name': 'Kennedy Fwy @ 30th', 'lat': 41.2856, 'lng': -95.9507},
}

class CameraProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}")

    def do_GET(self):
        if self.path.startswith('/camera?'):
            # Parse camera ID from query string
            try:
                params = dict(p.split('=') for p in self.path.split('?')[1].split('&') if '=' in p)
                camera_id = params.get('id', '109')

                # Fetch image from Nebraska 511 - try direct image URL first
                # The actual camera images are served from a different domain
                camera_url = f'https://lb.511ne.org/cctv/{camera_id}.jpg'

                req = urllib.request.Request(
                    camera_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': 'https://511.nebraska.gov/'
                    }
                )

                with urllib.request.urlopen(req, timeout=5) as response:
                    image_data = response.read()

                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(image_data)

                print(f"✅ Served camera {camera_id}")

            except Exception as e:
                print(f"❌ Error fetching camera: {e}")
                self.send_error(500, str(e))

        elif self.path == '/cameras':
            # Return list of available cameras
            import json

            camera_list = [
                {
                    'id': cam_id,
                    'name': data['name'],
                    'lat': data['lat'],
                    'lng': data['lng']
                }
                for cam_id, data in OMAHA_CAMERAS.items()
            ]

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(camera_list).encode())

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "source": "nebraska-511"}')

        else:
            self.send_error(404)

if __name__ == '__main__':
    print('═══════════════════════════════════════════════════════════')
    print('  R510 CAMERA PROXY - NEBRASKA 511')
    print('═══════════════════════════════════════════════════════════')
    print(f'📹 Starting on 0.0.0.0:{PORT}')
    print(f'📡 Source: Nebraska 511 Traffic Cameras')
    print(f'📍 Cameras: {len(OMAHA_CAMERAS)} Omaha metro locations')
    print('')
    print(f'Endpoints:')
    print(f'   http://localhost:{PORT}/camera?id=109')
    print(f'   http://localhost:{PORT}/cameras')
    print('')

    server = HTTPServer(('0.0.0.0', PORT), CameraProxyHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Stopped')
        server.shutdown()
