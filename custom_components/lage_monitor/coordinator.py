"""Data coordinator for Lage Monitor."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
import logging
import math
import re
import unicodedata
from urllib.parse import quote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT_RADIUS_KM,
    CONF_CUSTOM_PRESS_FEEDS,
    CONF_FOCUS_MODE,
    CONF_INCLUDE_NEWS,
    CONF_INCLUDE_POLICE,
    CONF_INCLUDE_PRESS,
    CONF_LOCAL_KEYWORDS,
    CONF_NEWS_LIMIT,
    CONF_NINA_ARS,
    CONF_POLICE_COUNT_MODE,
    CONF_SCAN_INTERVAL,
    CONF_WARN_AREA,
    CONF_WARN_DWD,
    CONF_WARN_LHP,
    CONF_WARN_MOWAS,
    CONF_WARN_POLICE,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_CUSTOM_PRESS_FEEDS,
    DEFAULT_FOCUS_MODE,
    DEFAULT_LOCAL_KEYWORDS,
    DEFAULT_POLICE_COUNT_MODE,
    DEFAULT_WARN_DWD,
    DEFAULT_WARN_LHP,
    DEFAULT_WARN_MOWAS,
    DEFAULT_WARN_POLICE,
    FOCUS_MODE_LOCAL,
    GERMAN_NEWS_FEEDS,
    KEYWORD_WEIGHTS,
    MILITARY_KEYWORDS,
    POLICE_COUNT_MODE_ALL,
    PRESSEPORTAL_FEEDS,
    WARNUNG_BUND_ASSETS_BASE_URL,
    WARNUNG_BUND_BASE_URL,
)
from .feed import FeedItem, fetch_feed, fetch_json, iso_timestamp

_LOGGER = logging.getLogger(__name__)
COORD_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


@dataclass(slots=True)
class LageSnapshot:
    """Current aggregated situation."""

    germany_score: int
    global_score: int
    active_alerts: int
    police_items: int
    high_priority_items: int
    military_signal_score: int
    stability_index: int
    headlines: list[dict]
    alerts: list[dict]
    map_markers: list[dict]
    military_items: list[dict]
    top_keywords: list[dict]
    sources: list[str]
    source_status: dict[str, dict]
    diagnostics: dict[str, str | int | bool]
    last_update: str
    score_breakdown: dict[str, int]


class LageMonitorCoordinator(DataUpdateCoordinator[LageSnapshot]):
    """Coordinator for data aggregation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._warnung_kreise: dict[str, dict] | None = None
        self._warnung_gemeinden: dict[str, dict] | None = None
        interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, entry.data[CONF_SCAN_INTERVAL])
        )
        super().__init__(
            hass,
            _LOGGER,
            name="Lage Monitor",
            update_interval=interval,
        )

    async def _async_update_data(self) -> LageSnapshot:
        try:
            return await self._build_snapshot()
        except Exception as err:  # noqa: BLE001
            if self.data is not None:
                _LOGGER.warning("Could not update Lage Monitor, keeping previous data: %s", err)
                return self.data
            _LOGGER.warning("Could not update Lage Monitor, using empty snapshot: %s", err)
            return self._empty_snapshot()

    async def _build_snapshot(self) -> LageSnapshot:
        headlines: list[FeedItem] = []
        alerts: list[dict] = []
        all_official_alerts: list[dict] = []
        source_status: dict[str, dict] = {}

        news_limit = self.entry.options.get(CONF_NEWS_LIMIT, self.entry.data[CONF_NEWS_LIMIT])
        configured_ars = self.entry.options.get(CONF_NINA_ARS, self.entry.data.get(CONF_NINA_ARS, ""))
        warn_area = self.entry.options.get(CONF_WARN_AREA, self.entry.data.get(CONF_WARN_AREA, ""))
        police_count_mode = self.entry.options.get(
            CONF_POLICE_COUNT_MODE,
            self.entry.data.get(CONF_POLICE_COUNT_MODE, DEFAULT_POLICE_COUNT_MODE),
        )
        service_filter = {
            "mowasOn": self.entry.options.get(
                CONF_WARN_MOWAS,
                self.entry.data.get(CONF_WARN_MOWAS, DEFAULT_WARN_MOWAS),
            ),
            "dwdOn": self.entry.options.get(
                CONF_WARN_DWD,
                self.entry.data.get(CONF_WARN_DWD, DEFAULT_WARN_DWD),
            ),
            "lhpOn": self.entry.options.get(
                CONF_WARN_LHP,
                self.entry.data.get(CONF_WARN_LHP, DEFAULT_WARN_LHP),
            ),
            "policeOn": self.entry.options.get(
                CONF_WARN_POLICE,
                self.entry.data.get(CONF_WARN_POLICE, DEFAULT_WARN_POLICE),
            ),
        }
        focus_mode = self.entry.options.get(
            CONF_FOCUS_MODE,
            self.entry.data.get(CONF_FOCUS_MODE, DEFAULT_FOCUS_MODE),
        )
        local_keywords = self._parse_csv(
            self.entry.options.get(
                CONF_LOCAL_KEYWORDS,
                self.entry.data.get(CONF_LOCAL_KEYWORDS, DEFAULT_LOCAL_KEYWORDS),
            )
        )
        custom_press_feeds = self._parse_csv(
            self.entry.options.get(
                CONF_CUSTOM_PRESS_FEEDS,
                self.entry.data.get(CONF_CUSTOM_PRESS_FEEDS, DEFAULT_CUSTOM_PRESS_FEEDS),
            )
        )
        alert_radius_km = self.entry.options.get(
            CONF_ALERT_RADIUS_KM,
            self.entry.data.get(CONF_ALERT_RADIUS_KM, DEFAULT_ALERT_RADIUS_KM),
        )
        home_center = self._get_home_coordinates()
        resolved_warn_area = await self._resolve_warn_area(warn_area)

        if self.entry.options.get(CONF_INCLUDE_POLICE, self.entry.data[CONF_INCLUDE_POLICE]):
            official_alerts, official_status = await self._safe_fetch_official_alerts(
                resolved_warn_area,
                service_filter,
            )
            all_official_alerts = official_alerts
            if focus_mode == FOCUS_MODE_LOCAL and resolved_warn_area is not None:
                alerts.extend(official_alerts)
            else:
                alerts.extend(
                    self._filter_alerts_by_radius(official_alerts, home_center, alert_radius_km, focus_mode)
                )
            source_status["warnung_bund"] = official_status

        if self.entry.options.get(CONF_INCLUDE_PRESS, self.entry.data[CONF_INCLUDE_PRESS]):
            for source, url in self._iter_press_feeds(focus_mode):
                items, status = await self._safe_fetch_feed(url, source, max(5, news_limit // 3))
                headlines.extend(items)
                source_status[source] = status
            for index, url in enumerate(custom_press_feeds, start=1):
                source = f"custom_press_{index}"
                items, status = await self._safe_fetch_feed(url, source, max(5, news_limit // 3))
                headlines.extend(items)
                source_status[source] = status

        if (
            focus_mode != FOCUS_MODE_LOCAL
            and self.entry.options.get(CONF_INCLUDE_NEWS, self.entry.data[CONF_INCLUDE_NEWS])
        ):
            for source, url in GERMAN_NEWS_FEEDS.items():
                items, status = await self._safe_fetch_feed(url, source, max(5, news_limit // 3))
                headlines.extend(items)
                source_status[source] = status

        deduped = self._dedupe_items(headlines)
        scored = [self._score_item(item) for item in deduped]
        if focus_mode == FOCUS_MODE_LOCAL:
            scored.extend(self._alerts_to_scored_items(alerts))
        scored = self._apply_focus_filter(scored, focus_mode, local_keywords)
        scored.sort(key=lambda item: item["score"], reverse=True)

        germany_score = min(
            100,
            len(alerts) * 6 + sum(item["score"] for item in scored if item["region"] == "de") // 3,
        )
        global_score = min(100, sum(item["score"] for item in scored[:10]) // 2)
        high_priority = sum(1 for item in scored if item["score"] >= 12)
        police_raw_items = sum(1 for item in deduped if item.source == "presseportal_blaulicht")
        police_relevant_items = sum(
            1
            for item in scored
            if item["source"] == "presseportal_blaulicht" and item["score"] >= 8
        )
        police_items = (
            police_raw_items if police_count_mode == POLICE_COUNT_MODE_ALL else police_relevant_items
        )
        military_items = [item for item in scored if item["military_score"] >= 8][:10]
        military_signal = min(
            100,
            len(military_items) * 7 + sum(item["military_score"] for item in military_items) // 2,
        )
        stability_index = max(
            0,
            min(
                100,
                100
                - (
                    int(germany_score * 0.55)
                    + int(global_score * 0.15)
                    + high_priority * 3
                    + min(military_signal // 4, 20)
                ),
            ),
        )

        keyword_counter: Counter[str] = Counter()
        for item in scored[:20]:
            keyword_counter.update(item["keywords"])

        map_markers = self._build_map_markers(all_official_alerts, home_center)

        return LageSnapshot(
            germany_score=germany_score,
            global_score=global_score,
            active_alerts=len(alerts),
            police_items=police_items,
            high_priority_items=high_priority,
            military_signal_score=military_signal,
            stability_index=stability_index,
            headlines=scored[:news_limit],
            alerts=alerts[: min(len(alerts), 15)],
            map_markers=map_markers,
            military_items=military_items,
            top_keywords=[
                {"keyword": keyword, "count": count}
                for keyword, count in keyword_counter.most_common(8)
            ],
            sources=sorted({item["source"] for item in scored}),
            source_status=source_status,
            diagnostics={
                "configured_nina_ars": configured_ars or "",
                "warn_area": warn_area or "",
                "resolved_warn_area": resolved_warn_area.get("label", "") if resolved_warn_area else "",
                "resolved_warn_area_code": resolved_warn_area.get("dashboard_code", "") if resolved_warn_area else "",
                "degraded": any(status["ok"] is False for status in source_status.values()),
                "focus_mode": focus_mode,
                "local_keywords": ", ".join(local_keywords),
                "alert_radius_km": alert_radius_km,
                "warn_mowas": service_filter["mowasOn"],
                "warn_dwd": service_filter["dwdOn"],
                "warn_lhp": service_filter["lhpOn"],
                "warn_police": service_filter["policeOn"],
                "police_count_mode": police_count_mode,
                "police_raw_items": police_raw_items,
                "police_relevant_items": police_relevant_items,
                "sources_total": len(source_status),
                "sources_ok": sum(1 for status in source_status.values() if status["ok"] is True),
            },
            last_update=iso_timestamp(),
            score_breakdown={
                "alerts": len(alerts) * 6,
                "military_signal": military_signal,
                "high_priority_items": high_priority * 5,
                "police_items": police_items * 2,
            },
        )

    def _empty_snapshot(self) -> LageSnapshot:
        """Return a safe fallback snapshot so entities can still be created."""
        return LageSnapshot(
            germany_score=0,
            global_score=0,
            active_alerts=0,
            police_items=0,
            high_priority_items=0,
            military_signal_score=0,
            stability_index=100,
            headlines=[],
            alerts=[],
            map_markers=[],
            military_items=[],
            top_keywords=[],
            sources=[],
            source_status={},
            diagnostics={
                "configured_nina_ars": self.entry.options.get(CONF_NINA_ARS, self.entry.data[CONF_NINA_ARS]) or "",
                "warn_area": self.entry.options.get(CONF_WARN_AREA, self.entry.data.get(CONF_WARN_AREA, "")) or "",
                "degraded": True,
                "warn_mowas": self.entry.options.get(
                    CONF_WARN_MOWAS,
                    self.entry.data.get(CONF_WARN_MOWAS, DEFAULT_WARN_MOWAS),
                ),
                "warn_dwd": self.entry.options.get(
                    CONF_WARN_DWD,
                    self.entry.data.get(CONF_WARN_DWD, DEFAULT_WARN_DWD),
                ),
                "warn_lhp": self.entry.options.get(
                    CONF_WARN_LHP,
                    self.entry.data.get(CONF_WARN_LHP, DEFAULT_WARN_LHP),
                ),
                "warn_police": self.entry.options.get(
                    CONF_WARN_POLICE,
                    self.entry.data.get(CONF_WARN_POLICE, DEFAULT_WARN_POLICE),
                ),
                "sources_total": 0,
                "sources_ok": 0,
            },
            last_update=iso_timestamp(),
            score_breakdown={
                "alerts": 0,
                "military_signal": 0,
                "high_priority_items": 0,
                "police_items": 0,
            },
        )

    async def _safe_fetch_feed(self, url: str, source: str, limit: int) -> tuple[list[FeedItem], dict]:
        """Fetch a feed without aborting the whole integration on failure."""
        try:
            items = await fetch_feed(self.hass, url, source, limit)
            return items, {"ok": True, "items": len(items), "error": ""}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Feed %s failed: %s", source, err)
            return [], {"ok": False, "items": 0, "error": str(err)}

    async def _safe_fetch_official_alerts(
        self,
        resolved_warn_area: dict | None,
        service_filter: dict[str, bool],
    ) -> tuple[list[dict], dict]:
        """Fetch warnung.bund.de alerts without aborting the whole integration on failure."""
        try:
            alerts = await self._fetch_official_alerts(resolved_warn_area, service_filter)
            return alerts, {"ok": True, "items": len(alerts), "error": ""}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("warnung.bund.de fetch failed: %s", err)
            return [], {"ok": False, "items": 0, "error": str(err)}

    async def _fetch_official_alerts(
        self,
        resolved_warn_area: dict | None,
        service_filter: dict[str, bool],
    ) -> list[dict]:
        alerts: list[dict] = []
        if resolved_warn_area is not None:
            dashboard = await self._fetch_warnung_dashboard(resolved_warn_area["dashboard_code"])
            alerts.extend(self._normalize_dashboard_alert(item) for item in dashboard if isinstance(item, dict))

        if not alerts:
            for channel in self._iter_enabled_warn_channels(service_filter):
                data = await fetch_json(self.hass, f"{WARNUNG_BUND_BASE_URL}/{channel}/mapData.json")
                if not isinstance(data, list):
                    continue
                alerts.extend(
                    self._normalize_map_alert(item, channel)
                    for item in data[:50]
                    if isinstance(item, dict)
                )

        unique: dict[str, dict] = {}
        for alert in alerts:
            key = str(alert.get("id") or alert.get("title"))
            unique[key] = alert

        resolved = [alert for alert in unique.values() if self._is_service_enabled(alert, service_filter)]
        for alert in resolved:
            if alert.get("latitude") is None and alert.get("longitude") is None:
                lat, lon = await self._fetch_warning_centroid(alert.get("id"))
                alert["latitude"] = lat
                alert["longitude"] = lon

        return resolved

    async def _fetch_warnung_dashboard(self, dashboard_code: str) -> list[dict]:
        """Fetch a warnung.bund.de dashboard by 12-digit district code."""
        data = await fetch_json(self.hass, f"{WARNUNG_BUND_BASE_URL}/dashboard/{dashboard_code}.json")
        return data if isinstance(data, list) else []

    def _dedupe_items(self, items: Iterable[FeedItem]) -> list[FeedItem]:
        seen: set[str] = set()
        unique: list[FeedItem] = []
        for item in items:
            key = item.link or item.title.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _score_item(self, item: FeedItem) -> dict:
        haystack = f"{item.title} {item.summary}".lower()
        matched = [keyword for keyword in KEYWORD_WEIGHTS if keyword in haystack]
        military_matched = [keyword for keyword in MILITARY_KEYWORDS if keyword in haystack]
        score = sum(KEYWORD_WEIGHTS[keyword] for keyword in matched)
        military_score = sum(MILITARY_KEYWORDS[keyword] for keyword in military_matched)
        region = "de"
        if item.source == "tagesschau_ausland":
            region = "world"
            score += 2
        if item.source.startswith("presseportal"):
            region = "de"
            score += 3
        if any(token in haystack for token in ("deutschland", "berlin", "hamburg", "nrw", "bayern")):
            region = "de"
            score += 2
        if any(token in haystack for token in ("ukraine", "russland", "china", "usa", "iran", "israel")):
            region = "world"
            score += 2

        return {
            "title": item.title,
            "link": item.link,
            "summary": item.summary,
            "published": item.published,
            "source": item.source,
            "score": min(score, 100),
            "keywords": matched,
            "military_keywords": military_matched,
            "military_score": min(military_score, 100),
            "region": region,
            "latitude": None,
            "longitude": None,
        }

    async def _fetch_warning_centroid(self, identifier: str | None) -> tuple[float | None, float | None]:
        """Fetch warning geometry and return a centroid when available."""
        if not identifier:
            return None, None
        safe_identifier = quote(str(identifier), safe="")
        try:
            geojson = await fetch_json(self.hass, f"{WARNUNG_BUND_BASE_URL}/warnings/{safe_identifier}.geojson")
        except Exception:  # noqa: BLE001
            return None, None
        return self._centroid_from_geojson(geojson)

    async def _get_warnung_catalogs(self) -> tuple[dict[str, dict], dict[str, dict]]:
        """Load and cache district and municipality catalogs from warnung.bund.de."""
        if self._warnung_kreise is None:
            data = await fetch_json(self.hass, f"{WARNUNG_BUND_ASSETS_BASE_URL}/converted_kreise.json")
            self._warnung_kreise = data if isinstance(data, dict) else {}
        if self._warnung_gemeinden is None:
            data = await fetch_json(
                self.hass,
                f"{WARNUNG_BUND_ASSETS_BASE_URL}/converted_gemeinden.json",
            )
            self._warnung_gemeinden = data if isinstance(data, dict) else {}
        return self._warnung_kreise, self._warnung_gemeinden

    async def _resolve_warn_area(self, raw_value: str) -> dict | None:
        """Resolve a user-entered place or district name to a warnung.bund.de dashboard code."""
        value = str(raw_value or "").strip()
        if not value:
            return None

        kreise, gemeinden = await self._get_warnung_catalogs()
        if value in kreise:
            kreis = kreise[value]
            return self._make_warn_area_result(value, kreis.get("NAME") or value, None)

        if value in gemeinden:
            gemeinde = gemeinden[value]
            return self._make_warn_area_result(
                str(gemeinde.get("RS") or "")[:5],
                gemeinde.get("NAME") or value,
                str(gemeinde.get("RS") or ""),
            )

        if re.fullmatch(r"\d{12}", value):
            for gemeinde in gemeinden.values():
                rs = str(gemeinde.get("RS") or "")
                if rs == value:
                    return self._make_warn_area_result(
                        rs[:5],
                        gemeinde.get("NAME") or value,
                        rs,
                    )
            if value[:5] in kreise:
                kreis = kreise[value[:5]]
                return self._make_warn_area_result(value[:5], kreis.get("NAME") or value, None)

        normalized = self._normalize_text(value)
        exact_kreis = self._match_warn_area_by_name(normalized, kreise)
        if exact_kreis is not None:
            code, label = exact_kreis
            return self._make_warn_area_result(code, label, None)

        exact_gemeinde = self._match_warn_area_by_name(normalized, gemeinden, use_rs=True)
        if exact_gemeinde is not None:
            code, label, rs = exact_gemeinde
            return self._make_warn_area_result(code, label, rs)

        return None

    def _make_warn_area_result(
        self,
        kreis_code: str,
        label: str,
        rs: str | None,
    ) -> dict:
        """Build a resolved warn area result."""
        return {
            "label": label,
            "kreis_code": kreis_code,
            "dashboard_code": f"{kreis_code}0000000",
            "rs": rs or "",
        }

    def _match_warn_area_by_name(
        self,
        normalized_query: str,
        source: dict[str, dict],
        *,
        use_rs: bool = False,
    ):
        """Match a query against district or municipality names."""
        exact_match = None
        partial_match = None
        for key, item in source.items():
            label = str(item.get("NAME") or "").strip()
            if not label:
                continue
            normalized_label = self._normalize_text(label)
            if normalized_label == normalized_query:
                if use_rs:
                    rs = str(item.get("RS") or "")
                    return rs[:5], label, rs
                return str(key), label
            if partial_match is None and normalized_query in normalized_label:
                partial_match = (key, item)
            if exact_match is None and normalized_label.startswith(normalized_query):
                exact_match = (key, item)

        selected = exact_match or partial_match
        if selected is None:
            return None

        key, item = selected
        label = str(item.get("NAME") or "").strip() or str(key)
        if use_rs:
            rs = str(item.get("RS") or "")
            return rs[:5], label, rs
        return str(key), label

    def _normalize_dashboard_alert(self, item: dict) -> dict:
        """Normalize a warnung.bund.de dashboard alert entry."""
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        lat, lon = self._extract_lat_lon(item)
        return {
            "id": self._extract_warning_identifier(item),
            "title": payload_data.get("headline")
            or item.get("title")
            or self._extract_localized_title(item),
            "source": self._extract_service_source(item),
            "severity": payload_data.get("severity") or item.get("severity") or "",
            "sent": payload_data.get("sent") or item.get("sent") or item.get("startDate"),
            "link": None,
            "latitude": lat,
            "longitude": lon,
        }

    def _normalize_map_alert(self, item: dict, channel: str) -> dict:
        """Normalize a warnung.bund.de mapData alert entry."""
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        lat, lon = self._extract_lat_lon(item)
        return {
            "id": self._extract_warning_identifier(item),
            "title": payload_data.get("headline")
            or item.get("title")
            or self._extract_localized_title(item),
            "source": channel,
            "severity": payload_data.get("severity") or item.get("severity") or "",
            "sent": payload_data.get("sent") or item.get("sent") or item.get("startDate"),
            "link": None,
            "latitude": lat,
            "longitude": lon,
        }

    def _extract_localized_title(self, item: dict) -> str:
        """Return a localized title when available."""
        title = item.get("i18nTitle")
        if isinstance(title, dict):
            for key in ("de", "en"):
                value = title.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return str(item.get("headline") or item.get("title") or "Warnung")

    def _extract_service_source(self, item: dict) -> str:
        """Determine the service source from provider or identifier fields."""
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        provider = str(
            payload_data.get("provider")
            or item.get("provider")
            or item.get("identifier")
            or item.get("id")
            or ""
        ).lower()
        if "pol" in provider:
            return "police"
        if "dwd" in provider:
            return "dwd"
        if "lhp" in provider:
            return "lhp"
        if "katwarn" in provider:
            return "katwarn"
        if "biwapp" in provider:
            return "biwapp"
        return "mowas"

    def _iter_enabled_warn_channels(self, service_filter: dict[str, bool]) -> list[str]:
        """Return the warnung.bund.de channels enabled by the current service filter."""
        channels: list[str] = []
        if service_filter.get("mowasOn"):
            channels.extend(["mowas", "biwapp", "katwarn"])
        if service_filter.get("dwdOn"):
            channels.append("dwd")
        if service_filter.get("lhpOn"):
            channels.append("lhp")
        if service_filter.get("policeOn"):
            channels.append("police")
        return channels

    def _is_service_enabled(self, alert: dict, service_filter: dict[str, bool]) -> bool:
        """Check whether an alert belongs to an enabled service group."""
        source = str(alert.get("source") or "").lower()
        if source in {"mowas", "biwapp", "katwarn"}:
            return service_filter.get("mowasOn", False)
        if source == "dwd":
            return service_filter.get("dwdOn", False)
        if source == "lhp":
            return service_filter.get("lhpOn", False)
        if source == "police":
            return service_filter.get("policeOn", False)
        return True

    def _extract_lat_lon(self, item: dict) -> tuple[float | None, float | None]:
        """Try to extract coordinates from a map warning payload."""
        direct = self._extract_coordinate_pair(item)
        if direct != (None, None):
            return direct
        nested = self._find_nested_coordinate_pair(item)
        if nested != (None, None):
            return nested
        return None, None

    def _extract_warning_identifier(self, item: dict) -> str | None:
        """Return the best warning identifier we can find for detail/geojson lookups."""
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        for candidate in (
            item.get("identifier"),
            item.get("id"),
            payload.get("identifier"),
            payload.get("id"),
            payload_data.get("identifier"),
            payload_data.get("id"),
            payload_data.get("warningId"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _extract_coordinate_pair(self, value: dict) -> tuple[float | None, float | None]:
        """Extract a lat/lon pair from a single mapping level."""
        for lat_key, lon_key in (
            ("lat", "lon"),
            ("lat", "lng"),
            ("lat", "long"),
            ("latitude", "longitude"),
            ("latitude", "lng"),
            ("Lat", "Lon"),
        ):
            lat = self._to_float_or_none(value.get(lat_key))
            lon = self._to_float_or_none(value.get(lon_key))
            if lat is not None and lon is not None:
                return lat, lon

        coords = value.get("coordinate") or value.get("coordinates")
        if isinstance(coords, str):
            parts = COORD_RE.findall(coords)
            if len(parts) >= 2:
                lat = self._to_float_or_none(parts[0])
                lon = self._to_float_or_none(parts[1])
                if lat is not None and lon is not None:
                    return lat, lon
        if isinstance(coords, list) and len(coords) >= 2:
            first = self._to_float_or_none(coords[0])
            second = self._to_float_or_none(coords[1])
            if first is not None and second is not None:
                if abs(first) <= 90 and abs(second) <= 180:
                    return first, second
                if abs(first) <= 180 and abs(second) <= 90:
                    return second, first

        return None, None

    def _find_nested_coordinate_pair(self, value) -> tuple[float | None, float | None]:
        """Walk nested dict/list structures until a coordinate pair is found."""
        if isinstance(value, dict):
            direct = self._extract_coordinate_pair(value)
            if direct != (None, None):
                return direct
            for child in value.values():
                nested = self._find_nested_coordinate_pair(child)
                if nested != (None, None):
                    return nested
        elif isinstance(value, list):
            for child in value:
                nested = self._find_nested_coordinate_pair(child)
                if nested != (None, None):
                    return nested
        return None, None

    def _to_float_or_none(self, value) -> float | None:
        """Convert a numeric-ish value to float when possible."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    def _normalize_text(self, value: str) -> str:
        """Normalize user-facing place names for matching."""
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())

    def _centroid_from_geojson(self, geojson: dict) -> tuple[float | None, float | None]:
        """Compute a simple centroid from GeoJSON geometry."""
        features = geojson.get("features")
        if not isinstance(features, list) or not features:
            return None, None

        all_points: list[tuple[float, float]] = []
        for feature in features:
            geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
            coords = geometry.get("coordinates")
            if not coords:
                continue
            all_points.extend(self._flatten_coordinates(coords))

        if not all_points:
            return None, None

        avg_lon = sum(point[0] for point in all_points) / len(all_points)
        avg_lat = sum(point[1] for point in all_points) / len(all_points)
        return round(avg_lat, 6), round(avg_lon, 6)

    def _flatten_coordinates(self, coords) -> list[tuple[float, float]]:
        """Flatten GeoJSON coordinate arrays to lon/lat tuples."""
        if (
            isinstance(coords, list)
            and len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            return [(float(coords[0]), float(coords[1]))]

        points: list[tuple[float, float]] = []
        if isinstance(coords, list):
            for child in coords:
                points.extend(self._flatten_coordinates(child))
        return points

    def _build_map_markers(
        self,
        alerts: list[dict],
        home_center: tuple[float | None, float | None],
    ) -> list[dict]:
        """Build nationwide daily map markers plus a home focus marker."""
        markers: list[dict] = []
        todays_alerts = self._filter_alerts_for_today(alerts)
        clustered: dict[tuple[float, float], list[dict]] = {}

        for alert in todays_alerts:
            lat = alert.get("latitude")
            lon = alert.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            key = (round(float(lat) / 0.35) * 0.35, round(float(lon) / 0.5) * 0.5)
            clustered.setdefault(key, []).append(alert)

        for (lat, lon), cluster_alerts in clustered.items():
            top_titles = [item.get("title") or "Warnung" for item in cluster_alerts[:3]]
            sources = sorted({str(item.get("source") or "") for item in cluster_alerts if item.get("source")})
            markers.append(
                {
                    "kind": "cluster",
                    "title": top_titles[0],
                    "source": ", ".join(sources[:3]),
                    "severity": f"{len(cluster_alerts)} Meldungen heute",
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "count": len(cluster_alerts),
                    "titles": top_titles,
                }
            )

        home_lat, home_lon = home_center
        if isinstance(home_lat, (int, float)) and isinstance(home_lon, (int, float)):
            markers.append(
                {
                    "kind": "home",
                    "title": "Home",
                    "source": "zone.home",
                    "severity": "Home Assistant Fokus",
                    "latitude": float(home_lat),
                    "longitude": float(home_lon),
                    "count": 1,
                }
            )

        markers.sort(key=lambda item: (item.get("kind") == "home", item.get("count", 0)), reverse=True)
        return markers

    def _filter_alerts_for_today(self, alerts: list[dict]) -> list[dict]:
        """Keep only alerts from today in the Home Assistant timezone when possible."""
        today = dt_util.now().date()
        filtered: list[dict] = []
        for alert in alerts:
            sent = alert.get("sent")
            if not sent:
                filtered.append(alert)
                continue
            parsed = dt_util.parse_datetime(str(sent))
            if parsed is None:
                filtered.append(alert)
                continue
            local_dt = dt_util.as_local(parsed)
            if local_dt.date() == today:
                filtered.append(alert)
        return filtered

    def _alerts_to_scored_items(self, alerts: list[dict]) -> list[dict]:
        """Convert local alerts into headline-style items for the top list."""
        items: list[dict] = []
        for alert in alerts:
            title = str(alert.get("title") or "Warnung")
            source = str(alert.get("source") or "nina")
            severity = str(alert.get("severity") or "")
            score = 10
            if source == "police":
                score = 14
            elif source == "dwd":
                score = 12
            elif source == "mowas":
                score = 15
            items.append(
                {
                    "title": title,
                    "link": alert.get("link") or "",
                    "summary": severity or f"{source} im Umkreis von Home",
                    "published": str(alert.get("sent") or ""),
                    "source": source,
                    "score": score,
                    "keywords": [],
                    "military_keywords": [],
                    "military_score": 0,
                    "region": "de",
                    "latitude": alert.get("latitude"),
                    "longitude": alert.get("longitude"),
                }
            )
        return items

    def _iter_press_feeds(self, focus_mode: str) -> Iterable[tuple[str, str]]:
        """Return the press feeds relevant for the selected mode."""
        if focus_mode == FOCUS_MODE_LOCAL:
            if "presseportal_blaulicht" in PRESSEPORTAL_FEEDS:
                yield "presseportal_blaulicht", PRESSEPORTAL_FEEDS["presseportal_blaulicht"]
            return
        yield from PRESSEPORTAL_FEEDS.items()

    def _parse_csv(self, value: str) -> list[str]:
        """Parse a comma-separated option into normalized values."""
        return [item.strip() for item in value.split(",") if item.strip()]

    def _apply_focus_filter(self, items: list[dict], focus_mode: str, local_keywords: list[str]) -> list[dict]:
        """Filter and boost items for local focus mode."""
        if focus_mode != FOCUS_MODE_LOCAL or not local_keywords:
            return items

        filtered: list[dict] = []
        keywords_lower = [keyword.lower() for keyword in local_keywords]
        for item in items:
            haystack = f"{item['title']} {item['summary']}".lower()
            if any(keyword in haystack for keyword in keywords_lower):
                item["score"] += 4
                filtered.append(item)
        return filtered

    def _get_home_coordinates(self) -> tuple[float | None, float | None]:
        """Read Home Assistant home coordinates."""
        zone_home = self.hass.states.get("zone.home")
        if zone_home is None:
            return None, None
        lat = zone_home.attributes.get("latitude")
        lon = zone_home.attributes.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
        return None, None

    def _filter_alerts_by_radius(
        self,
        alerts: list[dict],
        home_center: tuple[float | None, float | None],
        radius_km: int,
        focus_mode: str,
    ) -> list[dict]:
        """Filter geocoded alerts around home when local mode is enabled."""
        if focus_mode != FOCUS_MODE_LOCAL:
            return alerts

        home_lat, home_lon = home_center
        if home_lat is None or home_lon is None:
            return alerts

        filtered: list[dict] = []
        for alert in alerts:
            lat = alert.get("latitude")
            lon = alert.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                filtered.append(alert)
                continue
            if self._haversine_km(home_lat, home_lon, float(lat), float(lon)) <= radius_km:
                filtered.append(alert)
        return filtered

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return approximate distance in kilometers."""
        radius = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
