"""BfS ODL gamma dose rate (https://odlinfo.bfs.de/ODL/EN/service/data-interface/).

Latest 1 h values of ~1,600 stations as GeoJSON (WFS 1.1.0, no key).
Normal background is roughly 0.05-0.18 uSv/h; only clearly elevated stations
are reported. The thresholds are pragmatic awareness values, not official
alarm levels.
"""

from __future__ import annotations

from typing import Any

from . import LAYER_RADIATION, first_list, to_float, valid_point

ODL_URL = (
    "https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature"
    "&typeName=opendata:odlinfo_odl_1h_latest&outputFormat=application/json"
)
ELEVATED_USV_H = 0.30  # severity 1
HIGH_USV_H = 1.00  # severity 2
CRITICAL_USV_H = 10.0  # severity 3


def severity_for(value: float) -> int:
    if value >= CRITICAL_USV_H:
        return 3
    if value >= HIGH_USV_H:
        return 2
    if value >= ELEVATED_USV_H:
        return 1
    return 0


def normalize_stations(payload: Any, *, min_severity: int = 1) -> list[dict]:
    items: list[dict] = []
    for feature in first_list(payload, "features"):
        props = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(props, dict) or not isinstance(geometry, dict):
            continue
        if to_float(props.get("site_status")) not in (None, 1.0):
            continue  # defective / test operation stations produce false positives
        if str(props.get("unit") or "µSv/h").replace("μ", "µ") != "µSv/h":
            continue
        value = to_float(props.get("value"))
        coords = geometry.get("coordinates")
        if value is None or not isinstance(coords, list) or len(coords) < 2:
            continue
        lon, lat = to_float(coords[0]), to_float(coords[1])
        if not valid_point(lat, lon):
            continue
        severity = severity_for(value)
        if severity < min_severity:
            continue
        name = str(props.get("name") or props.get("id") or "Messstation")
        items.append(
            {
                "layer": LAYER_RADIATION,
                "key": f"odl:{props.get('id') or name}",
                "title": f"{name}: {value:g} µSv/h",
                "detail": "Gamma-Ortsdosisleistung (1-h-Wert)",
                "value": value,
                "unit": "µSv/h",
                "latitude": lat,
                "longitude": lon,
                "severity": severity,
                "since": str(props.get("end_measure") or ""),
                "source": "bfs_odl",
            }
        )
    items.sort(key=lambda item: -item["value"])
    return items
