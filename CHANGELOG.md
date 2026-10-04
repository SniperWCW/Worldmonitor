# Changelog

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
