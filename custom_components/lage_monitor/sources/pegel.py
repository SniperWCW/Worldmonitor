"""PEGELONLINE (WSV) water levels with flood marks (Meldestufen M_I..M_III).

Docs: https://pegelonline.wsv.de/webservice/dokuRestapi
No key needed. Only stations near Home are queried (radius in km), because the
nationwide list with time series is large.
"""

from __future__ import annotations

from typing import Any

from . import LAYER_WATER, first_list, to_float, valid_point

PEGEL_BASE_URL = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"


def stations_url(lat: float, lon: float, radius_km: float) -> str:
    radius = int(min(max(radius_km, 10), 100))
    return (
        f"{PEGEL_BASE_URL}/stations.json?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&radius={radius}&includeTimeseries=true&includeCurrentMeasurement=true"
        "&includeCharacteristicValues=true"
    )


def flood_level(value: float, marks: dict[str, float]) -> int:
    """0 = below all marks, 1..3 = at or above M_I..M_III."""
    level = 0
    for index, name in enumerate(("m_i", "m_ii", "m_iii"), start=1):
        mark = marks.get(name)
        if mark is not None and value >= mark:
            level = index
    return level


def normalize_stations(payload: Any, *, min_level: int = 1) -> list[dict]:
    """Keep stations whose water level (W) is at or above a flood mark.

    Stations without published flood marks cannot be judged and are skipped.
    """
    items: list[dict] = []
    for station in first_list(payload, "stations"):
        lat = to_float(station.get("latitude"))
        lon = to_float(station.get("longitude"))
        if not valid_point(lat, lon):
            continue
        series = next(
            (
                ts
                for ts in station.get("timeseries") or []
                if isinstance(ts, dict) and str(ts.get("shortname", "")).upper() == "W"
            ),
            None,
        )
        measurement = series.get("currentMeasurement") if series else None
        if not isinstance(measurement, dict):
            continue
        value = to_float(measurement.get("value"))
        if value is None:
            continue
        marks = {
            str(cv.get("shortname", "")).lower(): to_float(cv.get("value"))
            for cv in series.get("characteristicValues") or []
            if isinstance(cv, dict)
        }
        level = flood_level(value, {k: v for k, v in marks.items() if v is not None})
        if level < min_level:
            continue
        water = station.get("water") if isinstance(station.get("water"), dict) else {}
        name = str(station.get("longname") or station.get("shortname") or "Pegel").title()
        unit = str(series.get("unit") or "cm")
        items.append(
            {
                "layer": LAYER_WATER,
                "key": f"pegel:{station.get('uuid') or name}",
                "title": f"{name} ({str(water.get('longname') or '').title()})".replace(" ()", ""),
                "detail": f"Wasserstand {value:g} {unit}, Meldestufe {level}",
                "level": level,
                "value": value,
                "unit": unit,
                "trend": measurement.get("trend"),
                "latitude": lat,
                "longitude": lon,
                "severity": level,  # M_I -> 1, M_II -> 2, M_III -> 3
                "since": str(measurement.get("timestamp") or ""),
                "source": "pegelonline",
            }
        )
    items.sort(key=lambda item: (-item["severity"], item["title"]))
    return items
