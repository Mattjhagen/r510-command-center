"""Refresh the Omaha-metro live traffic-camera manifest for the R510 kiosk.

Sources (all public, no auth, verified 2026-09-13):
  - Nebraska DOT: ArcGIS MapServer, 841 cams state-wide, direct JPEGs
        https://giscat.ne.gov/dot/rest/services/HighwayCamerasDOT/MapServer
  - Iowa DOT:      ArcGIS Hub GeoJSON, 1250 cams, JPEGS + HLS live video
        https://data.iowadot.gov/datasets/...traffic-cameras.geojson
  - WOWT City Cam Network: community weather cams, direct JPEGs
        https://www.wowt.com/weather/citycamnetwork

Output: cameras.json (compact manifest for the kiosk page).
"""

import json
import sys
import urllib.request

NE_QUERY = (
    "https://giscat.ne.gov/dot/rest/services/HighwayCamerasDOT/MapServer/0/query"
    "?where=1%3D1&returnGeometry=true&f=json&outFields=*"
    "&returnGeometry=true&outSR=4326&maxRecordCount=2000"
)
IA_GEOJSON = (
    "https://data.iowadot.gov/datasets/c4063f200a7b4da5826e2ac86c677cf5_0.geojson"
)
IA_GEOJSON_FALLBACK = (
    "https://hub.arcgis.com/api/download/v1/items/c4063f200a7b4da5826e2ac86c677cf5"
    "/geojson?redirect=true&layers=0"
)

# City of Omaha keeps surface-street/city cameras under the NDOT layer; these
# are the neighborhoods worth keeping for the metro view.
NE_CITIES = {"omaha", "bellevue", "papillion", "la vista", "springfield", "sarpy", "ralston", "mo rvr"}

# Council Bluffs / metro Iowa cameras are all titled "CB - ..."
IA_CB_PREFIX = "CB "

WOWT_CAMS = [
    {"id": "wowt-councilbluffs", "name": "Council Bluffs Riverfront", "lat": 41.2589, "lng": -95.8477,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/councilbluffs.jpg", "src": "WOWT"},
    {"id": "wowt-ubt", "name": "WOWT - UBT Tower (Douglas St)", "lat": 41.2590, "lng": -95.9333,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/ubt.jpg", "src": "WOWT"},
    {"id": "wowt-firstnatne", "name": "WOWT - First National North (DT Omaha)", "lat": 41.2588, "lng": -95.9302,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/firstnatne.jpg", "src": "WOWT"},
    {"id": "wowt-firstnatsw", "name": "WOWT - First National South (NE Omaha)", "lat": 41.2560, "lng": -95.9295,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/firstnatsw.jpg", "src": "WOWT"},
    {"id": "wowt-amnatbank", "name": "WOWT - American National Bank (Farnam)", "lat": 41.2566, "lng": -95.9367,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/amnatbank.jpg", "src": "WOWT"},
    {"id": "wowt-blackstoneplaza", "name": "WOWT - Blackstone Plaza", "lat": 41.2627, "lng": -95.9712,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/blackstoneplaza.jpg", "src": "WOWT"},
    {"id": "wowt-childrens", "name": "WOWT - Children's Nebraska (Dodge St)", "lat": 41.2625, "lng": -96.0414,
     "url": "https://webpubcontent.gray.tv/wowt/cameras/childrens.jpg", "src": "WOWT"},
]


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "R510-kiosk-camera-manifest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_ne() -> list[dict]:
    raw = json.loads(_get(NE_QUERY))
    out = []
    for feat in raw.get("features", []):
        a = feat.get("attributes", {})
        g = feat.get("geometry") or {}
        city = (a.get("city") or "").strip().lower()
        url = a.get("PhotoURL")
        if city not in NE_CITIES or not url:
            continue
        name = a.get("name") or a.get("location") or "NE cam"
        if a.get("location"):
            name = f"{name} · {a['location']}"
        out.append({
            "id": a.get("IRISID") or url,
            "name": name,
            "lat": g.get("y"),
            "lng": g.get("x"),
            "url": url,
            "src": "NDOT",
        })
    return [c for c in out if c["lat"] is not None and c["lng"] is not None]


def fetch_ia() -> list[dict]:
    try:
        raw = json.loads(_get(IA_GEOJSON))
    except Exception:
        raw = json.loads(_get(IA_GEOJSON_FALLBACK))
    out = []
    for feat in raw.get("features", []):
        p = feat.get("properties", {})
        desc = p.get("Desc_") or p.get("ImageName") or ""
        if not desc.startswith(IA_CB_PREFIX):
            continue
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        if len(coords) != 2 or not p.get("ImageURL"):
            continue
        out.append({
            "id": str(p.get("device_id", desc)),
            "name": desc,
            "lat": coords[1],
            "lng": coords[0],
            "url": p["ImageURL"],
            "video": p.get("VideoURL") or None,
            "src": "IADOT",
        })
    return out


def main() -> int:
    cams = []
    print("Fetching Nebraska DOT cameras...", flush=True)
    ne = fetch_ne()
    cams += ne
    print(f"  {len(ne)} Nebraska metro cameras", flush=True)
    print("Fetching Iowa DOT cameras...", flush=True)
    ia = fetch_ia()
    cams += ia
    print(f"  {len(ia)} Council Bluffs cameras", flush=True)
    cams += WOWT_CAMS
    print(f"  {len(WOWT_CAMS)} WOWT community cameras", flush=True)
    print(f"TOTAL: {len(cams)}", flush=True)

    out = {"generated": "2026-09-13", "sources": ["NDOT", "IADOT", "WOWT"], "cameras": cams}
    path = sys.argv[1] if len(sys.argv) > 1 else "cameras.json"
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())