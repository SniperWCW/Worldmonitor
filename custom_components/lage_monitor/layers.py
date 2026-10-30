"""Orchestrate the optional map layers (Autobahn, water levels, radiation).

Pure orchestration: HTTP and caching are injected so this module can be
tested without Home Assistant. ``fetch(key, url, min_interval, max_stale)``
must return a ``fetchcache.FetchResult``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from . import geo
from .fetchcache import FetchResult
from .sources import autobahn, bfs, pegel

Fetch = Callable[..., Awaitable[FetchResult]]  # (key, url, min_interval, max_stale, timeout=None)

MAX_WEBCAMS = 40
MAX_ROAD_ITEMS = 25
MAX_WATER_ITEMS = 25
MAX_RADIATION_ITEMS = 15

TRAFFIC_MIN_INTERVAL = 300
WEBCAM_MIN_INTERVAL = 900
WATER_MIN_INTERVAL = 900
RADIATION_MIN_INTERVAL = 1800
LAYER_MAX_STALE = 3 * 3600


@dataclass(frozen=True, slots=True)
class LayerConfig:
    autobahn_roads: tuple[str, ...] = ()
    water: bool = False
    radiation: bool = False

    @property
    def any_enabled(self) -> bool:
        return bool(self.autobahn_roads) or self.water or self.radiation


def _aggregate_status(results: list[FetchResult], items: int) -> dict[str, Any]:
    failed = [r for r in results if not r.ok]
    errors = "; ".join(sorted({r.error for r in failed if r.error}))
    return {
        "ok": not failed,
        "items": items,
        "error": errors,
        "state": "error" if failed and all(r.value is None for r in failed) else ("stale" if failed else "fresh"),
        "stale": any(r.stale for r in results),
        "age_seconds": int(max((r.age for r in results), default=0)),
        "failures": max((r.failures for r in results), default=0),
    }


def _distance(home: tuple[float | None, float | None], item: dict) -> float:
    if home[0] is None or home[1] is None:
        return 0.0
    return geo.haversine_km(home[0], home[1], item["latitude"], item["longitude"])


def _within(items: list[dict], home, radius_km: float) -> list[dict]:
    """Keep items within the radius of Home; without Home keep only those in Germany."""
    kept = []
    for item in items:
        if home[0] is None or home[1] is None:
            if geo.in_germany(item["latitude"], item["longitude"]):
                kept.append(item)
            continue
        distance = _distance(home, item)
        if distance <= radius_km:
            kept.append({**item, "distance_km": round(distance, 1)})
    return kept


def _dedupe_measures(items: list[dict]) -> list[dict]:
    """One entry per measure: a large roadworks site is reported once per ramp and phase."""
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for item in items:  # already sorted: the first (most severe, nearest) entry wins
        key = (item["kind"], item["road"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


async def _fetch_autobahn(cfg, home, radius_km, fetch: Fetch):
    jobs = [(road, kind) for road in cfg.autobahn_roads for kind in ("webcam", "closure", "warning")]
    results = await asyncio.gather(
        *(
            fetch(
                f"layer:autobahn:{road}:{kind}",
                autobahn.road_url(road, kind),
                WEBCAM_MIN_INTERVAL if kind == "webcam" else TRAFFIC_MIN_INTERVAL,
                LAYER_MAX_STALE,
            )
            for road, kind in jobs
        )
    )
    cams: list[dict] = []
    traffic: list[dict] = []
    for (road, kind), result in zip(jobs, results, strict=True):
        if result.value is None:
            continue
        if kind == "webcam":
            cams.extend(autobahn.normalize_webcams(result.value, road))
        else:
            traffic.extend(autobahn.normalize_traffic(result.value, road, kind))
    cams = sorted(_within(cams, home, radius_km), key=lambda i: i.get("distance_km", 0))[:MAX_WEBCAMS]
    traffic = _within(traffic, home, radius_km * 2)
    traffic = [i for i in traffic if i["severity"] > 0]  # announced future works are noise
    traffic.sort(key=lambda i: (-i["severity"], i.get("distance_km", 0)))
    traffic = _dedupe_measures(traffic)
    items = cams + traffic[:MAX_ROAD_ITEMS]
    return items, _aggregate_status(list(results), len(items))


async def _fetch_water(home, radius_km, fetch: Fetch):
    if home[0] is None or home[1] is None:
        return [], {"ok": True, "items": 0, "error": "Home-Position fehlt", "state": "fresh", "stale": False}
    result = await fetch(
        "layer:pegel", pegel.stations_url(home[0], home[1], radius_km), WATER_MIN_INTERVAL, LAYER_MAX_STALE
    )
    items = pegel.normalize_stations(result.value)[:MAX_WATER_ITEMS] if result.value is not None else []
    return items, _aggregate_status([result], len(items))


async def _fetch_radiation(home, radius_km, fetch: Fetch):
    result = await fetch(
        "layer:odl", bfs.ODL_URL, RADIATION_MIN_INTERVAL, LAYER_MAX_STALE, timeout=bfs.REQUEST_TIMEOUT_S
    )
    items = bfs.normalize_stations(result.value) if result.value is not None else []
    items = _within(items, home, max(radius_km, bfs.MIN_RADIUS_KM))[:MAX_RADIATION_ITEMS]
    return items, _aggregate_status([result], len(items))


async def fetch_layers(
    cfg: LayerConfig,
    home: tuple[float | None, float | None],
    radius_km: float,
    fetch: Fetch,
) -> tuple[list[dict], dict[str, dict]]:
    """Fetch all enabled layers; one failing layer never affects the others."""
    if not cfg.any_enabled:
        return [], {}
    names: list[str] = []
    jobs = []
    if cfg.autobahn_roads:
        names.append("autobahn")
        jobs.append(_fetch_autobahn(cfg, home, radius_km, fetch))
    if cfg.water:
        names.append("pegelonline")
        jobs.append(_fetch_water(home, radius_km, fetch))
    if cfg.radiation:
        names.append("bfs_odl")
        jobs.append(_fetch_radiation(home, radius_km, fetch))
    outcomes = await asyncio.gather(*jobs, return_exceptions=True)
    items: list[dict] = []
    status: dict[str, dict] = {}
    for name, outcome in zip(names, outcomes, strict=True):
        if isinstance(outcome, Exception):
            status[name] = {"ok": False, "items": 0, "error": f"Verarbeitung: {outcome}", "state": "error", "stale": False}
            continue
        layer_items, layer_status = outcome
        items.extend(layer_items)
        status[name] = layer_status
    return items, status
