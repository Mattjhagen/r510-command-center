# LIVE CAMERA FEEDS — Omaha (verified 2026-09-14)

Handoff for the agent wiring live cameras into the r510 kiosk.
All URLs below were curl-verified live from r510 (HTTP 200, `Content-Type: image/jpeg`).

## 1. Nebraska DOT 511 cameras — direct snapshot JPEGs (BEST SOURCE)

Source registry: `https://giscat.ne.gov/dot/rest/services/HighwayCamerasDOT/MapServer/0/query?where=1%3D1&returnGeometry=true&outFields=*&f=json` (841 cams statewide).

Image URL pattern: `https://dot511.nebraska.gov/images/vid-<CODE>-00.jpg`
- Snapshots refresh every few seconds. No auth, no CORS issues, plain `<img>` embeddable.
- `<CODE>` encodes route+camera: e.g. `002006365` = I-80 (route 006) at Dodge & 118th.
- Use `Status == "In Service"` and a non-empty `PhotoURL` to filter. There are ~552 live cams statewide if you want non-Omaha coverage too.

### Omaha / Council Bluffs area (32 cams)

| Camera | Location | URL |
|---|---|---|
| D2-480-2.25 | Dodge St | https://dot511.nebraska.gov/images/vid-002480002-00.jpg |
| D2-480-2.25b | Dodge St | https://dot511.nebraska.gov/images/vid-002480003-00.jpg |
| D2-6-356.91 | W Dodge Rd & 204th St | https://dot511.nebraska.gov/images/VID-002006356-00.jpg |
| D2-6-359.79 | W Dodge Rd & 168th St | https://dot511.nebraska.gov/images/vid-002006359-00.jpg |
| D2-6-360.94 | W Dodge Rd & 156th St | https://dot511.nebraska.gov/images/vid-002006361-00.jpg |
| D2-6-361.93 | W Dodge Rd & 144th St | https://dot511.nebraska.gov/images/vid-002006362-00.jpg |
| D2-6-364.20 | Dodge St @ 118th St | https://dot511.nebraska.gov/images/vid-002006365-00.jpg |
| D2-680-1.29 | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680001-00.jpg |
| D2-680-1.29b | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680002-00.jpg |
| D2-680-1.29c | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680003-00.jpg |
| D2-680-1.29d | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680005-00.jpg |
| D2-680-1.29e | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680006-00.jpg |
| D2-680-1.29f | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680007-00.jpg |
| D2-680-1.29g | I-680 N of W Center Rd | https://dot511.nebraska.gov/images/vid-002680013-00.jpg |
| D2-75-83.24 | US-75 & Cornhusker Rd | https://dot511.nebraska.gov/images/vid-002075083-00.jpg |
| D2-75-84.45 | US-75 & Childs Rd | https://dot511.nebraska.gov/images/vid-002075084-00.jpg |
| D2-75-85.95 | Gilmore Bridge | https://dot511.nebraska.gov/images/vid-002075086-00.jpg |
| D2-75-87.07 | L Street | https://dot511.nebraska.gov/images/vid-002075087-00.jpg |
| D2-80-439.25 | N-370 | https://dot511.nebraska.gov/images/vid-002080439-00.jpg |
| D2-80-440.70 | N-50 | https://dot511.nebraska.gov/images/vid-002080440-00.jpg |
| D2-80-443.01 | 126th Street | https://dot511.nebraska.gov/images/vid-002080443-00.jpg |
| D2-80-445.06 | I-80 & L St | https://dot511.nebraska.gov/images/vid-002080445-00.jpg |
| D2-80-446.26 | I-80 & 108th St | https://dot511.nebraska.gov/images/vid-002080446-00.jpg |
| D2-80-448.48 | 84th Street | https://dot511.nebraska.gov/images/vid-002080448-00.jpg |
| D2-80-449.30 | 72nd Street | https://dot511.nebraska.gov/images/vid-002080449-00.jpg |
| D2-80-450.25 | I-80 & 60th St | https://dot511.nebraska.gov/images/vid-002080450-00.jpg |
| D2-80-452.95 | JFK I-480 | https://dot511.nebraska.gov/images/vid-002080452-00.jpg |
| D2-80-453.15 | Jct I-480 at JFK | https://dot511.nebraska.gov/images/vid-002080453-00.jpg |
| D2-80-453.36 | I-80 & 24th St | https://dot511.nebraska.gov/images/vid-002080454-00.jpg |
| D2-80-454.15 | 13th Street | https://dot511.nebraska.gov/images/vid-002080455-00.jpg |
| D2-80-455.01 | Nebraska-Iowa Memorial Bridge | https://dot511.nebraska.gov/images/vid-002080456-00.jpg |
| D2-Camera 07 | I-480 | https://dot511.nebraska.gov/images/vid-002075091-00.jpg |

## 2. USGS river webcams (public domain, no auth)

| Camera | Location | URL |
|---|---|---|
| NPDodge — NP Dodge Park Webcam | Missouri River, Omaha | https://ne.water.usgs.gov/webcam/images/npdodge.jpg (updates ~5 min) |

Full index: `https://ne.water.usgs.gov/webcam/`

## 3. WOWT CityCam (already used by kiosk)

`https://www.wowt.com/weather/citycamnetwork` — references the same NDOT imagery where applicable; not needed separately.

## 4. Related portals (for future expansion, not direct embeds)

- Nebraska 511 live map: `https://new.511.nebraska.gov/` (and `https://511.nebraska.gov/list/cameras`)
- NDOT travel page: `https://dot.nebraska.gov/travel/`
- Keep Omaha Moving: `https://keepomahamoving.com/` (no cams; confirms 511 link only)

## Notes for the integrating agent

- Refresh strategy: images self-update server-side every ~3-5s; just leave `<img>` tags with the URL and `loading="lazy"` — a periodic `src` re-set or cache-buster query string picks up the new frame. Do NOT fetch/re-bake these into r510.html; they are live remote images (unlike the ArcGIS crime feed which is baked).
- Prefer the 13th Street / JFK I-480 / Bridge shots for "Omaha" character; the I-80 corridor cams show the most traffic activity.
- ArcGIS registry has ~552 live cams statewide if more coverage is wanted (filter `Status == "In Service"`).
- Do NOT commit `.env` or any API keys. These URLs are public and keyless.