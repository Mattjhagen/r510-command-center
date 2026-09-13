#!/usr/bin/env python3
"""
Aircraft Data Proxy for R510 Command Center
Uses OpenSky Network API to get real aircraft data without hardware
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import time

PORT = 8080

# OpenSky Network API (free, no auth required)
# Bounding box around Omaha, NE (expand to see more aircraft)
OMAHA_BBOX = {
    'lamin': 40.5,  # South
    'lamax': 42.0,  # North
    'lomin': -97.0, # West
    'lomax': -95.0  # East
}

OPENSKY_URL = f"https://opensky-network.org/api/states/all?lamin={OMAHA_BBOX['lamin']}&lomin={OMAHA_BBOX['lomin']}&lamax={OMAHA_BBOX['lamax']}&lomax={OMAHA_BBOX['lomax']}"

class AircraftProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}")

    def do_GET(self):
        if self.path == '/data/aircraft.json':
            try:
                print(f"Fetching aircraft from OpenSky Network...")

                req = urllib.request.Request(
                    OPENSKY_URL,
                    headers={'User-Agent': 'R510-Command-Center/1.0'}
                )

                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read())

                # Convert OpenSky format to dump1090 format
                aircraft_list = []

                if data.get('states'):
                    for state in data['states']:
                        # OpenSky state format:
                        # [0]=icao24, [1]=callsign, [5]=longitude, [6]=latitude,
                        # [7]=baro_altitude, [9]=velocity, [10]=true_track, [13]=squawk

                        if state[5] and state[6]:  # Must have position
                            ac = {
                                'hex': state[0].upper(),
                                'flight': (state[1] or '').strip() or state[0].upper(),
                                'lat': state[6],
                                'lon': state[5],
                                'alt_baro': int(state[7] * 3.28084) if state[7] else None,  # meters to feet
                                'gs': int(state[9] * 1.944) if state[9] else None,  # m/s to knots
                                'track': state[10] if state[10] else 0,
                                'squawk': str(state[13]) if state[13] else None,
                                'category': 'A1',
                                'seen': 0.1
                            }
                            aircraft_list.append(ac)

                # Create dump1090-compatible response
                response_data = {
                    'now': time.time(),
                    'messages': len(aircraft_list) * 100,
                    'aircraft': aircraft_list
                }

                response_json = json.dumps(response_data)

                print(f"✅ Returning {len(aircraft_list)} aircraft")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(response_json.encode())

            except Exception as e:
                print(f"❌ Error: {e}")
                # Return empty aircraft list on error
                error_response = {
                    'now': time.time(),
                    'messages': 0,
                    'aircraft': []
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(error_response).encode())

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'source': 'opensky-network'}).encode())

        else:
            self.send_error(404)

if __name__ == '__main__':
    print('═══════════════════════════════════════════════════════════')
    print('  R510 AIRCRAFT DATA PROXY')
    print('═══════════════════════════════════════════════════════════')
    print(f'📡 Starting on 0.0.0.0:{PORT}')
    print(f'✈️  Data source: OpenSky Network API')
    print(f'📍 Coverage: Omaha, NE area')
    print('')
    print(f'Endpoints:')
    print(f'   http://localhost:{PORT}/data/aircraft.json')
    print(f'   http://localhost:{PORT}/health')
    print('')

    server = HTTPServer(('0.0.0.0', PORT), AircraftProxyHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Stopped')
        server.shutdown()
