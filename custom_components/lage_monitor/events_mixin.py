"""USGS / EONET events and map marker building."""

from __future__ import annotations

import asyncio
from typing import Any

from .const import (
    EONET_EVENTS_API_URL,
    EVENTS_MAX_STALE,
    EVENTS_MIN_INTERVAL,
    FOCUS_MODE_LOCAL,
    GERMANY_BBOX,
    USGS_EARTHQUAKE_FEED_URL,
)
from . import geo, geometry
from .feed import fetch_json_conditional
from .fetchcache import SourcePolicy
from .scoring import cluster_items
from .common import _LOGGER


class EventsMixin:
    """USGS / EONET events and map marker building."""

    async def _safe_fetch_public_event_items(
        self,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Fetch keyless structured event sources for Germany and the local radius."""
        results = await asyncio.gather(
            self._safe_fetch_usgs_items(home_center, radius_km),
            self._safe_fetch_eonet_items(home_center, radius_km),
            return_exceptions=True,
        )
        items: list[dict] = []
        status: dict[str, dict] = {}
        for source_name, result in zip(("usgs", "eonet"), results, strict=False):
            if isinstance(result, Exception):
                status[source_name] = {"ok": False, "items": 0, "error": str(result)}
                continue
            source_items, source_status = result
            items.extend(source_items)
            status[source_name] = source_status
        items.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
        return items, status

    async def _safe_fetch_usgs_items(
        self,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> tuple[list[dict], dict]:
        """Fetch recent USGS earthquakes (cached, conditional) and normalize hits."""
        policy = SourcePolicy(min_interval=EVENTS_MIN_INTERVAL, max_stale=EVENTS_MAX_STALE)

        async def fetch(etag, last_modified):
            return await fetch_json_conditional(self.hass, USGS_EARTHQUAKE_FEED_URL, etag, last_modified)

        result = await self._cached_get("events:usgs", fetch, policy)
        if not result.ok:
            _LOGGER.warning("USGS %s: %s", "stale" if result.stale else "failed", result.error)
        if result.value is None:
            return [], result.status(0)
        try:
            items = self._normalize_usgs_items(result.value, home_center, radius_km)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("USGS data could not be processed: %s", err)
            return [], {**result.status(0), "ok": False, "error": f"Verarbeitung: {err}"}
        return items, result.status(len(items))

    async def _safe_fetch_eonet_items(
        self,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> tuple[list[dict], dict]:
        """Fetch recent natural events for Germany and the local radius."""
        params_list = [
            self._eonet_query_params_from_bbox(GERMANY_BBOX, days=14, limit=40),
        ]
        local_bbox = self._bbox_for_home_radius(home_center, radius_km)
        if local_bbox is not None:
            params_list.append(self._eonet_query_params_from_bbox(local_bbox, days=14, limit=25))

        policy = SourcePolicy(min_interval=EVENTS_MIN_INTERVAL, max_stale=EVENTS_MAX_STALE)

        def make_fetch(url: str):
            async def fetch(etag, last_modified):
                return await fetch_json_conditional(self.hass, url, etag, last_modified)

            return fetch

        results = await asyncio.gather(
            *(
                self._cached_get(
                    f"events:eonet:{index}",
                    make_fetch(f"{EONET_EVENTS_API_URL}?{params}"),
                    policy,
                )
                for index, params in enumerate(params_list)
            )
        )

        merged: list[dict] = []
        seen: set[str] = set()
        for result in results:
            events = result.value.get("events") if isinstance(result.value, dict) else None
            if not isinstance(events, list):
                continue
            for event in events:
                item = self._normalize_eonet_event(event, home_center, radius_km)
                if item is None:
                    continue
                key = str(item.get("link") or item.get("title") or "")
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        merged.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
        items = merged[:14]

        failed = [result for result in results if not result.ok]
        errors = "; ".join(sorted({result.error for result in failed if result.error}))
        status = {
            "ok": not failed,
            "items": len(items),
            "error": errors,
            "state": "error" if failed and all(r.value is None for r in failed) else (
                "stale" if failed else "fresh"
            ),
            "stale": any(result.stale for result in results),
            "age_seconds": int(max((result.age for result in results), default=0)),
            "failures": max((result.failures for result in results), default=0),
        }
        if failed:
            _LOGGER.warning("EONET incomplete (%s of %s requests failed): %s", len(failed), len(results), errors)
        return items, status

    def _normalize_usgs_items(
        self,
        data: Any,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> list[dict]:
        """Convert USGS GeoJSON earthquakes into scored items."""
        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            return []

        items: list[dict] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
            geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
            coordinates = geometry.get("coordinates")
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                continue
            lon = self._to_float_or_none(coordinates[0])
            lat = self._to_float_or_none(coordinates[1])
            mag = self._to_float_or_none(properties.get("mag")) or 0.0
            if lat is None or lon is None:
                continue

            is_germany = self._is_in_germany(lat, lon)
            is_local = self._is_within_radius(home_center, lat, lon, radius_km)
            is_near = geo.in_neighborhood(lat, lon)
            if mag < 4.5 and not is_germany and not is_local and not (is_near and mag >= 3.5):
                continue

            title = str(properties.get("title") or properties.get("place") or "Erdbeben").strip()
            place = str(properties.get("place") or "").strip()
            published = self._timestamp_from_epoch_ms(properties.get("time"))
            score = 4 + min(14, int(round(mag * 2)))
            if is_germany:
                score += 4
            if is_local:
                score += 6
            if mag >= 6.0:
                score += 4
            summary = f"USGS Erdbeben Magnitude {mag:.1f}"
            if place:
                summary = f"{summary} bei {place}"
            items.append(
                self._build_structured_item(
                    title=title,
                    summary=summary,
                    source="usgs",
                    published=published,
                    score=score,
                    region="de" if is_germany or is_local else "world",
                    latitude=lat,
                    longitude=lon,
                    severity=f"M{mag:.1f}",
                    keywords=["erdbeben"],
                )
            )
        return items[:12]

    def _normalize_eonet_event(
        self,
        event: dict,
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> dict | None:
        """Convert an EONET event into a scored item."""
        if not isinstance(event, dict):
            return None
        geometry_entries = event.get("geometry")
        if not isinstance(geometry_entries, list) or not geometry_entries:
            return None
        latest_geometry = geometry_entries[-1]
        lat, lon = self._extract_eonet_geometry_center(latest_geometry)
        if lat is None or lon is None:
            return None

        categories = event.get("categories") if isinstance(event.get("categories"), list) else []
        category_titles = [
            str(category.get("title") or category.get("id") or "").strip()
            for category in categories
            if isinstance(category, dict)
        ]
        category_text = ", ".join(title for title in category_titles if title)
        source_titles = [
            str(source.get("id") or source.get("title") or "").strip()
            for source in (event.get("sources") if isinstance(event.get("sources"), list) else [])
            if isinstance(source, dict)
        ]
        title = str(event.get("title") or "Naturereignis").strip()
        link = str(event.get("link") or "").strip()
        published = str(latest_geometry.get("date") or event.get("closed") or "")
        is_germany = self._is_in_germany(lat, lon)
        is_local = self._is_within_radius(home_center, lat, lon, radius_km)
        if not is_germany and not is_local and not geo.in_neighborhood(lat, lon):
            return None

        score = self._score_eonet_categories(category_titles)
        if is_local:
            score += 5
        summary_parts = [part for part in (category_text, ", ".join(source_titles[:2])) if part]
        summary = " | ".join(summary_parts) or "NASA EONET Naturereignis"
        return self._build_structured_item(
            title=title,
            summary=summary,
            source="eonet",
            published=published,
            score=score,
            region="de" if is_germany or is_local else "world",
            latitude=lat,
            longitude=lon,
            severity=category_text or "Naturereignis",
            keywords=[title.lower() for title in category_titles[:2] if title] or ["naturereignis"],
            link=link,
        )

    def _eonet_query_params_from_bbox(
        self,
        bbox: tuple[float, float, float, float],
        *,
        days: int,
        limit: int,
    ) -> str:
        """Return encoded EONET query parameters for a bbox search."""
        min_lon, max_lat, max_lon, min_lat = bbox
        return (
            f"status=all&days={days}&limit={limit}"
            f"&bbox={min_lon},{max_lat},{max_lon},{min_lat}"
        )

    def _extract_eonet_geometry_center(self, geometry: dict) -> tuple[float | None, float | None]:
        """Return a representative coordinate for an EONET geometry object."""
        if not isinstance(geometry, dict):
            return None, None
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": geometry.get("type"),
                "coordinates": geometry.get("coordinates"),
            },
        }
        return self._centroid_from_geojson(geojson)

    def _score_eonet_categories(self, categories: list[str]) -> int:
        """Assign a simple risk score to public natural-event categories."""
        normalized = [self._normalize_text(category) for category in categories]
        if any(category in normalized for category in ("severestorms", "wildfires", "floods")):
            return 14
        if any(category in normalized for category in ("volcanoes", "landslides")):
            return 12
        if any(category in normalized for category in ("seaandlakeice", "drought")):
            return 9
        return 8

    def _build_map_markers(
        self,
        alerts: list[dict],
        scored_items: list[dict],
        home_center: tuple[float | None, float | None],
        local_keywords: list[str],
        radius_km: int,
        focus_mode: str,
    ) -> list[dict]:
        """Build map markers from local alerts plus geolocated news items."""
        markers: list[dict] = []
        map_items = self._build_alert_map_items(alerts, home_center, radius_km) + self._build_news_map_items(
            scored_items,
            home_center,
            local_keywords,
            radius_km,
            focus_mode,
        )
        clustered: dict[tuple[float, float], list[dict]] = {}

        for item in map_items:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            key = (round(float(lat) / 0.35) * 0.35, round(float(lon) / 0.5) * 0.5)
            clustered.setdefault(key, []).append(item)

        for (lat, lon), cluster_alerts in clustered.items():
            cluster_items = [
                {
                    "title": str(item.get("title") or "Meldung"),
                    "source": str(item.get("source") or ""),
                    "severity": str(item.get("severity") or ""),
                    "link": str(item.get("link") or ""),
                    "region": str(item.get("region") or "de"),
                    "local": bool(item.get("local")),
                    "themes": list(item.get("themes") or []),
                }
                for item in cluster_alerts[:5]
            ]
            top_titles = [item["title"] for item in cluster_items[:3]]
            sources = sorted({str(item.get("source") or "") for item in cluster_alerts if item.get("source")})
            themes = sorted({
                str(theme)
                for item in cluster_alerts
                for theme in (item.get("themes") or [])
                if str(theme)
            })
            markers.append(
                {
                    "key": f"cluster:{round(lat, 5)}:{round(lon, 5)}",
                    "kind": "cluster",
                    "title": top_titles[0],
                    "source": ", ".join(sources[:3]),
                    "severity": f"{len(cluster_alerts)} Meldungen/News",
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "count": len(cluster_alerts),
                    "titles": top_titles,
                    "items": cluster_items,
                    "region": "world" if all(item.get("region") == "world" for item in cluster_alerts) else "de",
                    "local": any(bool(item.get("local")) for item in cluster_alerts),
                    "themes": themes,
                }
            )

        home_lat, home_lon = home_center
        if isinstance(home_lat, (int, float)) and isinstance(home_lon, (int, float)):
            markers.append(
                {
                    "key": f"home:{round(float(home_lat), 5)}:{round(float(home_lon), 5)}",
                    "kind": "home",
                    "title": "Home",
                    "source": "zone.home",
                    "severity": "Home Assistant Fokus",
                    "latitude": float(home_lat),
                    "longitude": float(home_lon),
                    "count": 1,
                    "items": [],
                    "region": "local",
                    "local": True,
                    "themes": [],
                }
            )

        markers.sort(key=lambda item: (item.get("kind") == "home", item.get("count", 0)), reverse=True)
        return markers

    def _build_alert_map_items(
        self,
        alerts: list[dict],
        home_center: tuple[float | None, float | None],
        radius_km: int,
    ) -> list[dict]:
        """Convert today's local alerts into map items."""
        items: list[dict] = []
        for alert in self._filter_alerts_for_today(alerts):
            lat = alert.get("latitude")
            lon = alert.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            distance = self._alert_distance_km(alert, home_center)
            item = {
                "title": str(alert.get("title") or "Warnung"),
                "source": str(alert.get("source") or ""),
                "severity": str(alert.get("severity") or ""),
                "link": str(alert.get("link") or ""),
                "latitude": float(lat),
                "longitude": float(lon),
                "region": "de",
                "local": distance is not None and distance <= radius_km,
            }
            item["themes"] = self._classify_item_themes({
                "title": item["title"],
                "summary": item["severity"],
                "keywords": [],
                "military_score": 0,
            })
            items.append(item)
        return items

    def _build_news_map_items(
        self,
        scored_items: list[dict],
        home_center: tuple[float | None, float | None],
        local_keywords: list[str],
        radius_km: int,
        focus_mode: str,
    ) -> list[dict]:
        """Geolocate high-value news items for the map."""
        items: list[dict] = []
        home_lat, home_lon = home_center
        seen: set[str] = set()
        scope_counts = {"de": 0, "world": 0}

        for item in scored_items:
            if item.get("source") in {"mowas", "biwapp", "katwarn", "dwd", "lhp", "police"}:
                continue
            score = int(item.get("score") or 0)
            if score < 8:
                continue
            region = "world" if item.get("region") == "world" else "de"
            if scope_counts[region] >= 8:
                continue

            lat, lon, severity = self._resolve_news_coordinates(item, local_keywords, home_center)
            if lat is None or lon is None:
                continue
            if (
                focus_mode == FOCUS_MODE_LOCAL
                and home_lat is not None
                and home_lon is not None
                and self._haversine_km(home_lat, home_lon, lat, lon) > radius_km
                and severity != "Lokale News am Home-Fokus"
            ):
                continue

            key = str(item.get("link") or item.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": str(item.get("title") or "News"),
                    "source": str(item.get("source") or ""),
                    "severity": severity,
                    "link": str(item.get("link") or ""),
                    "latitude": lat,
                    "longitude": lon,
                    "region": region,
                    "local": self._is_within_radius(home_center, lat, lon, radius_km),
                    "themes": list(item.get("themes") or []),
                }
            )
            scope_counts[region] += 1
            if all(count >= 8 for count in scope_counts.values()):
                break

        return items

    def _resolve_news_coordinates(
        self,
        item: dict,
        local_keywords: list[str],
        home_center: tuple[float | None, float | None],
    ) -> tuple[float | None, float | None, str]:
        """Resolve a best-effort coordinate for a news item."""
        direct_lat = self._to_float_or_none(item.get("latitude"))
        direct_lon = self._to_float_or_none(item.get("longitude"))
        if direct_lat is not None and direct_lon is not None:
            return direct_lat, direct_lon, str(item.get("severity") or "Ereignis mit Koordinaten")

        text = f"{item.get('title', '')} {item.get('summary', '')}"
        normalized_text = self._normalize_text(text)
        home_lat, home_lon = home_center

        for keyword in local_keywords:
            normalized_keyword = self._normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_text:
                if home_lat is not None and home_lon is not None:
                    return float(home_lat), float(home_lon), "Lokale News am Home-Fokus"

        match = geo.locate(str(item.get("title") or ""), str(item.get("summary") or ""))
        if match is not None:
            return match.lat, match.lon, match.label

        return None, None, ""
