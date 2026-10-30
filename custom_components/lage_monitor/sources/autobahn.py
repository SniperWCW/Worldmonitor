"""Autobahn GmbH traffic data (https://autobahn.api.bund.dev/).

Endpoints, one request per road and kind:
``{BASE}/{road}/services/webcam|closure|warning``. Webcams are JPEG snapshots,
not video streams.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from . import LAYER_ROAD, LAYER_WEBCAMS, first_list, https_url, to_float, valid_point

AUTOBAHN_BASE_URL = "https://verkehr.autobahn.de/o/autobahn"
ROAD_RE = re.compile(r"^A\d{1,3}$")
MAX_ROADS = 8  # 3 requests per road; keep the load on the public API small
MAX_ROUTES = 8
DELAY_RE = re.compile(r"Reisezeitverlust:\s*(\d+)\s*Minuten")
SPEED_RE = re.compile(r"Durchschnittsgeschwindigkeit:\s*(\d+)\s*km/h")


def _fold(text: str) -> str:
    """Lower-case and strip diacritics so "Böblingen" matches "boeblingen"/"Boblingen"."""
    text = str(text or "").lower().replace("ß", "ss")
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(src, dst)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def parse_routes(raw: str) -> list[dict]:
    """Parse lines like ``A81 | Feuerbach, Ludwigsburg`` into road + folded keywords.

    Without keywords the whole road counts as a route.
    """
    routes: list[dict] = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        road, _, rest = line.partition("|")
        road = road.strip().upper()
        if not ROAD_RE.match(road):
            continue
        keywords = [k for k in (_fold(part).strip() for part in rest.split(",")) if k]
        routes.append({"road": road, "keywords": keywords})
        if len(routes) >= MAX_ROUTES:
            break
    return routes


def roads_to_fetch(roads: list[str], routes: list[dict]) -> list[str]:
    """Configured roads plus the roads of all routes (deduplicated, capped)."""
    merged = list(roads)
    for route in routes:
        if route["road"] not in merged:
            merged.append(route["road"])
    return merged[:MAX_ROADS]


def mark_routes(items: list[dict], routes: list[dict]) -> list[dict]:
    """Set ``on_route`` on items that belong to one of the user's routes."""
    if not routes:
        return items
    for item in items:
        haystack = _fold(f"{item.get('title', '')} {item.get('subtitle', '')} {item.get('detail_full', item.get('detail', ''))}")
        item["on_route"] = any(
            route["road"] == item.get("road")
            and (not route["keywords"] or any(k in haystack for k in route["keywords"]))
            for route in routes
        )
    return items


def parse_roads(raw: str) -> list[str]:
    """Parse "A8, a81 A6" into ["A8", "A81", "A6"] (validated, deduplicated, capped)."""
    roads: list[str] = []
    for part in re.split(r"[,\s;]+", str(raw or "")):
        road = part.strip().upper()
        if ROAD_RE.match(road) and road not in roads:
            roads.append(road)
    return roads[:MAX_ROADS]


def road_url(road: str, kind: str) -> str:
    if not ROAD_RE.match(road) or kind not in ("webcam", "closure", "warning"):
        raise ValueError(f"invalid autobahn request {road}/{kind}")
    return f"{AUTOBAHN_BASE_URL}/{road}/services/{kind}"


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(part).strip() for part in value if str(part).strip())
    return str(value or "").strip()


def _point(item: dict) -> tuple[float | None, float | None]:
    coordinate = item.get("coordinate")
    if not isinstance(coordinate, dict):
        return None, None
    lat = to_float(coordinate.get("lat"))
    lon = to_float(coordinate.get("long", coordinate.get("lon")))
    return (lat, lon) if valid_point(lat, lon) else (None, None)


def normalize_webcams(payload: Any, road: str) -> list[dict]:
    items: list[dict] = []
    for raw in first_list(payload, "webcam"):
        lat, lon = _point(raw)
        image = https_url(raw.get("imageurl"))
        if lat is None or not image:
            continue
        items.append(
            {
                "layer": LAYER_WEBCAMS,
                "key": f"webcam:{raw.get('identifier') or (lat, lon)}",
                "title": _text(raw.get("title")) or f"{road} Webcam",
                "subtitle": _text(raw.get("subtitle")),
                "road": road,
                "latitude": lat,
                "longitude": lon,
                "severity": 0,
                "image": image,
                "link": https_url(raw.get("linkurl")),
                "source": "autobahn",
            }
        )
    return items


def normalize_traffic(payload: Any, road: str, kind: str) -> list[dict]:
    """Closures (``kind="closure"``) and traffic warnings (``kind="warning"``)."""
    items: list[dict] = []
    for raw in first_list(payload, kind, "warning" if kind == "warning" else "closure"):
        lat, lon = _point(raw)
        if lat is None:
            continue
        blocked = str(raw.get("isBlocked", "")).lower() == "true"
        severity = 2 if kind == "closure" or blocked else 1
        if raw.get("future") in (True, "true"):
            severity = 0  # announced, not in effect yet
        title = _text(raw.get("title")) or road
        full_text = _text(raw.get("description"))
        delay = DELAY_RE.search(full_text)
        speed = SPEED_RE.search(full_text)
        if kind == "warning" and (delay or speed):
            parts = []
            if delay:
                parts.append(f"{delay.group(1)} Min. Verzögerung")
            if speed:
                parts.append(f"Ø {speed.group(1)} km/h")
            detail = ", ".join(parts)
        else:
            detail = full_text[:200]
        items.append(
            {
                "layer": LAYER_ROAD,
                "key": f"{kind}:{raw.get('identifier') or (lat, lon, title)}",
                "title": title,
                "subtitle": _text(raw.get("subtitle")),
                "detail": detail,
                "detail_full": full_text[:600],
                "delay_min": int(delay.group(1)) if delay else None,
                "kind": kind,
                "road": road,
                "latitude": lat,
                "longitude": lon,
                "severity": severity,
                "since": str(raw.get("startTimestamp") or ""),
                "source": "autobahn",
            }
        )
    return items
