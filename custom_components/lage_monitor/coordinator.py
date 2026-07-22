"""Data coordinator for Lage Monitor."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
import logging
import re
from urllib.parse import quote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ALERTS,
    ATTR_HEADLINES,
    ATTR_LAST_UPDATE,
    ATTR_MAP_MARKERS,
    ATTR_MILITARY_ITEMS,
    ATTR_SCORE_BREAKDOWN,
    ATTR_SOURCES,
    ATTR_TOP_KEYWORDS,
    CONF_INCLUDE_NEWS,
    CONF_INCLUDE_POLICE,
    CONF_INCLUDE_PRESS,
    CONF_NEWS_LIMIT,
    CONF_NINA_ARS,
    CONF_POLICE_COUNT_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_POLICE_COUNT_MODE,
    GERMAN_NEWS_FEEDS,
    KEYWORD_WEIGHTS,
    MILITARY_KEYWORDS,
    NINA_BASE_URL,
    POLICE_COUNT_MODE_ALL,
    POLICE_COUNT_MODE_RELEVANT,
    PRESSEPORTAL_FEEDS,
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
        interval = timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, entry.data[CONF_SCAN_INTERVAL]))
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
        source_status: dict[str, dict] = {}
        news_limit = self.entry.options.get(CONF_NEWS_LIMIT, self.entry.data[CONF_NEWS_LIMIT])
        configured_ars = self.entry.options.get(CONF_NINA_ARS, self.entry.data[CONF_NINA_ARS])
        police_count_mode = self.entry.options.get(
            CONF_POLICE_COUNT_MODE,
            self.entry.data.get(CONF_POLICE_COUNT_MODE, DEFAULT_POLICE_COUNT_MODE),
        )

        if self.entry.options.get(CONF_INCLUDE_POLICE, self.entry.data[CONF_INCLUDE_POLICE]):
            nina_alerts, nina_status = await self._safe_fetch_nina_alerts(configured_ars)
            alerts.extend(nina_alerts)
            source_status["nina"] = nina_status

        if self.entry.options.get(CONF_INCLUDE_PRESS, self.entry.data[CONF_INCLUDE_PRESS]):
            for source, url in PRESSEPORTAL_FEEDS.items():
                items, status = await self._safe_fetch_feed(url, source, max(5, news_limit // 3))
                headlines.extend(items)
                source_status[source] = status

        if self.entry.options.get(CONF_INCLUDE_NEWS, self.entry.data[CONF_INCLUDE_NEWS]):
            for source, url in GERMAN_NEWS_FEEDS.items():
                items, status = await self._safe_fetch_feed(url, source, max(5, news_limit // 3))
                headlines.extend(items)
                source_status[source] = status

        deduped = self._dedupe_items(headlines)
        scored = [self._score_item(item) for item in deduped]
        scored.sort(key=lambda item: item["score"], reverse=True)

        germany_score = min(
            100,
            len(alerts) * 6
            + sum(item["score"] for item in scored if item["region"] == "de") // 3,
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
            police_raw_items
            if police_count_mode == POLICE_COUNT_MODE_ALL
            else police_relevant_items
        )
        military_items = [item for item in scored if item["military_score"] >= 8][:10]
        military_signal = min(
            100,
            len(military_items) * 7
            + sum(item["military_score"] for item in military_items) // 2,
        )
        stability_index = max(
            0,
            min(
                100,
                100 - (
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

        map_markers = self._build_markers(alerts, scored[: min(news_limit, 12)])

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
                "degraded": any(status["ok"] is False for status in source_status.values()),
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
                "degraded": True,
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

    async def _safe_fetch_nina_alerts(self, ars: str) -> tuple[list[dict], dict]:
        """Fetch NINA alerts without aborting the whole integration on failure."""
        try:
            alerts = await self._fetch_nina_alerts(ars)
            return alerts, {"ok": True, "items": len(alerts), "error": ""}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("NINA alert fetch failed: %s", err)
            return [], {"ok": False, "items": 0, "error": str(err)}

    async def _fetch_nina_alerts(self, ars: str) -> list[dict]:
        alerts: list[dict] = []
        if ars:
            dashboard = await self._fetch_nina_dashboard(ars)
            if isinstance(dashboard, list):
                for item in dashboard:
                    if not isinstance(item, dict):
                        continue
                    alerts.append(
                        {
                            "id": item.get("id") or item.get("identifier"),
                            "title": item.get("title") or item.get("headline"),
                            "source": item.get("provider") or "nina_dashboard",
                            "severity": item.get("severity") or item.get("msgType"),
                            "sent": item.get("sent"),
                            "link": item.get("payload", {}).get("data") if isinstance(item.get("payload"), dict) else None,
                            "latitude": None,
                            "longitude": None,
                        }
                    )

        for channel in ("mowas", "police", "dwd", "lhp"):
            data = await fetch_json(self.hass, f"{NINA_BASE_URL}/{channel}/mapData.json")
            if not isinstance(data, list):
                continue
            for item in data[:50]:
                if not isinstance(item, dict):
                    continue
                payload = item.get("payload") or {}
                alerts.append(
                    {
                        "id": item.get("id"),
                        "title": payload.get("data", {}).get("headline")
                        if isinstance(payload.get("data"), dict)
                        else item.get("title"),
                        "source": channel,
                        "severity": payload.get("data", {}).get("severity")
                        if isinstance(payload.get("data"), dict)
                        else None,
                        "sent": payload.get("data", {}).get("sent")
                        if isinstance(payload.get("data"), dict)
                        else None,
                        "link": None,
                        "latitude": self._extract_lat_lon(item)[0],
                        "longitude": self._extract_lat_lon(item)[1],
                    }
                )

        unique: dict[str, dict] = {}
        for alert in alerts:
            key = str(alert.get("id") or alert.get("title"))
            unique[key] = alert
        resolved = list(unique.values())
        for alert in resolved:
            if alert.get("latitude") is None and alert.get("longitude") is None:
                lat, lon = await self._fetch_warning_centroid(alert.get("id"))
                alert["latitude"] = lat
                alert["longitude"] = lon
        return resolved

    async def _fetch_nina_dashboard(self, ars: str):
        """Fetch a dashboard, retrying with an 8-digit AGS fallback when needed."""
        candidates = [ars]
        normalized = ars.strip()
        if len(normalized) == 12 and normalized[:8] not in candidates:
            candidates.append(normalized[:8])

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                return await fetch_json(self.hass, f"{NINA_BASE_URL}/dashboard/{candidate}.json")
            except Exception as err:  # noqa: BLE001
                last_error = err
                _LOGGER.warning("NINA dashboard lookup failed for %s: %s", candidate, err)

        if last_error is not None:
            raise last_error
        return []

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
            geojson = await fetch_json(self.hass, f"{NINA_BASE_URL}/warnings/{safe_identifier}.geojson")
        except Exception:  # noqa: BLE001
            return None, None
        return self._centroid_from_geojson(geojson)

    def _extract_lat_lon(self, item: dict) -> tuple[float | None, float | None]:
        """Try to extract coordinates from a map warning payload."""
        for lat_key, lon_key in (
            ("lat", "lon"),
            ("latitude", "longitude"),
            ("Lat", "Lon"),
        ):
            lat = item.get(lat_key)
            lon = item.get(lon_key)
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                return float(lat), float(lon)

        coords = item.get("coordinate") or item.get("coordinates")
        if isinstance(coords, str):
            parts = COORD_RE.findall(coords)
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])

        return None, None

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

    def _build_markers(self, alerts: list[dict], headlines: list[dict]) -> list[dict]:
        """Build marker data for frontend maps."""
        markers: list[dict] = []

        for alert in alerts:
            lat = alert.get("latitude")
            lon = alert.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            markers.append(
                {
                    "kind": "alert",
                    "title": alert.get("title") or "Warnung",
                    "source": alert.get("source"),
                    "severity": alert.get("severity"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
            )

        # Headlines are currently not geocoded, but we keep the structure for future enrichment.
        for headline in headlines:
            lat = headline.get("latitude")
            lon = headline.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            markers.append(
                {
                    "kind": "headline",
                    "title": headline.get("title"),
                    "source": headline.get("source"),
                    "severity": headline.get("score"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
            )

        return markers
