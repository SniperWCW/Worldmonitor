"""Data coordinator for Lage Monitor."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterable
from dataclasses import field, replace
from datetime import timedelta
from email.utils import parsedate_to_datetime
import math
import re
import time
from typing import Any
import unicodedata

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT_COOLDOWN_MIN,
    CONF_ALERT_ROUTE_DELAY,
    CONF_AUTOBAHN_ROUTES,
    CONF_WATER_ALWAYS,
    CONF_ALERT_NOTIFY_SERVICE,
    CONF_ALERT_RADIUS_KM,
    CONF_ALERT_SCORE_DROP,
    CONF_AUTOBAHN_ROADS,
    CONF_LAYER_RADIATION,
    CONF_LAYER_WATER,
    CONF_LIVE_STREAMS,
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
    DEFAULT_ALERT_COOLDOWN_MIN,
    DEFAULT_ALERT_ROUTE_DELAY,
    DEFAULT_AUTOBAHN_ROUTES,
    DEFAULT_WATER_ALWAYS,
    DEFAULT_ALERT_NOTIFY_SERVICE,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_ALERT_SCORE_DROP,
    DEFAULT_AUTOBAHN_ROADS,
    DEFAULT_CUSTOM_PRESS_FEEDS,
    DEFAULT_FOCUS_MODE,
    DEFAULT_LAYER_RADIATION,
    DEFAULT_LAYER_WATER,
    DEFAULT_LIVE_STREAMS,
    DEFAULT_LOCAL_KEYWORDS,
    DEFAULT_POLICE_COUNT_MODE,
    DEFAULT_WARN_DWD,
    DEFAULT_WARN_LHP,
    DEFAULT_WARN_MOWAS,
    DEFAULT_WARN_POLICE,
    DOMAIN,
    FEED_MAX_STALE,
    FEED_MIN_INTERVAL_NEWS,
    FEED_MIN_INTERVAL_POLICE,
    FETCH_CONCURRENCY,
    FOCUS_MODE_LOCAL,
    UPDATE_FAILURES_BEFORE_UNAVAILABLE,
    GERMAN_NEWS_FEEDS,
    NATIONAL_PRIORITY_KEYWORDS,
    POLICE_COUNT_MODE_ALL,
    PRESSEPORTAL_FEEDS,
)
from . import alerting, geo, geometry
from .feed import (
    FeedItem,
    fetch_feed,
    fetch_json_conditional,
    iso_timestamp,
)
from .fetchcache import FetchResult, ResilientCache, SourcePolicy
from .layers import LayerConfig, fetch_layers
from .live import parse_streams
from .sources.autobahn import parse_roads, parse_routes
from .scoring import score_text
from .analysis_mixin import AnalysisMixin
from .common import (
    COORD_RE,
    LageSnapshot,
    SCORE_HISTORY_VERSION,
    _LOGGER,
    _assessment_status,
)
from .events_mixin import EventsMixin
from .warnings_mixin import WarningsMixin


class LageMonitorCoordinator(WarningsMixin, AnalysisMixin, EventsMixin, DataUpdateCoordinator[LageSnapshot]):
    """Coordinator for data aggregation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._warnung_kreise: dict[str, dict] | None = None
        self._warnung_gemeinden: dict[str, dict] | None = None
        self._score_history: list[dict[str, Any]] = []
        self._history_loaded = False
        self._cache = ResilientCache()
        self._fetch_semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
        self._consecutive_failures = 0
        self._stale_since: str | None = None
        self._alert_state = alerting.AlertState()
        self._history_store: Store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_history")
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
        """Refresh data; never present an outage as a calm situation.

        Individual sources degrade on their own (see ``fetchcache``). This
        handler covers failures of the whole refresh: the previous snapshot is
        kept but flagged ``stale`` in the diagnostics. After several failures
        in a row the entities become unavailable instead of showing old data
        as if it were current.
        """
        try:
            await self._async_load_history()
            snapshot = await self._build_snapshot()
        except Exception as err:  # noqa: BLE001
            self._consecutive_failures += 1
            if self.data is None:
                # First refresh: let Home Assistant retry the setup.
                raise UpdateFailed(f"Initial Lage Monitor refresh failed: {err}") from err
            if self._consecutive_failures >= UPDATE_FAILURES_BEFORE_UNAVAILABLE:
                raise UpdateFailed(
                    f"Lage Monitor refresh failed {self._consecutive_failures} times: {err}"
                ) from err
            _LOGGER.warning(
                "Could not update Lage Monitor (%s in a row), keeping previous data: %s",
                self._consecutive_failures,
                err,
            )
            if self._stale_since is None:
                self._stale_since = iso_timestamp()
            return replace(
                self.data,
                diagnostics={
                    **self.data.diagnostics,
                    "stale": True,
                    "stale_since": self._stale_since,
                    "consecutive_failures": self._consecutive_failures,
                    "last_error": str(err),
                },
            )

        self._consecutive_failures = 0
        self._stale_since = None
        return snapshot

    async def _async_load_history(self) -> None:
        """Load persisted score history once per coordinator lifetime."""
        if self._history_loaded:
            return
        self._history_loaded = True
        try:
            stored = await self._history_store.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not load Lage Monitor history: %s", err)
            return
        if not isinstance(stored, dict) or stored.get("score_version") != SCORE_HISTORY_VERSION:
            # Score semantics can change between releases. Mixing old samples into
            # the new trend line would create a fictitious jump.
            return
        entries = stored.get("entries", [])
        loaded: list[dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            ts = dt_util.parse_datetime(str(item.get("ts") or ""))
            if ts is None:
                continue
            loaded.append(
                {
                    "ts": dt_util.as_local(ts),
                    "germany_score": int(item.get("germany_score", 100)),
                    "global_score": int(item.get("global_score", 100)),
                    "local_score": int(item.get("local_score", 100)),
                    "stability_index": int(item.get("stability_index", 100)),
                }
            )
        cutoff = dt_util.now() - timedelta(days=7, hours=1)
        self._score_history = [item for item in loaded if item["ts"] >= cutoff]

    async def _async_save_history(self) -> None:
        """Persist current history window for restart-stable trends."""
        payload = {
            "score_version": SCORE_HISTORY_VERSION,
            "entries": [
                {
                    "ts": item["ts"].isoformat(),
                    "germany_score": int(item["germany_score"]),
                    "global_score": int(item["global_score"]),
                    "local_score": int(item["local_score"]),
                    "stability_index": int(item["stability_index"]),
                }
                for item in self._score_history
            ]
        }
        try:
            await self._history_store.async_save(payload)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not save Lage Monitor history: %s", err)

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
            alerts.extend(
                self._filter_alerts_by_radius(
                    official_alerts,
                    home_center,
                    alert_radius_km,
                    focus_mode,
                    local_keywords,
                )
            )
            source_status["warnung_bund"] = official_status

        feed_limit = self._feed_fetch_limit(news_limit)
        feed_jobs: list[tuple[str, str]] = []
        if self.entry.options.get(CONF_INCLUDE_PRESS, self.entry.data[CONF_INCLUDE_PRESS]):
            feed_jobs.extend(self._iter_press_feeds(focus_mode))
            feed_jobs.extend(
                (f"custom_press_{index}", url)
                for index, url in enumerate(custom_press_feeds, start=1)
            )
        if self.entry.options.get(CONF_INCLUDE_NEWS, self.entry.data[CONF_INCLUDE_NEWS]):
            for source, url in GERMAN_NEWS_FEEDS.items():
                # Keep one nationwide source available even in local focus mode.
                if focus_mode == FOCUS_MODE_LOCAL and source != "tagesschau_all":
                    continue
                feed_jobs.append((source, url))

        feed_results = await asyncio.gather(
            *(self._safe_fetch_feed(url, source, feed_limit) for source, url in feed_jobs)
        )
        for (source, _url), (items, status) in zip(feed_jobs, feed_results, strict=True):
            headlines.extend(items)
            source_status[source] = status

        public_event_items, public_event_status = await self._safe_fetch_public_event_items(
            home_center,
            alert_radius_km,
        )
        source_status.update(public_event_status)

        layer_items, layer_status = await self._safe_fetch_layers(home_center, alert_radius_km)
        source_status.update(layer_status)

        deduped = self._dedupe_items(headlines)
        deduped = self._filter_recent_feed_items(deduped)
        scored = [self._score_item(item) for item in deduped]
        scored.extend(public_event_items)
        if focus_mode == FOCUS_MODE_LOCAL:
            scored.extend(self._alerts_to_scored_items(alerts))
        scored = self._apply_focus_filter(scored, focus_mode, local_keywords)
        scored.sort(key=lambda item: item["score"], reverse=True)
        local_headlines = self._build_local_headlines(
            scored,
            alerts,
            local_keywords,
            news_limit,
            home_center,
            alert_radius_km,
            focus_mode,
        )
        local_alerts = self._select_local_alerts_for_headlines(
            alerts,
            local_keywords,
            home_center,
            alert_radius_km,
            focus_mode,
        )
        germany_headlines = self._build_germany_headlines(scored, local_keywords, news_limit)
        world_headlines = [item for item in scored if item.get("region") == "world"][:news_limit]
        local_risk_items = [
            item for item in local_headlines if int(item.get("score") or 0) >= 8
        ]

        now = dt_util.now()
        official_alert_risk = self._normalize_aggregate_risk(
            self._alerts_to_scored_items(alerts), now, scale=42.0, cap=45
        )
        germany_items, world_items = self._split_scope_items(scored)
        germany_risk_items = [
            item for item in germany_items if int(item.get("score") or 0) >= 8
        ]
        world_risk_items = [
            item for item in world_items if int(item.get("score") or 0) >= 8
        ]
        germany_relevant_headlines = [
            item for item in germany_headlines if int(item.get("score") or 0) >= 8
        ]
        world_relevant_headlines = [
            item for item in world_headlines if int(item.get("score") or 0) >= 8
        ]
        germany_police_items = [
            item for item in germany_risk_items if item.get("source") == "presseportal_blaulicht"
        ]
        germany_news_items = [
            item for item in germany_risk_items if item.get("source") != "presseportal_blaulicht"
        ]
        germany_priority_items = [
            item for item in germany_risk_items if int(item.get("score") or 0) >= 12
        ]
        germany_police_risk = self._normalize_aggregate_risk(
            germany_police_items, now, scale=55.0, cap=25
        )
        germany_news_risk = self._normalize_aggregate_risk(
            germany_news_items, now, scale=70.0, cap=45
        )
        germany_high_priority_risk = self._normalize_aggregate_risk(
            germany_priority_items, now, scale=55.0, cap=30
        )
        germany_event_risk = self._normalize_aggregate_risk(
            germany_risk_items, now, scale=90.0, cap=78
        )
        germany_risk_score = self._combine_risks(official_alert_risk, germany_event_risk)
        global_risk_score = self._normalize_aggregate_risk(
            world_risk_items, now, scale=95.0, cap=100
        )
        local_risk_score = self._normalize_aggregate_risk(
            local_risk_items, now, scale=52.0, cap=100
        )
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
        military_items_all = [item for item in scored if item["military_score"] >= 8]
        military_items_germany = [item for item in military_items_all if item["region"] == "de"][:10]
        military_items_world = [item for item in military_items_all if item["region"] == "world"][:10]
        local_keys = {
            str(item.get("link") or item.get("title") or "") for item in local_headlines
        }
        military_items_local = [
            item
            for item in military_items_germany
            if str(item.get("link") or item.get("title") or "") in local_keys
        ][:10]
        military_items = military_items_all[:10]
        military_signal_germany_risk = self._compute_military_signal(military_items_germany)
        military_signal_world_risk = self._compute_military_signal(military_items_world)
        military_signal_risk = max(military_signal_germany_risk, military_signal_world_risk)
        germany_score = 100 - germany_risk_score
        global_score = 100 - global_risk_score
        local_score = 100 - local_risk_score
        # A transparent composite of the two independent scopes. Local is a
        # subset of Germany and is intentionally not counted a second time.
        stability_index = round(germany_score * 0.75 + global_score * 0.25)
        military_signal_germany = 100 - military_signal_germany_risk
        military_signal_world = 100 - military_signal_world_risk
        military_signal = 100 - military_signal_risk
        score_breakdown = {
            "alerts": official_alert_risk,
            "police_germany": germany_police_risk,
            "news_germany": germany_news_risk,
            "high_priority_germany": germany_high_priority_risk,
            "local_total": local_risk_score,
            "military_signal": military_signal_risk,
            "military_signal_germany": military_signal_germany_risk,
            "military_signal_world": military_signal_world_risk,
            "high_priority_items": high_priority * 5,
            "police_items": police_items * 2,
        }
        risk_components = {
            "germany": self._build_risk_components(
                germany_risk_items,
                "de",
                official_alert_risk,
                germany_police_risk,
                germany_news_risk,
                germany_high_priority_risk,
                military_signal_germany_risk,
            ),
            "world": self._build_risk_components(
                world_risk_items,
                "world",
                0,
                0,
                min(35, global_risk_score // 2),
                min(35, sum(1 for item in world_risk_items if int(item.get("score") or 0) >= 12) * 6),
                military_signal_world_risk,
            ),
            "local": self._build_risk_components(
                local_risk_items,
                "de",
                min(30, self._normalize_aggregate_risk(
                    self._alerts_to_scored_items(local_alerts), now, scale=42.0, cap=45
                )),
                min(25, sum(1 for item in local_risk_items if item.get("source") == "presseportal_blaulicht") * 5),
                min(35, local_risk_score // 2),
                min(35, sum(1 for item in local_risk_items if int(item.get("score") or 0) >= 12) * 6),
                self._compute_military_signal(military_items_local),
            ),
        }
        theme_scores = {
            "germany": self._build_theme_scores(germany_risk_items, now),
            "world": self._build_theme_scores(world_risk_items, now),
            "local": self._build_theme_scores(local_risk_items, now),
        }
        scope_counts = {
            "local": {"alerts": len(local_alerts), "military": len(military_items_local)},
            "germany": {"alerts": len(alerts), "military": len(military_items_germany)},
            "world": {"alerts": 0, "military": len(military_items_world)},
        }
        risk_drivers = self._build_risk_drivers(
            score_breakdown,
            germany_relevant_headlines,
            alerts,
        )
        score_trend = self._build_score_trend(germany_score, stability_index)
        source_freshness = self._build_source_freshness(scored, alerts, source_status)
        data_quality = self._build_data_quality(
            source_status,
            source_freshness,
            germany_items,
            world_items,
            local_headlines,
        )
        history_summary = self._build_history_summary(
            germany_score,
            global_score,
            local_score,
            stability_index,
        )
        analysis_summary = self._build_analysis_summary(
            germany_score,
            global_score,
            local_score,
            stability_index,
            active_alerts=len(alerts),
            local_active_alerts=len(local_alerts),
            military_signal_germany=military_signal_germany,
            military_signal_world=military_signal_world,
            risk_drivers=risk_drivers,
            germany_headlines=germany_relevant_headlines,
            world_headlines=world_relevant_headlines,
            local_headlines=local_risk_items,
            alert_radius_km=alert_radius_km,
            history_summary=history_summary,
            data_quality=data_quality,
        )

        keyword_counter: Counter[str] = Counter()
        for item in scored[:20]:
            keyword_counter.update(item["keywords"])

        map_markers = self._build_map_markers(
            alerts,
            scored,
            home_center,
            local_keywords,
            alert_radius_km,
            focus_mode,
        )

        snapshot = LageSnapshot(
            germany_score=germany_score,
            global_score=global_score,
            local_score=local_score,
            active_alerts=len(alerts),
            police_items=police_items,
            high_priority_items=high_priority,
            military_signal_score=military_signal,
            military_signal_germany=military_signal_germany,
            military_signal_world=military_signal_world,
            stability_index=stability_index,
            germany_risk_score=germany_risk_score,
            global_risk_score=global_risk_score,
            local_risk_score=local_risk_score,
            headlines=scored[:news_limit],
            local_headlines=local_headlines,
            germany_headlines=germany_headlines,
            world_headlines=world_headlines,
            alerts=self._public_alerts(alerts[: min(len(alerts), 15)]),
            local_alerts=self._public_alerts(local_alerts[: min(len(local_alerts), 15)]),
            map_markers=map_markers,
            military_items=military_items,
            military_items_germany=military_items_germany,
            military_items_local=military_items_local,
            military_items_world=military_items_world,
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
                "home_state": (
                    geo.state_for_point(float(home_center[0]), float(home_center[1])) or ""
                    if home_center[0] is not None and home_center[1] is not None
                    else ""
                ),
                "degraded": any(status["ok"] is False for status in source_status.values()),
                "stale": False,
                "consecutive_failures": 0,
                "stale_sources": sorted(
                    name for name, status in source_status.items() if status.get("stale")
                ),
                "failing_sources": sorted(
                    name
                    for name, status in source_status.items()
                    if status["ok"] is False and not status.get("stale")
                ),
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
            score_breakdown=score_breakdown,
            analysis_summary=analysis_summary,
            risk_drivers=risk_drivers,
            score_trend=score_trend,
            risk_components=risk_components,
            history_summary=history_summary,
            source_freshness=source_freshness,
            data_quality=data_quality,
            theme_scores=theme_scores,
            scope_counts=scope_counts,
            layer_items=layer_items,
            live_streams=parse_streams(self._option(CONF_LIVE_STREAMS, DEFAULT_LIVE_STREAMS)),
        )
        self._dispatch_alert_events(snapshot)
        return snapshot

    def _option(self, key: str, default: Any) -> Any:
        """Read an option, falling back to the original setup data and then the default."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    async def _safe_fetch_layers(
        self,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Fetch the optional map layers (Autobahn, water levels, radiation)."""
        cfg = LayerConfig(
            autobahn_roads=tuple(parse_roads(self._option(CONF_AUTOBAHN_ROADS, DEFAULT_AUTOBAHN_ROADS))),
            routes=tuple(parse_routes(self._option(CONF_AUTOBAHN_ROUTES, DEFAULT_AUTOBAHN_ROUTES))),
            water=bool(self._option(CONF_LAYER_WATER, DEFAULT_LAYER_WATER)),
            water_always=bool(self._option(CONF_WATER_ALWAYS, DEFAULT_WATER_ALWAYS)),
            radiation=bool(self._option(CONF_LAYER_RADIATION, DEFAULT_LAYER_RADIATION)),
        )

        async def fetch(
            key: str, url: str, min_interval: float, max_stale: float, timeout: float | None = None
        ) -> FetchResult:
            async def run(etag, last_modified):
                return await fetch_json_conditional(self.hass, url, etag, last_modified, timeout=timeout)

            return await self._cached_get(
                key, run, SourcePolicy(min_interval=min_interval, max_stale=max_stale)
            )

        return await fetch_layers(cfg, home_center, radius_km, fetch)

    def _dispatch_alert_events(self, snapshot: LageSnapshot) -> None:
        """Fire ``lage_monitor_alert`` for noteworthy changes (and notify if configured)."""
        try:
            events = alerting.detect(
                self._alert_state,
                now=time.monotonic(),
                status=_assessment_status(snapshot.germany_score)["key"],
                score=snapshot.germany_score,
                local_alerts=snapshot.local_alerts,
                layer_items=snapshot.layer_items,
                drop_threshold=int(self._option(CONF_ALERT_SCORE_DROP, DEFAULT_ALERT_SCORE_DROP)),
                route_delay_min=int(self._option(CONF_ALERT_ROUTE_DELAY, DEFAULT_ALERT_ROUTE_DELAY)),
                cooldown_s=60.0 * int(self._option(CONF_ALERT_COOLDOWN_MIN, DEFAULT_ALERT_COOLDOWN_MIN)),
            )
        except Exception:  # noqa: BLE001 - alerting must never break a refresh
            _LOGGER.exception("Could not evaluate Lage Monitor alert events")
            return
        for event in events:
            self._publish_event(event)

    def _publish_event(self, event: dict[str, Any]) -> None:
        """Fire the bus event and forward it to the configured notify service."""
        self.hass.bus.async_fire(alerting.EVENT_NAME, event)
        service = str(self._option(CONF_ALERT_NOTIFY_SERVICE, DEFAULT_ALERT_NOTIFY_SERVICE)).strip()
        if service.startswith("notify."):
            service = service[len("notify."):]
        if service and re.fullmatch(r"[a-z0-9_]+", service):
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": "Lage Monitor", "message": alerting.format_message(event)},
                )
            )

    def send_test_alert(self, title: str = "") -> dict[str, Any]:
        """Publish a test event (service ``lage_monitor.test_alert``)."""
        event = {
            "type": alerting.TYPE_TEST,
            "direction": "info",
            "title": title.strip()[:200] or "Testmeldung vom Lage Monitor",
        }
        self._publish_event(event)
        return event


    async def _cached_get(self, key: str, fetch, policy: SourcePolicy) -> FetchResult:
        """Run a cached fetch with a global concurrency limit."""
        async with self._fetch_semaphore:
            return await self._cache.get(key, fetch, policy)

    async def _safe_fetch_feed(self, url: str, source: str, limit: int) -> tuple[list[FeedItem], dict]:
        """Fetch a feed; on failure serve the last good items, flagged as stale."""
        is_police = source.startswith(("presseportal", "custom_press_"))
        policy = SourcePolicy(
            min_interval=FEED_MIN_INTERVAL_POLICE if is_police else FEED_MIN_INTERVAL_NEWS,
            max_stale=FEED_MAX_STALE,
        )

        async def fetch(etag, last_modified):
            return await fetch_feed(self.hass, url, source, limit, etag, last_modified)

        result = await self._cached_get(f"feed:{source}", fetch, policy)
        if not result.ok:
            _LOGGER.warning(
                "Feed %s %s: %s", source, "serving stale data" if result.stale else "failed", result.error
            )
        items = result.value or []
        return items, result.status(len(items))


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

    def _filter_recent_feed_items(self, items: list[FeedItem]) -> list[FeedItem]:
        """Keep only feed items from today or yesterday when a date is available."""
        cutoff_date = dt_util.now().date() - timedelta(days=1)
        filtered: list[FeedItem] = []

        for item in items:
            published_dt = self._parse_feed_datetime(item.published)
            if published_dt is None:
                filtered.append(item)
                continue
            if dt_util.as_local(published_dt).date() >= cutoff_date:
                filtered.append(item)

        return filtered

    def _parse_feed_datetime(self, value: str | None):
        """Parse RSS/Atom publication timestamps to timezone-aware datetimes."""
        raw = str(value or "").strip()
        if not raw:
            return None

        parsed = dt_util.parse_datetime(raw)
        if parsed is not None:
            return parsed if parsed.tzinfo is not None else dt_util.as_utc(parsed)

        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
        return parsed if parsed.tzinfo is not None else dt_util.as_utc(parsed)

    def _score_item(self, item: FeedItem) -> dict:
        """Score a feed item via the pure scoring module (see scoring.py)."""
        result = score_text(item.title, item.summary, item.source)
        scored_item = {
            "title": item.title,
            "link": item.link,
            "summary": item.summary,
            "published": item.published,
            "published_dt": self._parse_feed_datetime(item.published),
            "source": item.source,
            "score": result.score,
            "keywords": result.keywords,
            "priority_keywords": result.priority_keywords,
            "military_keywords": result.military_keywords,
            "military_score": result.military_score,
            "region": result.region,
            "near_abroad": result.near_abroad,
            "state": result.state,
            "latitude": None,
            "longitude": None,
        }
        scored_item["themes"] = self._classify_item_themes(scored_item)
        return scored_item


    def _extract_lat_lon(self, item: dict) -> tuple[float | None, float | None]:
        """Try to extract coordinates from a map warning payload."""
        direct = self._extract_coordinate_pair(item)
        if direct != (None, None):
            return direct
        nested = self._find_nested_coordinate_pair(item)
        if nested != (None, None):
            return nested
        return None, None


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
            if self._valid_lat_lon(lat, lon):
                return lat, lon

        coords = value.get("coordinate") or value.get("coordinates")
        if isinstance(coords, str):
            parts = COORD_RE.findall(coords)
            if len(parts) >= 2:
                lat = self._to_float_or_none(parts[0])
                lon = self._to_float_or_none(parts[1])
                if self._valid_lat_lon(lat, lon):
                    return lat, lon
        if isinstance(coords, list) and len(coords) >= 2:
            first = self._to_float_or_none(coords[0])
            second = self._to_float_or_none(coords[1])
            if first is not None and second is not None:
                geojson_type = str(value.get("type") or "").lower()
                if geojson_type in {
                    "point",
                    "multipoint",
                    "linestring",
                    "multilinestring",
                    "polygon",
                    "multipolygon",
                    "geometrycollection",
                } and self._valid_lat_lon(second, first):
                    # RFC 7946 fixes GeoJSON positions to longitude, latitude.
                    return second, first
                if 5 <= first <= 16 and 47 <= second <= 56:
                    # Unlabelled German coordinate pairs are commonly lon/lat.
                    return second, first
                if 47 <= first <= 56 and 5 <= second <= 16:
                    return first, second
                if self._valid_lat_lon(first, second):
                    # Preserve CAP-style latitude,longitude as the generic fallback.
                    return first, second

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

    def _valid_lat_lon(self, lat: float | None, lon: float | None) -> bool:
        """Return whether a complete coordinate pair is within global bounds."""
        return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180

    def _timestamp_from_epoch_ms(self, value) -> str:
        """Convert a Unix epoch in milliseconds to an ISO timestamp."""
        numeric = self._to_float_or_none(value)
        if numeric is None:
            return ""
        return dt_util.utc_from_timestamp(numeric / 1000).replace(microsecond=0).isoformat()

    def _build_structured_item(
        self,
        *,
        title: str,
        summary: str,
        source: str,
        published: str,
        score: int,
        region: str,
        latitude: float | None,
        longitude: float | None,
        severity: str = "",
        keywords: list[str] | None = None,
        link: str = "",
        military_score: int = 0,
    ) -> dict:
        """Create a normalized scored item from structured event data."""
        item = {
            "title": title,
            "link": link,
            "summary": summary,
            "published": published,
            "published_dt": self._parse_feed_datetime(published),
            "source": source,
            "score": min(max(int(score), 0), 100),
            "keywords": keywords or [],
            "priority_keywords": [],
            "military_keywords": [],
            "military_score": min(max(int(military_score), 0), 100),
            "region": region,
            "latitude": latitude,
            "longitude": longitude,
            "severity": severity,
        }
        item["themes"] = self._classify_item_themes(item)
        return item

    def _normalize_text(self, value: str) -> str:
        """Normalize user-facing place names for matching."""
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())

    def _is_in_germany(self, lat: float, lon: float) -> bool:
        """Return whether a coordinate lies inside Germany (coarse outline).

        The former bounding box also contained Basel, Salzburg, Prague and
        Szczecin; ``geo.in_germany`` uses a polygon instead.
        """
        return geo.in_germany(lat, lon)

    def _is_within_radius(
        self,
        home_center: tuple[float | None, float | None],
        lat: float,
        lon: float,
        radius_km: int,
    ) -> bool:
        """Return whether a point lies within the configured local radius."""
        home_lat, home_lon = home_center
        if home_lat is None or home_lon is None:
            return False
        return self._haversine_km(home_lat, home_lon, lat, lon) <= radius_km

    def _bbox_for_home_radius(
        self,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> tuple[float, float, float, float] | None:
        """Build an EONET-style bbox around the Home location."""
        home_lat, home_lon = home_center
        if home_lat is None or home_lon is None:
            return None
        lat_delta = radius_km / 111.0
        lon_scale = max(0.2, math.cos(math.radians(home_lat)))
        lon_delta = radius_km / (111.0 * lon_scale)
        return (
            round(home_lon - lon_delta, 4),
            round(home_lat + lat_delta, 4),
            round(home_lon + lon_delta, 4),
            round(home_lat - lat_delta, 4),
        )


    def _centroid_from_geojson(self, geojson: dict) -> tuple[float | None, float | None]:
        """Compute an area-weighted representative point from GeoJSON."""
        context = self._geometry_context_from_geojson(geojson)
        return context.get("latitude"), context.get("longitude")

    def _geometry_context_from_geojson(self, geojson: object) -> dict[str, Any]:
        """Parse RFC 7946 geometry (see ``geometry.geometry_context_from_geojson``)."""
        return geometry.geometry_context_from_geojson(geojson)


    def _feed_fetch_limit(self, news_limit: int) -> int:
        """Fetch deeper into feeds so later scoring can still surface relevant articles."""
        return max(12, int(news_limit or 0))


    def _build_local_headlines(
        self,
        scored: list[dict],
        alerts: list[dict],
        local_keywords: list[str],
        limit: int,
        home_center: tuple[float | None, float | None],
        radius_km: int,
        focus_mode: str,
    ) -> list[dict]:
        """Build a strict local-only list from local keyword hits and local alerts."""
        items: list[dict] = []
        seen: set[str] = set()
        local_alerts = self._select_local_alerts_for_headlines(
            alerts,
            local_keywords,
            home_center,
            radius_km,
            focus_mode,
        )
        for item in self._alerts_to_scored_items(local_alerts):
            key = str(item.get("link") or item.get("title") or "")
            if key and key not in seen:
                seen.add(key)
                items.append(item)
        for item in scored:
            if self._is_item_within_radius(item, home_center, radius_km):
                key = str(item.get("link") or item.get("title") or "")
                if key and key not in seen:
                    seen.add(key)
                    items.append(item)
                continue
            if not self._matches_local_keywords(item, local_keywords):
                continue
            key = str(item.get("link") or item.get("title") or "")
            if key and key not in seen:
                seen.add(key)
                items.append(item)
        items.sort(key=lambda item: item["score"], reverse=True)
        return items[:limit]

    def _is_item_within_radius(
        self,
        item: dict,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> bool:
        """Return whether a scored item is geocoded within the local radius."""
        lat = self._to_float_or_none(item.get("latitude"))
        lon = self._to_float_or_none(item.get("longitude"))
        if lat is None or lon is None:
            return False
        return self._is_within_radius(home_center, lat, lon, radius_km)


    def _build_germany_headlines(
        self,
        scored: list[dict],
        local_keywords: list[str],
        limit: int,
    ) -> list[dict]:
        """Build a Germany-wide list without local-only items."""
        items = [
            item
            for item in scored
            if item.get("region") == "de"
            and item.get("source") != "police"
            and not self._matches_local_keywords(item, local_keywords)
        ]
        return items[:limit]

    def _national_priority_matches(self, text: str) -> list[str]:
        """Return terms that make a story nationally relevant in local mode."""
        haystack = str(text or "").lower()
        return [keyword for keyword in NATIONAL_PRIORITY_KEYWORDS if keyword in haystack]

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
            priority_matches = self._national_priority_matches(haystack)
            if priority_matches:
                item["score"] = max(int(item.get("score", 0)), 24)
                item["priority_keywords"] = priority_matches
                filtered.append(item)
            elif any(keyword in haystack for keyword in keywords_lower):
                item["score"] += 4
                filtered.append(item)
        return filtered

    def _matches_local_keywords(self, item: dict, local_keywords: list[str]) -> bool:
        """Check whether an item matches the configured local terms."""
        if not local_keywords:
            return False
        haystack = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        return any(keyword.lower() in haystack for keyword in local_keywords)

    def _is_all_clear_alert(self, alert: dict) -> bool:
        """Filter out all-clear messages from official warning sources."""
        haystack = " ".join(
            str(alert.get(field) or "")
            for field in ("title", "summary", "severity", "source")
        ).lower()
        return any(
            token in haystack
            for token in (
                "entwarnung",
                "warnung aufgehoben",
                "aufhebung",
                "all clear",
            )
        )

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


    def _alert_distance_km(
        self,
        alert: dict,
        home_center: tuple[float | None, float | None],
    ) -> float | None:
        """Return distance from Home to the warning area, point, or centroid."""
        home_lat, home_lon = home_center
        if not self._valid_lat_lon(home_lat, home_lon):
            return None

        polygons = alert.get("_geometry_polygons")
        if isinstance(polygons, list) and polygons:
            distances: list[float] = []
            for polygon in polygons:
                if not isinstance(polygon, list) or not polygon:
                    continue
                outer = polygon[0]
                holes = polygon[1:]
                if self._point_in_ring(home_lat, home_lon, outer) and not any(
                    self._point_in_ring(home_lat, home_lon, hole) for hole in holes
                ):
                    return 0.0
                distances.extend(
                    self._distance_to_ring_km(home_lat, home_lon, ring)
                    for ring in polygon
                    if isinstance(ring, list) and len(ring) >= 2
                )
            if distances:
                return min(distances)

        geometry_points = alert.get("_geometry_points")
        if isinstance(geometry_points, list):
            distances = [
                self._haversine_km(home_lat, home_lon, float(point[0]), float(point[1]))
                for point in geometry_points
                if isinstance(point, list)
                and len(point) >= 2
                and self._valid_lat_lon(
                    self._to_float_or_none(point[0]), self._to_float_or_none(point[1])
                )
            ]
            if distances:
                return min(distances)

        lat = self._to_float_or_none(alert.get("latitude"))
        lon = self._to_float_or_none(alert.get("longitude"))
        if self._valid_lat_lon(lat, lon):
            return self._haversine_km(home_lat, home_lon, lat, lon)
        return None

    def _point_in_ring(self, lat: float, lon: float, ring: list) -> bool:
        """Return whether a point is inside a polygon ring using ray casting."""
        inside = False
        if len(ring) < 3:
            return False
        previous = ring[-1]
        for current in ring:
            if not (
                isinstance(current, list)
                and len(current) >= 2
                and isinstance(previous, list)
                and len(previous) >= 2
            ):
                previous = current
                continue
            current_lat, current_lon = float(current[0]), float(current[1])
            previous_lat, previous_lon = float(previous[0]), float(previous[1])
            crosses = (current_lat > lat) != (previous_lat > lat)
            if crosses:
                boundary_lon = (previous_lon - current_lon) * (lat - current_lat) / (
                    previous_lat - current_lat
                ) + current_lon
                if lon < boundary_lon:
                    inside = not inside
            previous = current
        return inside

    def _distance_to_ring_km(self, lat: float, lon: float, ring: list) -> float:
        """Return the minimum local-planar distance from a point to a ring."""
        return min(
            self._point_to_segment_distance_km(lat, lon, ring[index], ring[(index + 1) % len(ring)])
            for index in range(len(ring))
        )

    def _point_to_segment_distance_km(
        self, lat: float, lon: float, start: list, end: list
    ) -> float:
        """Measure point-to-segment distance with a local equirectangular projection."""
        lon_scale = 111.320 * math.cos(math.radians(lat))
        lat_scale = 110.574

        def projected(point: list) -> tuple[float, float]:
            point_lat = float(point[0])
            point_lon = float(point[1])
            delta_lon = (point_lon - lon + 180) % 360 - 180
            return delta_lon * lon_scale, (point_lat - lat) * lat_scale

        start_x, start_y = projected(start)
        end_x, end_y = projected(end)
        segment_x = end_x - start_x
        segment_y = end_y - start_y
        length_squared = segment_x * segment_x + segment_y * segment_y
        if length_squared <= 1e-12:
            return math.hypot(start_x, start_y)
        projection = max(
            0.0,
            min(1.0, -(start_x * segment_x + start_y * segment_y) / length_squared),
        )
        return math.hypot(start_x + projection * segment_x, start_y + projection * segment_y)


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
