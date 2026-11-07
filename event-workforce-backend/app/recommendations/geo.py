"""Location helpers for the Recommendations module (pure Python, no DB, easy to unit-test).

The worker profile stores only a preferred_area name, so areas are converted to
coordinates using the fixed list below.

IMPORTANT: coordinates are APPROXIMATE (area centres, roughly +/- 1-2 km, written
from memory). That is fine for a 20 km radius, but please spot-check them on
Google Maps and add any missing Coimbatore areas. Keys are matched ignoring
case, spaces and punctuation, so "R.S. Puram" and "rs puram" are the same.
"""
import math
import re
from typing import Optional

RADIUS_KM = 20.0
EARTH_RADIUS_KM = 6371.0088

_AREAS = {
    "Gandhipuram": (11.0183, 76.9725),
    "RS Puram": (11.0074, 76.9496),
    "Saibaba Colony": (11.0268, 76.9467),
    "Peelamedu": (11.0250, 77.0220),
    "Singanallur": (10.9990, 77.0290),
    "Ukkadam": (10.9893, 76.9606),
    "Town Hall": (10.9936, 76.9594),
    "Race Course": (10.9993, 76.9733),
    "Cross Cut Road": (11.0165, 76.9665),
    "Ganapathy": (11.0420, 76.9900),
    "Ganapathi": (11.0420, 76.9900),
    "Saravanampatti": (11.0788, 76.9951),
    "Saravanampatty": (11.0788, 76.9951),
    "Vadavalli": (11.0252, 76.9031),
    "Thudiyalur": (11.0770, 76.9395),
    "Kovaipudur": (10.9400, 76.9340),
    "Kovaipudhur": (10.9400, 76.9340),
    "Podanur": (10.9611, 76.9908),
    "Sulur": (11.0265, 77.1260),
    "Ramanathapuram": (10.9971, 76.9941),
    "Kuniyamuthur": (10.9550, 76.9640),
    "Hopes College": (11.0235, 77.0003),
    "Hope College": (11.0235, 77.0003),
    "Kalapatti": (11.0810, 77.0260),
    "Vilankurichi": (11.0545, 77.0262),
    "Eachanari": (10.9300, 76.9985),
    "Tatabad": (11.0215, 76.9570),
    "Ondipudur": (11.0000, 77.0460),
}


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


AREA_COORDS = {_norm(name): coords for name, coords in _AREAS.items()}


def resolve_area(name) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for a known area name, else None."""
    return AREA_COORDS.get(_norm(name))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def job_point(job: dict) -> Optional[tuple[float, float]]:
    """Job's own coordinates if present, otherwise the coordinates of its area name."""
    lat, lon = job.get("latitude"), job.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return resolve_area(job.get("area"))


def rank_nearby(jobs: list[dict], origin: tuple[float, float], radius_km: float = RADIUS_KM) -> list[dict]:
    """Keep jobs within radius_km of origin; nearest first, then earliest date.

    Jobs whose location cannot be resolved are skipped. Returns copies with a
    distance_km field and without raw latitude/longitude.
    """
    ranked = []
    for job in jobs:
        point = job_point(job)
        if point is None:
            continue
        dist = haversine_km(origin[0], origin[1], point[0], point[1])
        if dist <= radius_km:
            item = {k: v for k, v in job.items() if k not in ("latitude", "longitude")}
            item["distance_km"] = round(dist, 1)
            ranked.append(item)
    ranked.sort(key=lambda j: (j["distance_km"], j.get("job_date") or ""))
    return ranked