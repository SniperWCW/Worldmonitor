"""Official warnings (warnung.bund.de): fetching, area resolution, scoring."""

from __future__ import annotations

import asyncio
from dataclasses import field
import html
import re
from typing import Any
from urllib.parse import quote

from homeassistant.util import dt as dt_util

from .const import (
    ALERTS_MAX_STALE,
    ALERTS_MIN_INTERVAL,
    DETAIL_MAX_STALE,
    DETAIL_MIN_INTERVAL,
    FOCUS_MODE_LOCAL,
    WARNUNG_BUND_ASSETS_BASE_URL,
    WARNUNG_BUND_BASE_URL,
)
from . import geometry
from .feed import fetch_json
from .fetchcache import SourcePolicy
from .common import _LOGGER


class WarningsMixin:
    """Official warnings (warnung.bund.de): fetching, area resolution, scoring."""

    async def _safe_fetch_official_alerts(
        self,
        resolved_warn_area: dict | None,
        service_filter: dict[str, bool],
    ) -> tuple[list[dict], dict]:
        """Fetch warnung.bund.de alerts; on failure keep the last good list (stale).

        An unreachable warning service must not look like "no warnings".
        """
        policy = SourcePolicy(min_interval=ALERTS_MIN_INTERVAL, max_stale=ALERTS_MAX_STALE)

        async def fetch(_etag, _last_modified):
            alerts = await self._fetch_official_alerts(resolved_warn_area, service_filter)
            return alerts, None, None

        # No semaphore here: the leaf requests inside take it, avoiding nested waits.
        result = await self._cache.get("alerts:warnung_bund", fetch, policy)
        if not result.ok:
            _LOGGER.warning(
                "warnung.bund.de %s: %s",
                "serving stale alerts" if result.stale else "unavailable",
                result.error,
            )
        alerts = [dict(alert) for alert in (result.value or [])]
        return alerts, result.status(len(alerts))

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
            channels = self._iter_enabled_warn_channels(service_filter)
            channel_data = await asyncio.gather(
                *(
                    fetch_json(self.hass, f"{WARNUNG_BUND_BASE_URL}/{channel}/mapData.json")
                    for channel in channels
                ),
                return_exceptions=True,
            )
            failed_channels = 0
            for channel, data in zip(channels, channel_data, strict=True):
                if isinstance(data, Exception):
                    failed_channels += 1
                    _LOGGER.warning("Warning channel %s failed: %s", channel, data)
                    continue
                if not isinstance(data, list):
                    continue
                alerts.extend(
                    self._normalize_map_alert(item, channel)
                    for item in data[:50]
                    if isinstance(item, dict)
                )
            if channels and failed_channels == len(channels):
                # Every channel failed: report an error so the stale fallback applies.
                raise RuntimeError("alle Warnkanäle von warnung.bund.de nicht erreichbar")

        unique: dict[str, dict] = {}
        for alert in alerts:
            if self._is_all_clear_alert(alert):
                continue
            key = str(alert.get("id") or alert.get("title"))
            unique[key] = alert

        resolved = [alert for alert in unique.values() if self._is_service_enabled(alert, service_filter)]
        if resolved:
            await self._enrich_official_alert_details(resolved[:15])
        geometry_alerts = [alert for alert in resolved if alert.get("id")]
        geometries = await asyncio.gather(
            *(self._fetch_warning_geometry(alert.get("id")) for alert in geometry_alerts)
        )
        for alert, geometry in zip(geometry_alerts, geometries, strict=True):
            lat = geometry.get("latitude")
            lon = geometry.get("longitude")
            if lat is not None and lon is not None:
                alert["latitude"] = lat
                alert["longitude"] = lon
            polygons = geometry.get("polygons")
            points = geometry.get("points")
            if polygons:
                alert["_geometry_polygons"] = polygons
                alert["geo_precision"] = "warning_area"
            elif points:
                alert["_geometry_points"] = points
                alert["geo_precision"] = "exact_point"
            elif alert.get("latitude") is not None and alert.get("longitude") is not None:
                alert["geo_precision"] = "reported_point"

        valid_ids = {str(alert.get("id")) for alert in resolved if alert.get("id")}
        self._cache.prune({f"detail:{i}" for i in valid_ids}, prefix="detail:")
        self._cache.prune({f"geometry:{i}" for i in valid_ids}, prefix="geometry:")

        return resolved

    async def _fetch_warnung_dashboard(self, dashboard_code: str) -> list[dict]:
        """Fetch a warnung.bund.de dashboard by 12-digit district code."""
        data = await fetch_json(self.hass, f"{WARNUNG_BUND_BASE_URL}/dashboard/{dashboard_code}.json")
        return data if isinstance(data, list) else []

    async def _fetch_warning_geometry(self, identifier: str | None) -> dict[str, Any]:
        """Fetch and parse warning geometry, cached per warning id."""
        if not identifier:
            return {}
        safe_identifier = quote(str(identifier), safe="")
        url = f"{WARNUNG_BUND_BASE_URL}/warnings/{safe_identifier}.geojson"
        policy = SourcePolicy(
            min_interval=DETAIL_MIN_INTERVAL, max_stale=DETAIL_MAX_STALE, backoff_base=300
        )

        async def fetch(_etag, _last_modified):
            geojson = await fetch_json(self.hass, url)
            return self._geometry_context_from_geojson(geojson), None, None

        result = await self._cached_get(f"geometry:{identifier}", fetch, policy)
        return result.value if isinstance(result.value, dict) else {}

    async def _fetch_warning_centroid(self, identifier: str | None) -> tuple[float | None, float | None]:
        """Compatibility wrapper returning the area-weighted warning centroid."""
        geometry = await self._fetch_warning_geometry(identifier)
        return geometry.get("latitude"), geometry.get("longitude")

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

    async def _enrich_official_alert_details(self, alerts: list[dict]) -> None:
        """Populate official warning text and affected regions from warnung.bund detail data."""
        await asyncio.gather(
            *(self._enrich_single_official_alert(alert) for alert in alerts),
            return_exceptions=True,
        )

    async def _enrich_single_official_alert(self, alert: dict) -> None:
        """Populate a single official alert with description and affected region text."""
        identifier = str(alert.get("id") or "").strip()
        if not identifier:
            return
        try:
            details = await self._fetch_warning_details(identifier)
        except Exception:  # noqa: BLE001
            return
        if details["description"]:
            alert["description"] = details["description"]
        if details["affected_regions"]:
            alert["affected_regions"] = details["affected_regions"]

    async def _fetch_warning_details(self, identifier: str) -> dict[str, str]:
        """Fetch human-readable warning details (cached per warning id)."""
        empty = {"description": "", "affected_regions": ""}
        safe_identifier = quote(identifier, safe="")
        url = f"{WARNUNG_BUND_BASE_URL}/warnings/{safe_identifier}.json"
        policy = SourcePolicy(
            min_interval=DETAIL_MIN_INTERVAL, max_stale=DETAIL_MAX_STALE, backoff_base=300
        )

        async def fetch(_etag, _last_modified):
            return await self._download_warning_details(url), None, None

        result = await self._cached_get(f"detail:{identifier}", fetch, policy)
        return result.value if result.value is not None else empty

    async def _download_warning_details(self, url: str) -> dict[str, str]:
        """Download and parse the detail JSON of one warning."""
        data = await fetch_json(self.hass, url)
        if not isinstance(data, dict):
            return {"description": "", "affected_regions": ""}

        info_entries = data.get("info")
        if not isinstance(info_entries, list):
            return {"description": "", "affected_regions": ""}

        selected_info = None
        for entry in info_entries:
            if isinstance(entry, dict) and str(entry.get("language") or "").upper().startswith("DE"):
                selected_info = entry
                break
        if selected_info is None:
            selected_info = next((entry for entry in info_entries if isinstance(entry, dict)), None)
        if not isinstance(selected_info, dict):
            return {"description": "", "affected_regions": ""}

        areas = selected_info.get("area")
        area_entries = areas if isinstance(areas, list) else [areas] if isinstance(areas, dict) else []
        area_descriptions: list[str] = []
        for area in area_entries:
            if not isinstance(area, dict):
                continue
            area_desc = self._clean_warning_text(area.get("areaDesc"))
            if area_desc and area_desc not in area_descriptions:
                area_descriptions.append(area_desc)

        return {
            "description": self._clean_warning_text(selected_info.get("description")),
            "affected_regions": " | ".join(area_descriptions),
        }

    def _clean_warning_text(self, value: object) -> str:
        """Convert warnung.bund rich text into compact plain text."""
        text = str(value or "")
        if not text.strip():
            return ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

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

    def _score_official_alert(self, alert: dict) -> int:
        """Return a differentiated risk score for official alerts."""
        source = str(alert.get("source") or "").lower()
        severity = str(alert.get("severity") or "")
        title = str(alert.get("title") or "")
        description = str(alert.get("description") or "")
        text = self._normalize_text(" ".join((severity, title, description)))

        source_weight = {
            "police": 2,
            "dwd": 4,
            "lhp": 4,
            "biwapp": 5,
            "katwarn": 5,
            "mowas": 6,
        }.get(source, 4)

        severity_weight = 0
        for keywords, weight in (
            (("extrem", "extreme", "stufe 4", "unwetterwarnung", "gefahr"), 8),
            (("hoch", "high", "stufe 3", "warnung", "warning", "alarm"), 5),
            (("moderat", "moderate", "stufe 2", "beobachtung"), 3),
            (("gering", "minor", "stufe 1", "hinweis", "information", "update"), 1),
        ):
            if any(keyword in text for keyword in keywords):
                severity_weight = weight
                break

        critical_bonus = 0
        for keywords, weight in (
            (("evaku", "rauchgas", "grossbrand", "explosion", "terror", "amok"), 6),
            (("kampfmittel", "chemikal", "trinkwasserverunreinigung", "ausfall", "blackout"), 5),
            (("hochwasser", "ueberschwemm", "sturm", "orkan", "waldbrand"), 4),
            (("hitz", "glatteis", "schnee", "regen"), 2),
        ):
            if any(keyword in text for keyword in keywords):
                critical_bonus = max(critical_bonus, weight)

        reduction = 0
        for keywords, weight in (
            (("aktualisierung", "fortschreibung", "update", "hinweis"), 1),
            (("schutzchlor", "chlorung", "chlorungsmassnahme", "vorsorglich"), 3),
            (("keine gesundheitsgefahrdung", "keine gesundheitsgefährdung", "entwarnung"), 4),
        ):
            if any(keyword in text for keyword in keywords):
                reduction = max(reduction, weight)

        score = source_weight + severity_weight + critical_bonus - reduction
        return max(2, min(score, 16))

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
            score = self._score_official_alert(alert)
            item = {
                "title": title,
                "link": alert.get("link") or "",
                "summary": severity or f"{source} im Umkreis von Home",
                "published": str(alert.get("sent") or ""),
                "published_dt": self._parse_feed_datetime(str(alert.get("sent") or "")),
                "source": source,
                "score": score,
                "keywords": [],
                "military_keywords": [],
                "military_score": 0,
                "region": "de",
                "latitude": alert.get("latitude"),
                "longitude": alert.get("longitude"),
            }
            item["themes"] = self._classify_item_themes(item)
            items.append(item)
        return items

    def _select_local_alerts_for_headlines(
        self,
        alerts: list[dict],
        local_keywords: list[str],
        home_center: tuple[float | None, float | None],
        radius_km: int,
        focus_mode: str,
    ) -> list[dict]:
        """Select local alerts, preferring warning geometry over text matches."""
        local_alerts: list[dict] = []
        for alert in alerts:
            distance = self._alert_distance_km(alert, home_center)
            if distance is not None:
                alert["distance_km"] = round(distance, 1)
                if distance <= radius_km:
                    local_alerts.append(alert)
                # Known remote geometry must not be overridden by a text hit.
                continue

            haystack = " ".join(
                str(alert.get(field) or "")
                for field in ("title", "severity", "affected_regions", "description")
            ).lower()
            if any(keyword.lower() in haystack for keyword in local_keywords):
                local_alerts.append(alert)

        return local_alerts

    def _filter_alerts_by_radius(
        self,
        alerts: list[dict],
        home_center: tuple[float | None, float | None],
        radius_km: int,
        focus_mode: str,
        local_keywords: list[str] | None = None,
    ) -> list[dict]:
        """Filter official alerts around Home when local mode is enabled."""
        if focus_mode != FOCUS_MODE_LOCAL:
            return alerts

        keywords = local_keywords or []

        filtered: list[dict] = []
        for alert in alerts:
            distance = self._alert_distance_km(alert, home_center)
            if distance is None:
                haystack = " ".join(
                    str(alert.get(field) or "")
                    for field in ("title", "severity", "affected_regions", "description")
                ).lower()
                if any(keyword.lower() in haystack for keyword in keywords):
                    filtered.append(alert)
                continue
            alert["distance_km"] = round(distance, 1)
            if distance <= radius_km:
                filtered.append(alert)
        return filtered

    def _public_alerts(self, alerts: list[dict]) -> list[dict]:
        """Remove internal geometry arrays before publishing sensor attributes."""
        return [
            {key: value for key, value in alert.items() if not key.startswith("_geometry_")}
            for alert in alerts
        ]
