"""Optional infrastructure data sources (pure parsing, no Home Assistant imports).

Every module turns an upstream JSON payload into a list of normalized layer
items. A layer item always carries ``layer``, ``key``, ``title``,
``latitude``, ``longitude`` and ``severity`` (0 = informational, 1 = notable,
2 = serious, 3 = critical); everything else is optional.
"""

from __future__ import annotations

from typing import Any

LAYER_WEBCAMS = "webcams"
LAYER_ROAD = "road"
LAYER_WATER = "water"
LAYER_RADIATION = "radiation"

SEVERITY_LABELS = {0: "Info", 1: "Beachten", 2: "Erhöht", 3: "Kritisch"}


def to_float(value: Any) -> float | None:
    """Return a finite float or None (upstream APIs send numbers as strings)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def valid_point(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def https_url(value: Any) -> str:
    """Return the URL only when it is plain http(s); upstream data is untrusted."""
    url = str(value or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else ""


def first_list(payload: Any, *preferred_keys: str) -> list[dict]:
    """Extract the item list from a payload whose wrapper key may vary."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return [item for item in value if isinstance(item, dict)]
    return []
