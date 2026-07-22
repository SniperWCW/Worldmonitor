# Lage Monitor for Home Assistant

Custom Home Assistant integration plus Lovelace card for a German and global situation overview.

## What this MVP does

- Pulls official warning data from the BBK NINA API
- Pulls Presseportal RSS feeds, including Blaulicht/Police
- Pulls major German news RSS feeds:
  - tagesschau
  - n-tv
  - stern
  - WELT
- Renders geocoded warning markers on an OpenStreetMap-based card map when coordinates are available
- Exposes a first military activity signal and a derived stability index
- Builds a simple severity heuristic for unrest, attacks, warnings, outages, and public-safety events
- Exposes Home Assistant sensors and a custom dashboard card

## Included sensors

- `sensor.deutschland_lage_score`
- `sensor.welt_lage_score`
- `sensor.aktive_warnungen`
- `sensor.polizei_und_blaulichtmeldungen`
- `sensor.hochpriorisierte_ereignisse`
- `sensor.militärisches_aktivitätssignal`
- `sensor.stabilitätsindex`

The richest attributes live on the Germany score entity:

- `alerts`
- `headlines`
- `sources`
- `last_update`
- `map_markers`
- `military_items`
- `score_breakdown`
- `top_keywords`

## Important note about "unrest" and "attacks"

This MVP does **not** claim to be a certified threat-detection system.
It is a practical situational-awareness aggregator.

The current risk score is based on:

- official alerts
- police and Blaulicht feeds
- news headlines
- keyword weighting
- a separate military keyword signal derived from news content

That is useful for awareness and automation, but it is **not** a substitute for police, civil protection, or intelligence systems.

## Data sources

Official / primary:

- NINA API: https://nina.api.bund.dev/
- Presseportal RSS: https://www.presseportal.de/rss/
- Tagesschau RSS: https://www.tagesschau.de/infoservices/rssfeeds
- n-tv RSS: https://www.n-tv.de/incoming/RSS-Feeds-von-n-tv-de-article10735026.html
- stern RSS: https://www.stern.de/sonst/rss-die-rss-feeds-von-stern-de-3516462.html
- WELT RSS: https://www.welt.de/services/rss/

Additional context for future map and conflict layers:

- OpenStreetMap tile policy: https://operations.osmfoundation.org/policies/tiles/
- OpenSky data overview: https://opensky-network.org/data
- UCDP API: https://ucdp.uu.se/apidocs/

## Installation

Copy the custom component into your Home Assistant config directory:

```text
custom_components/lage_monitor/
```

The dashboard card is part of the custom component and now lives here:

```text
custom_components/lage_monitor/frontend/lage-monitor-card.js
```

Then in Home Assistant:

1. Restart Home Assistant
2. The integration now tries to auto-register the Lovelace resource at `/lage_monitor_frontend/lage-monitor-card.js`
3. If your dashboard uses YAML mode or Home Assistant blocks storage-resource creation, add this fallback manually:

```yaml
lovelace:
  resources:
    - url: /lage_monitor_frontend/lage-monitor-card.js
      type: module
```

4. Add the integration via the UI
5. Create a card using:

```yaml
type: custom:lage-monitor-card
entity: sensor.deutschland_lage_score
alerts_entity: sensor.aktive_warnungen
stability_entity: sensor.stabilitätsindex
military_entity: sensor.militärisches_aktivitätssignal
title: Lage Monitor
limit: 8
```

## Recommended next steps

1. Add optional international event feeds like ACLED, GDELT, and USGS
2. Add configurable keyword profiles for terrorism, civil unrest, infrastructure, and weather
3. Add geo-filtering for Germany states or local radius
4. Add OpenSky-backed air activity when you want real movement data instead of keyword-only military signals
5. Add push automations when the score or keyword profile crosses a threshold
