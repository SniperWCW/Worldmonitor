"""Trends, risk drivers, summaries, theme scores and data quality."""

from __future__ import annotations

from datetime import timedelta
import math
from typing import Any

from homeassistant.util import dt as dt_util

from .scoring import aggregate_risk, baseline_deviation, cluster_items
from .common import OFFICIAL_ALERT_SOURCES, THEME_KEYWORDS, _assessment_status


class AnalysisMixin:
    """Trends, risk drivers, summaries, theme scores and data quality."""

    def _build_score_trend(self, germany_score: int, stability_index: int) -> dict[str, str | int]:
        """Compare the current snapshot against the previous one kept by the coordinator."""
        previous = self.data
        if previous is None:
            return {"delta": 0, "direction": "stable", "label": "Keine Vergleichsdaten"}

        delta = int(germany_score) - int(previous.germany_score)
        if delta >= 4:
            direction = "up"
            label = f"+{delta} seit letztem Update"
        elif delta <= -4:
            direction = "down"
            label = f"{delta} seit letztem Update"
        else:
            direction = "stable"
            label = f"nahezu stabil ({delta:+d})"

        stability_delta = int(stability_index) - int(previous.stability_index)
        return {
            "delta": delta,
            "direction": direction,
            "label": label,
            "stability_delta": stability_delta,
        }

    def _build_risk_components(
        self,
        items: list[dict],
        region: str,
        alert_risk: int,
        police_risk: int,
        news_risk: int,
        priority_risk: int,
        military_risk: int,
    ) -> dict[str, int]:
        """Map current signals to a website-style U/C/S/I proxy breakdown."""
        region_items = [item for item in items if item.get("region") == region]
        unrest_hits = 0
        conflict_hits = 0
        for item in region_items[:20]:
            text = self._normalize_text(
                f"{item.get('title', '')} {item.get('summary', '')} {' '.join(item.get('keywords', []))}"
            )
            if any(
                keyword in text
                for keyword in ("unruhen", "ausschreit", "protest", "demonstr", "streik", "riot", "blockad")
            ):
                unrest_hits += 1
            if any(
                keyword in text
                for keyword in ("anschlag", "terror", "explosion", "amok", "geisel", "angriff", "attack", "bomb", "krieg")
            ):
                conflict_hits += 1

        return {
            "unrest": min(100, int(police_risk) * 4 + unrest_hits * 8),
            "conflict": min(100, int(priority_risk) * 5 + conflict_hits * 10),
            "military": min(100, int(military_risk)),
            "information": min(100, int(alert_risk) * 2 + int(news_risk) * 3),
        }

    def _build_history_summary(
        self,
        germany_score: int,
        global_score: int,
        local_score: int,
        stability_index: int,
    ) -> dict[str, dict[str, Any]]:
        """Build lightweight 24h and 7d trends from coordinator runtime history."""
        now = dt_util.now()
        self._score_history.append(
            {
                "ts": now,
                "germany_score": int(germany_score),
                "global_score": int(global_score),
                "local_score": int(local_score),
                "stability_index": int(stability_index),
            }
        )
        cutoff = now - timedelta(days=7, hours=1)
        self._score_history = [item for item in self._score_history if item["ts"] >= cutoff]
        self.hass.async_create_task(self._async_save_history())
        return {
            "germany": self._history_for_metric("germany_score", int(germany_score), now),
            "local": self._history_for_metric("local_score", int(local_score), now),
            "world": self._history_for_metric("global_score", int(global_score), now),
            "stability": self._history_for_metric("stability_index", int(stability_index), now),
        }

    def _history_for_metric(
        self,
        key: str,
        current: int,
        now,
    ) -> dict[str, Any]:
        """Return current plus deltas to the closest 24h and 7d sample."""
        past_scores = [
            int(item[key])
            for item in self._score_history[:-1]
            if key in item
        ]
        baseline = baseline_deviation(
            100 - current,
            [100 - value for value in past_scores],
        )
        return {
            "current": current,
            "delta_24h": self._delta_from_history(key, current, now - timedelta(hours=24)),
            "delta_7d": self._delta_from_history(key, current, now - timedelta(days=7)),
            "label_24h": self._delta_label(self._delta_from_history(key, current, now - timedelta(hours=24))),
            "label_7d": self._delta_label(self._delta_from_history(key, current, now - timedelta(days=7))),
            "baseline": baseline,
            "series": self._history_series(key, max_points=28),
        }

    def _history_series(self, key: str, *, max_points: int) -> list[int]:
        """Return an evenly sampled seven-day score series for sparklines."""
        values = [int(item[key]) for item in self._score_history if key in item]
        if len(values) <= max_points:
            return values
        step = (len(values) - 1) / (max_points - 1)
        indexes = [round(index * step) for index in range(max_points)]
        return [values[index] for index in indexes]

    def _delta_from_history(self, key: str, current: int, target_time) -> int | None:
        """Find nearest sample at or before target time and return delta from now."""
        candidates = [item for item in self._score_history if item["ts"] <= target_time and key in item]
        if not candidates:
            return None
        reference = max(candidates, key=lambda item: item["ts"])
        return current - int(reference[key])

    def _delta_label(self, delta: int | None) -> str:
        """Human-readable summary for trend deltas."""
        if delta is None:
            return "Keine Daten"
        if delta > 0:
            return f"+{delta}"
        if delta < 0:
            return str(delta)
        return "0"

    def _build_source_freshness(
        self,
        scored_items: list[dict],
        alerts: list[dict],
        source_status: dict[str, dict],
    ) -> list[dict[str, str | int | None | bool]]:
        """Summarize source health and latest publication age for the dashboard."""
        now = dt_util.now()
        latest_by_source: dict[str, Any] = {}
        for item in scored_items:
            source = str(item.get("source") or "")
            published = self._parse_feed_datetime(item.get("published"))
            if not source or published is None:
                continue
            current = latest_by_source.get(source)
            if current is None or published > current:
                latest_by_source[source] = published

        latest_warn = None
        for alert in alerts:
            sent = dt_util.parse_datetime(str(alert.get("sent") or ""))
            if sent is None:
                continue
            sent_local = dt_util.as_local(sent)
            if latest_warn is None or sent_local > latest_warn:
                latest_warn = sent_local
        if latest_warn is not None:
            latest_by_source["warnung_bund"] = latest_warn

        freshness: list[dict[str, str | int | None | bool]] = []
        for source, status in sorted(source_status.items()):
            latest_dt = latest_by_source.get(source)
            age_minutes = None
            if latest_dt is not None:
                age_minutes = max(0, int((now - dt_util.as_local(latest_dt)).total_seconds() // 60))
            label = "Fehler"
            if status.get("stale"):
                label = "Cache (veraltet)"
            elif status.get("ok") is True:
                if age_minutes is None:
                    label = "Keine Zeitdaten"
                elif age_minutes <= 120:
                    label = "Frisch"
                elif age_minutes <= 720:
                    label = "Verzögert"
                else:
                    label = "Alt"
            freshness.append(
                {
                    "source": source,
                    "ok": bool(status.get("ok")),
                    "items": int(status.get("items") or 0),
                    "age_minutes": age_minutes,
                    "label": label,
                    "error": str(status.get("error") or ""),
                }
            )
        freshness.sort(key=lambda item: (not bool(item["ok"]), (item["age_minutes"] or 10**9)))
        return freshness[:12]

    def _build_risk_drivers(
        self,
        score_breakdown: dict[str, int],
        germany_headlines: list[dict],
        alerts: list[dict],
    ) -> list[dict]:
        """Return the strongest current score drivers in descending order."""
        drivers = [
            {
                "key": "alerts",
                "label": "Amtliche Warnungen",
                "value": int(score_breakdown.get("alerts", 0)),
                "detail": f"{len(alerts)} aktive Warnungen",
            },
            {
                "key": "news_germany",
                "label": "Deutschland-News",
                "value": int(score_breakdown.get("news_germany", 0)),
                "detail": f"{len(germany_headlines)} relevante Deutschland-Treffer",
            },
            {
                "key": "high_priority_germany",
                "label": "Hochpriorisierte Ereignisse",
                "value": int(score_breakdown.get("high_priority_germany", 0)),
                "detail": "Anschlag-, Terror- und Gewaltcluster",
            },
            {
                "key": "police_germany",
                "label": "Polizei- und Blaulichtdruck",
                "value": int(score_breakdown.get("police_germany", 0)),
                "detail": "Relevante Polizeimeldungen in Deutschland",
            },
        ]
        ranked = [driver for driver in drivers if driver["value"] > 0]
        ranked.sort(key=lambda driver: int(driver["value"]), reverse=True)
        return ranked[:4]

    def _build_analysis_summary(
        self,
        germany_score: int,
        global_score: int,
        local_score: int,
        stability_index: int,
        active_alerts: int,
        local_active_alerts: int,
        military_signal_germany: int,
        military_signal_world: int,
        risk_drivers: list[dict],
        germany_headlines: list[dict],
        world_headlines: list[dict],
        local_headlines: list[dict],
        alert_radius_km: int,
        history_summary: dict[str, dict[str, Any]],
        data_quality: dict[str, Any],
    ) -> dict[str, Any]:
        """Build concise Lagebewertungen for Germany, world, and Home radius."""
        top_driver = risk_drivers[0] if risk_drivers else None
        status = _assessment_status(germany_score)
        headline = "Deutschland aktuell ruhig."
        if germany_score < 25:
            headline = "Deutschland aktuell klar angespannt."
        elif germany_score < 40:
            headline = "Deutschland aktuell spürbar belastet."
        elif germany_score < 70:
            headline = "Deutschland aktuell erhöht aufmerksam, aber nicht akut kritisch."

        if stability_index <= 35:
            headline += " Die Stabilität ist deutlich unter Normalniveau."
        elif stability_index <= 55:
            headline += " Die Stabilität bleibt fragil."

        if top_driver is None:
            drivers = "Aktuell fehlen dominante Risikotreiber in den Eingangsdaten."
        else:
            drivers = f"Haupttreiber ist {top_driver['label'].lower()} ({top_driver['detail']})."
            if germany_headlines:
                top_title = str(germany_headlines[0].get("title") or "").strip()
                if top_title:
                    drivers += f" Prägendes Thema: {top_title}"

        if active_alerts >= 10 and military_signal_germany >= 70:
            outlook = "Amtliche Warnlagen sind vorhanden, während das Militärsignal in Deutschland derzeit nicht zusätzlich eskaliert."
        elif military_signal_germany < 50:
            outlook = "Neben der Nachrichtenlage sollte besonders beobachtet werden, ob sich das Deutschland-bezogene Militärsignal weiter verschärft."
        else:
            outlook = "Entscheidend für die nächsten Updates ist, ob die aktuellen Top-Ereignisse in Deutschland weiter eskalieren oder aus den Schlagzeilen fallen."

        germany_summary = {
            "title": "Deutschland",
            "status": status,
            "headline": headline,
            "drivers": drivers,
            "outlook": outlook,
        }
        world_summary = self._build_world_analysis_summary(global_score, military_signal_world, world_headlines)
        local_summary = self._build_local_analysis_summary(
            local_score,
            local_headlines,
            alert_radius_km,
            local_active_alerts,
        )

        summaries = {
            "germany": germany_summary,
            "world": world_summary,
            "local": local_summary,
        }
        for key, summary in summaries.items():
            history = history_summary.get(key, {})
            changes: list[str] = []
            delta = history.get("delta_24h")
            if isinstance(delta, int):
                if delta > 0:
                    changes.append(f"Lagewert in 24 Stunden um {delta} Punkte verbessert.")
                elif delta < 0:
                    changes.append(f"Lagewert in 24 Stunden um {abs(delta)} Punkte verschlechtert.")
                else:
                    changes.append("Lagewert gegenüber vor 24 Stunden unverändert.")
            baseline = history.get("baseline")
            if isinstance(baseline, dict) and baseline.get("label"):
                changes.append(f"Belastung {baseline['label']}.")
            if not changes:
                changes.append("Noch keine belastbare 24-Stunden-Vergleichsbasis vorhanden.")
            summary["changes"] = changes[:2]
            summary["confidence"] = data_quality.get("label", "niedrig")

        return {
            "headline": headline,
            "drivers": drivers,
            "outlook": outlook,
            **summaries,
        }

    def _build_world_analysis_summary(
        self,
        global_score: int,
        military_signal_world: int,
        world_headlines: list[dict],
    ) -> dict[str, Any]:
        """Build a concise global Lagebewertung."""
        status = _assessment_status(global_score)
        headline = "Weltweit aktuell ruhig."
        if global_score < 25:
            headline = "Weltweit aktuell klar angespannt."
        elif global_score < 40:
            headline = "Weltweit aktuell spürbar belastet."
        elif global_score < 70:
            headline = "Weltweit aktuell erhöht aufmerksam."

        if military_signal_world <= 45:
            headline += " Das globale Militärsignal bleibt deutlich belastet."
        elif military_signal_world <= 65:
            headline += " Das globale Militärsignal verdient Beobachtung."

        top_world = world_headlines[0] if world_headlines else None
        if top_world:
            drivers = f"Prägend international: {top_world.get('title') or 'ohne Titel'}"
        else:
            drivers = "Aktuell fehlen dominante internationale Treiber in den Eingangsdaten."

        if len(world_headlines) >= 4:
            outlook = "Maßgeblich ist, ob mehrere internationale Konflikt- oder Krisenthemen parallel hoch bleiben."
        else:
            outlook = "Entscheidend bleibt, ob einzelne Weltlagen in die Breite eskalieren oder wieder an Relevanz verlieren."

        return {
            "title": "Welt",
            "status": status,
            "headline": headline,
            "drivers": drivers,
            "outlook": outlook,
        }

    def _build_local_analysis_summary(
        self,
        local_score: int,
        local_headlines: list[dict],
        alert_radius_km: int,
        active_alerts: int,
    ) -> dict[str, Any]:
        """Build a concise local Lagebewertung around Home."""
        status = _assessment_status(local_score)
        headline = "Im Umkreis aktuell ruhig."
        if local_score < 25:
            headline = "Im Umkreis aktuell klar angespannt."
        elif local_score < 40:
            headline = "Im Umkreis aktuell spürbar belastet."
        elif local_score < 70:
            headline = "Im Umkreis aktuell erhöht aufmerksam."

        top_local = local_headlines[0] if local_headlines else None
        if top_local:
            drivers = f"Prägend im Umkreis von {alert_radius_km} km: {top_local.get('title') or 'ohne Titel'}"
        elif active_alerts:
            drivers = f"Es liegen Warnungen vor, aktuell aber ohne dominante lokale Schwerpunktmeldung im Radius von {alert_radius_km} km."
        else:
            drivers = f"Im Radius von {alert_radius_km} km liegen aktuell keine dominanten Treiber vor."

        if len(local_headlines) >= 3:
            outlook = "Relevant ist, ob sich die lokalen Schwerpunktmeldungen verdichten oder wieder zerstreuen."
        else:
            outlook = "Entscheidend ist, ob neue lokale Warnungen oder Ortsbezug-Events in den Home-Umkreis hineinlaufen."

        return {
            "title": "Umkreis",
            "status": status,
            "headline": headline,
            "drivers": drivers,
            "outlook": outlook,
        }

    def _compute_military_signal(self, items: list[dict]) -> int:
        """Return a deduplicated, time-weighted military risk score."""
        military_items = [
            {**item, "score": int(item.get("military_score") or 0)}
            for item in items
            if int(item.get("military_score") or 0) > 0
        ]
        return self._normalize_aggregate_risk(
            military_items, dt_util.now(), scale=62.0, cap=100
        )

    def _normalize_aggregate_risk(
        self,
        items: list[dict],
        now,
        *,
        scale: float,
        cap: int,
    ) -> int:
        """Map an unbounded aggregate to a stable 0..cap risk value.

        ``aggregate_risk`` removes near-duplicates, rewards independent source
        confirmation and decays old events. Exponential normalization avoids a
        handful of ordinary headlines forcing a permanent 0/100 safety score.
        """
        if not items:
            return 0
        raw = aggregate_risk(items, now)
        normalized = cap * (1.0 - math.exp(-max(0.0, raw) / max(1.0, scale)))
        return min(cap, max(0, round(normalized)))

    def _split_scope_items(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Return independent Germany and world inputs for score aggregation."""
        germany = [
            item
            for item in items
            if item.get("region") == "de" and item.get("source") not in OFFICIAL_ALERT_SOURCES
        ]
        world = [item for item in items if item.get("region") == "world"]
        return germany, world

    def _combine_risks(self, *risks: int) -> int:
        """Combine independent bounded risks without simply adding overlaps."""
        remaining = 1.0
        for risk in risks:
            remaining *= 1.0 - min(100, max(0, int(risk))) / 100.0
        return min(100, max(0, round((1.0 - remaining) * 100)))

    def _build_theme_scores(self, items: list[dict], now) -> dict[str, dict[str, int]]:
        """Build explainable thematic risk/safety scores for one scope."""
        result: dict[str, dict[str, int]] = {}
        for key in THEME_KEYWORDS:
            matches = [item for item in items if key in self._classify_item_themes(item)]
            risk = self._normalize_aggregate_risk(matches, now, scale=48.0, cap=100)
            result[key] = {
                "risk": risk,
                "score": 100 - risk,
                "events": len(cluster_items(matches)),
            }

        military_matches = [item for item in items if "military" in self._classify_item_themes(item)]
        military_risk = self._compute_military_signal(military_matches)
        result["military"] = {
            "risk": military_risk,
            "score": 100 - military_risk,
            "events": len(cluster_items(military_matches)),
        }
        return result

    def _classify_item_themes(self, item: dict) -> list[str]:
        """Return stable theme keys for lists, scores, and map filtering."""
        existing = item.get("themes")
        if isinstance(existing, list):
            return [str(value) for value in existing if str(value) in (*THEME_KEYWORDS, "military")]
        haystack = (
            f"{item.get('title', '')} {item.get('summary', '')} "
            f"{' '.join(item.get('keywords', []))}"
        ).lower()
        themes = [
            key for key, keywords in THEME_KEYWORDS.items()
            if any(keyword in haystack for keyword in keywords)
        ]
        if int(item.get("military_score") or 0) > 0 or item.get("military_keywords"):
            themes.append("military")
        return themes

    def _build_data_quality(
        self,
        source_status: dict[str, dict],
        freshness: list[dict],
        germany_items: list[dict],
        world_items: list[dict],
        local_items: list[dict],
    ) -> dict[str, Any]:
        """Describe source health separately from the situation score."""
        total = len(source_status)
        healthy = sum(
            1 for status in source_status.values()
            if status.get("ok") is True and not status.get("stale")
        )
        stale = sum(1 for status in source_status.values() if status.get("stale"))
        errors = sum(1 for status in source_status.values() if status.get("ok") is False)
        current = sum(
            1 for item in freshness
            if str(item.get("label") or "").lower() in {"frisch", "keine zeitdaten"}
        )
        availability = healthy / total if total else 0.0
        freshness_ratio = current / total if total else 0.0
        all_sources = {
            str(item.get("source") or "")
            for item in (*germany_items, *world_items, *local_items)
            if item.get("source")
        }
        diversity = min(1.0, len(all_sources) / 6.0)
        score = round(100 * (availability * 0.55 + freshness_ratio * 0.25 + diversity * 0.20))
        if score >= 80:
            label = "hoch"
        elif score >= 55:
            label = "mittel"
        else:
            label = "niedrig"
        return {
            "score": score,
            "label": label,
            "healthy_sources": healthy,
            "total_sources": total,
            "stale_sources": stale,
            "error_sources": errors,
            "scope_sources": {
                "germany": len({str(item.get("source") or "") for item in germany_items if item.get("source")}),
                "world": len({str(item.get("source") or "") for item in world_items if item.get("source")}),
                "local": len({str(item.get("source") or "") for item in local_items if item.get("source")}),
            },
        }
