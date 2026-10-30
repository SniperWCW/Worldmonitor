"""Shared constants, helpers and the snapshot type of the coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

_LOGGER = logging.getLogger("custom_components.lage_monitor.coordinator")

COORD_RE = re.compile(r"(-?\d+(?:\.\d+)?)")

OFFICIAL_ALERT_SOURCES = {"mowas", "biwapp", "katwarn", "dwd", "lhp", "police"}

SCORE_HISTORY_VERSION = 4

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": (
        "anschlag", "terror", "angriff", "gewalt", "amok", "geisel",
        "schuesse", "schüsse", "messer", "explosion", "unruhen", "ausschreit",
    ),
    "infrastructure": (
        "ausfall", "blackout", "strom", "energie", "wasser", "trinkwasser",
        "bahn", "brücke", "bruecke", "verkehr", "netz", "internet", "versorgung",
    ),
    "nature": (
        "erdbeben", "hochwasser", "überschwemm", "ueberschwemm", "sturm",
        "orkan", "waldbrand", "wildfire", "hitz", "glatteis", "schnee", "vulkan",
    ),
}

def _assessment_status(score: int) -> dict[str, str]:
    """Return the shared status thresholds used by backend and card."""
    if score >= 70:
        return {"key": "good", "label": "Ruhig"}
    if score >= 40:
        return {"key": "medium", "label": "Aufmerksam"}
    return {"key": "bad", "label": "Belastet"}

@dataclass(slots=True)
class LageSnapshot:
    """Current aggregated situation."""

    germany_score: int
    global_score: int
    local_score: int
    active_alerts: int
    police_items: int
    high_priority_items: int
    military_signal_score: int
    military_signal_germany: int
    military_signal_world: int
    stability_index: int
    germany_risk_score: int
    global_risk_score: int
    local_risk_score: int
    headlines: list[dict]
    local_headlines: list[dict]
    germany_headlines: list[dict]
    world_headlines: list[dict]
    alerts: list[dict]
    local_alerts: list[dict]
    map_markers: list[dict]
    military_items: list[dict]
    military_items_germany: list[dict]
    military_items_local: list[dict]
    military_items_world: list[dict]
    top_keywords: list[dict]
    sources: list[str]
    source_status: dict[str, dict]
    diagnostics: dict[str, str | int | bool]
    last_update: str
    score_breakdown: dict[str, int]
    analysis_summary: dict[str, Any]
    risk_drivers: list[dict]
    score_trend: dict[str, str | int]
    risk_components: dict[str, dict[str, int]]
    history_summary: dict[str, dict[str, Any]]
    source_freshness: list[dict[str, str | int | None | bool]]
    data_quality: dict[str, Any]
    theme_scores: dict[str, dict[str, dict[str, int]]]
    scope_counts: dict[str, dict[str, int]]
    layer_items: list[dict] = field(default_factory=list)
    live_streams: list[dict] = field(default_factory=list)
