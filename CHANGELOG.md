# Changelog

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
