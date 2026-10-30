# Changelog

## 0.3.2 - 2026-10-30

### Fixed

- The BfS radiation layer timed out because it downloaded all ~1,600 stations; the dose-rate filter (0.3 uSv/h) is now applied by the server.
- The Autobahn layer listed every ramp and phase of a large roadworks site separately and included announced future works. It now shows one entry per measure, only currently relevant ones, at most 25.

## 0.3.1 - 2026-10-30

### Added

- **Live & Kameras:** new card panel with a configurable list of streams and cameras (options field "Live-Streams und Kameras", one `Name | URL or camera.entity | region` per line). Supports YouTube links (privacy embed, loaded only after a tap), HLS (`.m3u8`), snapshot image URLs (reloaded every 30 s) and Home Assistant `camera.*` entities. No stream addresses are shipped as defaults.
- **Autobahn layer (optional):** webcams (still images), closures and traffic warnings for the configured motorways (`A8, A81`, max. 8) from the Autobahn GmbH API, shown on the map and in a new "Verkehr, Pegel & Messwerte" panel.
- **Water levels (optional):** PEGELONLINE gauges within the local radius at flood mark (Meldestufe) 1 or higher.
- **Radiation (optional):** BfS ODL stations with a dose rate of 0.3 uSv/h or more.
- **Alert events:** the `lage_monitor_alert` event is fired on the Home Assistant bus for status changes, score drops (default 15 points, 0 = off), new local official warnings, rising flood marks and elevated radiation stations. Optional notify service and per-event cooldown (default 60 min). The first refresh after a restart only seeds the baseline.
- New sensor attributes `layer_items` and `live_streams` (excluded from the recorder).

### Changed

- Version 0.3.0 was never published; 0.3.1 is the first release containing these changes.
- New release workflow: a push to master that changes the version in `manifest.json` (or a pushed `v*.*.*` tag) publishes a GitHub release with notes from this file and `lage_monitor.zip`.
- GeoJSON geometry parsing moved from `coordinator.py` to the pure module `geometry.py`; new sources live in the `sources/` package and `layers.py`, so the coordinator no longer grows with every source.

### Notes

- Everything new is off by default. The Autobahn, PEGELONLINE and BfS parsers follow the published API documentation and are unit-tested with sample payloads; they have not been run against the live services yet.

## 0.2.4 - 2026-10-16

### Fixed

- The Lovelace card resource is no longer registered twice. The resource collection is now loaded before it is checked, concurrent setup calls are guarded, and duplicate entries left over from earlier versions are removed automatically.

## 0.2.3 - 2026-10-04

### Changed

- Switched the default raster background from the blocked OSM Foundation endpoint to the German OSM tile service, which permits smaller non-commercial web applications under its usage policy.
- Added configurable XYZ tile URL and plain-text attribution fields to the Lovelace card editor.

### Fixed

- Tile requests now explicitly send an origin referrer and display the complete OpenStreetMap contributor attribution.
- Rejected tile responses are replaced with a neutral background and a compact provider warning instead of rendering the upstream 403 image.

## 0.2.2 - 2026-10-04

### Fixed

- MoWaS and other official warnings now always respect the configured Home radius in local focus mode, even when a warning district is configured.
- Radius checks use the complete Polygon or MultiPolygon warning area, including holes, instead of only its center point.
- GeoJSON coordinates are interpreted in the RFC-defined longitude/latitude order and validated before use.
- Map markers use an area-weighted warning centroid, while diagnostic attributes expose distance and geocoding precision without publishing large geometry arrays.
- A local keyword can no longer pull an already geocoded remote warning into the local list.
- Affected-region text is used only as a fallback when warning geometry is unavailable.
- Reset persisted score history because stricter local warning selection changes the local score semantics.

## 0.2.1 - 2026-10-03

### Changed

- Unified backend and frontend status thresholds so score, label, and narrative agree.
- Reduced routine police notices below the primary relevance threshold while preserving serious public-impact incidents.
- Reset persisted score history because the new relevance floor changes score semantics.
- Made official warning and military counts specific to the selected local, Germany, or world focus.
- Compact mobile hero now keeps quality signals in one row and avoids empty chart space.
- Shows three primary events initially, with explicit expansion and lower-priority hints separated.

### Added

- Clickable theme cards that filter both the event list and map.
- Per-item theme metadata and cluster-based theme signal counts.

### Fixed

- Local scores no longer include contextual events below the relevance threshold.
- Local military lists no longer reuse all Germany-wide military events.
- Raw internal source names are no longer appended to the local driver sentence.

## 0.2.0 - 2026-10-03

### Changed

- Reworked Germany, world, and local scores with strict regional separation.
- Added near-duplicate clustering, source corroboration, time decay, and bounded normalization.
- Replaced overlapping stability deductions with a transparent Germany/world composite.
- Reset persisted score history once because v0.2.0 changes the score semantics.
- Redesigned the Lovelace card around local, Germany, and world focus tabs.
- Added seven-day sparklines, 24-hour/7-day deltas, thematic risk cards, and change summaries.
- Renamed the rule-based "KI Lagebewertung" to "Automatische Lageeinschätzung".
- Made the map focus-aware and collapsed by default.

### Added

- Separate data-quality score with healthy, stale, and failed source counts.
- Theme risk for security, infrastructure, nature, and military signals.
- Human-readable source labels and publication times.
- Regression tests for regional score separation, decay, deduplication, source quality, and frontend safety.

### Fixed

- German items no longer influence the world score.
- Leaflet panes and controls can no longer overlap the Home Assistant app header.
- Mobile score and metric layouts no longer remain forced into three/four columns.
- External feed titles, summaries, sources, links, keywords, and configuration values are escaped or validated before rendering.
