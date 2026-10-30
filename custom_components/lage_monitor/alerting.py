"""Detect noteworthy changes between two snapshots (pure Python).

The coordinator fires every returned event as ``lage_monitor_alert`` on the
Home Assistant bus so automations can react, and optionally forwards it to a
notify service. The first snapshot after a restart only seeds the baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVENT_NAME = "lage_monitor_alert"

TYPE_STATUS = "status_change"
TYPE_DROP = "score_drop"
TYPE_OFFICIAL = "new_official_alert"
TYPE_FLOOD = "flood_level"
TYPE_RADIATION = "radiation_elevated"

STATUS_RANK = {"good": 0, "medium": 1, "bad": 2}
STATUS_LABEL = {"good": "Ruhig", "medium": "Aufmerksam", "bad": "Belastet"}


@dataclass(slots=True)
class AlertState:
    """What the previous refresh looked like, plus per-key cooldowns."""

    seeded: bool = False
    status: str = ""
    score: int | None = None
    local_alert_keys: set[str] = field(default_factory=set)
    flood_levels: dict[str, int] = field(default_factory=dict)
    radiation_keys: set[str] = field(default_factory=set)
    last_fired: dict[str, float] = field(default_factory=dict)


def alert_key(alert: dict) -> str:
    return f"{alert.get('source', '')}|{alert.get('identifier') or alert.get('title', '')}"


def detect(
    state: AlertState,
    *,
    now: float,
    status: str,
    score: int,
    local_alerts: list[dict],
    layer_items: list[dict],
    drop_threshold: int,
    cooldown_s: float,
) -> list[dict[str, Any]]:
    """Return new events and update ``state``. Pure apart from mutating ``state``."""
    events: list[dict[str, Any]] = []

    def emit(key: str, event: dict[str, Any]) -> None:
        last = state.last_fired.get(key)
        if last is not None and now - last < cooldown_s:
            return
        state.last_fired[key] = now
        events.append(event)

    alert_keys = {alert_key(a) for a in local_alerts}
    flood = {i["key"]: int(i.get("level") or 0) for i in layer_items if i.get("layer") == "water"}
    radiation = {i["key"] for i in layer_items if i.get("layer") == "radiation"}

    if state.seeded:
        if status != state.status and status in STATUS_RANK and state.status in STATUS_RANK:
            worse = STATUS_RANK[status] > STATUS_RANK[state.status]
            emit(
                f"status:{status}",
                {
                    "type": TYPE_STATUS,
                    "direction": "worse" if worse else "better",
                    "title": f"Lage {'verschlechtert' if worse else 'entspannt'}: {STATUS_LABEL[status]}",
                    "previous_status": state.status,
                    "status": status,
                    "score": score,
                },
            )
        if drop_threshold > 0 and state.score is not None and state.score - score >= drop_threshold:
            emit(
                "drop",
                {
                    "type": TYPE_DROP,
                    "direction": "worse",
                    "title": f"Lagewert fällt um {state.score - score} Punkte auf {score}",
                    "previous_score": state.score,
                    "score": score,
                    "status": status,
                },
            )
        for alert in local_alerts:
            key = alert_key(alert)
            if key not in state.local_alert_keys:
                emit(
                    f"official:{key}",
                    {
                        "type": TYPE_OFFICIAL,
                        "direction": "worse",
                        "title": str(alert.get("title") or "Amtliche Warnung"),
                        "source": str(alert.get("source") or ""),
                        "severity": str(alert.get("severity") or ""),
                    },
                )
        for item in layer_items:
            if item.get("layer") == "water" and flood.get(item["key"], 0) > state.flood_levels.get(item["key"], 0):
                emit(
                    f"flood:{item['key']}:{flood[item['key']]}",
                    {
                        "type": TYPE_FLOOD,
                        "direction": "worse",
                        "title": f"Hochwasser-Meldestufe {flood[item['key']]}: {item['title']}",
                        "level": flood[item["key"]],
                        "detail": item.get("detail", ""),
                    },
                )
            if item.get("layer") == "radiation" and item["key"] not in state.radiation_keys:
                emit(
                    f"radiation:{item['key']}",
                    {
                        "type": TYPE_RADIATION,
                        "direction": "worse",
                        "title": f"Erhöhte Ortsdosisleistung: {item['title']}",
                        "value": item.get("value"),
                    },
                )

    state.seeded = True
    state.status = status
    state.score = score
    state.local_alert_keys = alert_keys
    state.flood_levels = flood
    state.radiation_keys = radiation
    for key in [k for k, t in state.last_fired.items() if now - t > max(cooldown_s * 4, 86400)]:
        del state.last_fired[key]
    return events


def format_message(event: dict[str, Any]) -> str:
    return str(event.get("title") or "Lage Monitor")
