#!/usr/bin/env python3
"""
refresh_crime.py — Pull live Omaha Police incidents into crime.json for the kiosk.

Source: Omaha Police Incident Data — DCGIS Open Data Hub
  https://www.arcgis.com/sharing/rest/content/items/15ef780ba6d84414a34c5c89a6500572
  FeatureServer: services1.arcgis.com/tIBLyYZX96jUntYm/.../Omaha_Police_Incident_Data_(View)
Public, no auth, updates continuously via the RMS system. NIBRS-sourced.

Writes crime.json shaped to match the kiosk's existing CRIME_TYPES schema so the
frontend needs no restructuring:
  { generated_at, source, window_hours, count,
    incidents:[{ reportId, type, class, color, urgency, urgencyLabel,
                 lat, lng, location, time, minutesAgo, status, nibrs,
                 precinct, district }] }

Run every few minutes (systemd user timer, see refresh-crime.timer).
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SERVICE = (
    "https://services1.arcgis.com/tIBLyYZX96jUntYm/arcgis/rest/services/"
    "Omaha_Police_Incident_Data_(View)/FeatureServer/0"
)

OUT_FIELDS = ",".join([
    "RB", "dteMidpoint", "NIBRSCategory", "AddressBlock",
    "LatBlock", "LonBlock", "police_districts", "police_precincts",
    "sergeant_areas", "Neighborhood_Associations", "Zip_Codes",
])

DOWNSTREAM = [
    "/home/matt/r510-web/crime.json",
    "/opt/r510-dashboard/crime.json",
]

USER_AGENT = "r510-crime-watch-kiosk/1.0 (+local dashboard collector)"

# NIBRS category -> kiosk crime record. urgencyLabel mirrors the kiosk's HIGH/MEDIUM/LOW.
_MAP = [
    ("homicide",            "ASSAULT",  10),
    ("murder",              "ASSAULT",  10),
    ("kidnapping",          "ASSAULT",  10),
    ("human trafficking",   "ASSAULT",  10),
    ("sex",                 "ASSAULT",  10),
    ("assault",             "ASSAULT",   9),
    ("aggravated assault",  "ASSAULT",  10),
    ("robbery",             "ROBBERY",   9),
    ("extortion",           "ROBBERY",   8),
    ("weapon",              "ROBBERY",   8),
    ("arson",               "VANDALISM", 8),
    ("burglary",            "BURGLARY",  7),
    ("motor vehicle theft", "THEFT",     7),
    ("stolen property",     "THEFT",     5),
    ("larceny",             "THEFT",     5),
    ("counterfeiting",      "THEFT",     5),
    ("embezzlement",        "THEFT",     4),
    ("fraud",               "THEFT",     5),
    ("bribery",             "THEFT",     3),
    ("drug",                "THEFT",     4),
    ("curfew",              "VANDALISM", 2),
    ("disorderly conduc",   "VANDALISM", 3),
    ("trespass",            "VANDALISM", 3),
    ("destruction",         "VANDALISM", 4),
    ("all other",           "VANDALISM", 3),
]

TYPES = {
    "ASSAULT":   {"type": "ASSAULT",   "class": "crime-assault",   "color": "#c96c6c"},
    "ROBBERY":   {"type": "ROBBERY",   "class": "crime-robbery",   "color": "#d4a574"},
    "BURGLARY":  {"type": "BURGLARY",  "class": "crime-burglary",  "color": "#9884c4"},
    "THEFT":     {"type": "THEFT",     "class": "crime-theft",     "color": "#6b9bc4"},
    "VANDALISM": {"type": "VANDALISM", "class": "crime-vandalism", "color": "#6eb3c4"},
}


def _map_category(nibrs):
    """NIBRS string -> (kiosk_kind, urgency). Longest keyword match wins."""
    n = (nibrs or "").lower()
    best = ("VANDALISM", 3, -1)
    for kw, kind, urgency in _MAP:
        if len(kw) > best[2] and kw in n:
            best = (kind, urgency, len(kw))
    return TYPES[best[0]], best[1]


def _urgency_label(u):
    return "HIGH" if u >= 8 else ("MEDIUM" if u >= 6 else "LOW")


def _query_url(where, offset, count):
    params = {
        "where": where,
        "orderByFields": "dteMidpoint DESC",
        "outFields": OUT_FIELDS,
        "returnGeometry": "false",
        "geometryPrecision": 5,
        "resultOffset": str(offset),
        "resultRecordCount": str(count),
        "f": "json",
    }
    return SERVICE + "/query?" + urllib.parse.urlencode(params)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def fetch_incidents(window_hours, cap=120):
    seen = {}
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours)
    where = (
        "dteMidpoint >= timestamp '{start:%Y-%m-%d %H:%M:%S}'"
        " AND dteMidpoint <= CURRENT_TIMESTAMP"
    ).format(start=since)
    offset = 0
    page = 2000
    for _ in range(8):
        data = _get(_query_url(where, offset, page))
        if "error" in data:
            raise RuntimeError("ArcGIS error: %s" % json.dumps(data["error"])[:300])
        feats = data.get("features", [])
        for f in feats:
            a = f.get("attributes") or {}
            lat, lon = a.get("LatBlock"), a.get("LonBlock")
            if lat is None or lon is None:
                continue
            key = a.get("RB")
            if key in seen:
                continue
            ts = a.get("dteMidpoint")
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts / 1000, timezone.utc)
            mins = max(0, int((now - dt).total_seconds() // 60))
            kind, urgency = _map_category(a.get("NIBRSCategory"))
            rec = {
                "reportId": key,
                **kind,
                "urgency": urgency,
                "urgencyLabel": _urgency_label(urgency),
                "lat": round(float(lat), 5),
                "lng": round(float(lon), 5),
                "location": (a.get("AddressBlock") or "").strip() or "Unknown",
                "time": dt.strftime("%H:%M"),
                "occurredAt": dt.isoformat(),
                "minutesAgo": mins,
                "status": "ACTIVE" if mins < 30 else "LOGGED",
                "nibrs": (a.get("NIBRSCategory") or "").strip(),
                "precinct": (a.get("police_precincts") or "").strip(),
                "district": (a.get("police_districts") or "").strip(),
                "neighborhood": (a.get("Neighborhood_Associations") or "").strip(),
            }
            seen[key] = rec
        if len(feats) < page:
            break
        offset += page
    return sorted(seen.values(), key=lambda r: r["occurredAt"], reverse=True)[:cap]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--out", default="crime.json")
    ap.add_argument("--limit", type=int, default=120)
    args = ap.parse_args()

    try:
        incidents = fetch_incidents(args.hours, args.limit)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Omaha Police Incident Data (DCGIS ArcGIS, public)",
            "window_hours": args.hours,
            "count": len(incidents),
            "incidents": incidents,
        }
        with open(args.out, "w") as fh:
            json.dump(payload, fh, indent=1)
        print("OK  %d incidents -> %s" % (len(incidents), args.out))
    except Exception as e:  # noqa: BLE001 — collector must never hard-fail
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Omaha Police Incident Data (DCGIS ArcGIS, public)",
            "window_hours": args.hours,
            "count": 0,
            "incidents": [],
            "error": str(e),
        }
        with open(args.out, "w") as fh:
            json.dump(payload, fh, indent=1)
        print("ERR %s -> %s (empty payload written; kiosk falls back to mock)" % (e, args.out))
        sys.exit(1)

    for path in DOWNSTREAM:
        try:
            with open(args.out) as fh:
                with open(path, "w") as out:
                    out.write(fh.read())
            print("    + copied to %s" % path)
        except OSError as e:
            print("    - skipped %s (%s)" % (path, e))

    bake_kiosk(payload, incidents)


def bake_kiosk(payload, incidents):
    """Bake the crime payload inline into the deployed kiosk HTML.

    The 8421 static server only serves index.html, and the kiosk is a single
    copied file — so, like the camera manifest, fresh data is embedded at build
    time. The frontend prefers KIOSK_CRIME when present and never needs the
    network. Only used when there is real data (empty incidents would merely
    force the mock fallback anyway)."""
    if not incidents:
        print("    - bake skipped (0 real incidents)")
        return
    template = "/home/matt/r510-command-center/index.html"
    marker = "const KIOSK_CRIME = null; /*__CRIME_SPLICE__*/"
    target = "/home/matt/r510-web/r510.html"
    try:
        with open(template) as fh:
            html = fh.read()
        if marker not in html:
            print("    - bake skipped (splice marker missing in %s)" % template)
            return
        blob = "const KIOSK_CRIME = %s;" % json.dumps(payload, separators=(",", ":"))
        html = html.replace(marker, blob, 1)
        with open(target, "w") as fh:
            fh.write(html)
        print("    + baked %d incidents -> %s" % (len(incidents), target))
    except OSError as e:
        print("    - bake failed (%s)" % e)


if __name__ == "__main__":
    main()