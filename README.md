# Lage Monitor for Home Assistant

Custom Home Assistant integration plus Lovelace card for a German and global situation overview.

## What it does

- Pulls official warning data from the BBK NINA API
- Pulls Presseportal RSS feeds, including Blaulicht/Police
- Pulls major German news RSS feeds:
  - tagesschau
  - n-tv
  - stern
  - WELT
- Renders focus-aware local, German, and global map layers with geocoded warnings and news
- Exposes military signals, thematic risk values, source quality, trends, and a derived stability index
- De-duplicates similar stories, applies time decay, and moderately rewards independent confirmation
- Separates the situation score from confidence in the available source data
- Provides a mobile-first dashboard card with focus tabs, sparklines, and progressive disclosure

## Included sensors

- `sensor.germany_score`
- `sensor.global_score`
- `sensor.active_alerts`
- `sensor.police_items`
- `sensor.high_priority_items`
- `sensor.military_signal_score`
- `sensor.stability_index`
- `sensor.diagnostic_state`

The richest attributes live on the Germany score entity:

- `alerts`
- `local_alerts`
- `analysis_summary`
- `headlines`
- `sources`
- `last_update`
- `map_markers`
- `military_items`
- `military_items_local`
- `risk_drivers`
- `score_trend`
- `source_status`
- `diagnostics`
- `score_breakdown`
- `top_keywords`
- `data_quality`
- `theme_scores`
- `scope_counts`
- `history_summary`
- `source_freshness`

## Important note about "unrest" and "attacks"

This MVP does **not** claim to be a certified threat-detection system.
It is a practical situational-awareness aggregator.

The current risk score is based on:

- official alerts
- police and Blaulicht feeds
- news headlines
- keyword weighting
- a separate military keyword signal derived from news content
- source-aware near-duplicate clustering and age-based decay

The card uses two deliberately different scales:

- **Situation score:** 100 means calm, 0 means critical.
- **Theme risk:** 0 means no current signal, 100 means high current burden.

`data_quality` is shown separately. A calm score with weak or stale source coverage
must not be read as confirmation that nothing is happening.

That is useful for awareness and automation, but it is **not** a substitute for police, civil protection, or intelligence systems.

## Data sources

Official / primary:

- NINA API: https://nina.api.bund.dev/
- Presseportal RSS: https://www.presseportal.de/rss/
- Tagesschau RSS: https://www.tagesschau.de/infoservices/rssfeeds
- n-tv RSS: https://www.n-tv.de/incoming/RSS-Feeds-von-n-tv-de-article10735026.html
- stern RSS: https://www.stern.de/sonst/rss-die-rss-feeds-von-stern-de-3516462.html
- WELT RSS: https://www.welt.de/services/rss/

Optional layers (0.3.0):

- Autobahn API: https://autobahn.api.bund.dev/
- PEGELONLINE: https://pegelonline.wsv.de/webservice/dokuRestapi
- BfS ODL: https://odlinfo.bfs.de/ODL/EN/service/data-interface/data-interface.html

Additional context for future map and conflict layers:

- OpenStreetMap tile policy: https://operations.osmfoundation.org/policies/tiles/
- OpenStreetMap.de German tile service: https://www.openstreetmap.de/germanstyle/
- OpenSky data overview: https://opensky-network.org/data
- UCDP API: https://ucdp.uu.se/apidocs/

## Installation

Copy the custom component into your Home Assistant config directory:

```text
custom_components/lage_monitor/
```

The dashboard card is part of the custom component and lives here:

```text
custom_components/lage_monitor/frontend/lage-monitor-card.js
```

Then in Home Assistant:

1. Restart Home Assistant
2. The integration tries to auto-register the Lovelace resource at `/lage_monitor_frontend/lage-monitor-card.js`
3. If your dashboard uses YAML mode or Home Assistant blocks storage-resource creation, add this fallback manually:

```yaml
lovelace:
  resources:
    - url: /lage_monitor_frontend/lage-monitor-card.js
      type: module
```

4. Add the integration via the UI
5. Create a card using the UI editor or minimal YAML:

```yaml
type: custom:lage-monitor-card
```

Optional full YAML with overrides:

```yaml
type: custom:lage-monitor-card
title: Lage Monitor
limit: 5
zoom: 6
map_height: 320
tile_url: https://tile.openstreetmap.de/{z}/{x}/{y}.png
tile_attribution: © OpenStreetMap contributors
show_map: true
show_keywords: true
show_military: true
entity: sensor.germany_score
alerts_entity: sensor.active_alerts
stability_entity: sensor.stability_index
military_entity: sensor.military_signal_score
```

`tile_url` accepts HTTPS/HTTP or same-origin XYZ templates containing `{z}`, `{x}`, and `{y}`.
When another provider is configured, its required attribution must be entered in
`tile_attribution`. The card sends an origin referrer and otherwise relies on normal browser
caching; offline downloads or tile prefetching are not implemented.

## Live streams, cameras and extra layers (0.3.0)

All of this is optional and off by default. Set it up under *Settings > Devices & services > Lage Monitor > Configure*.

**Live & Kameras.** One entry per line in the field "Live-Streams und Kameras":

```text
# Name | URL or camera entity | optional region
Tagesschau24 | https://www.youtube.com/watch?v=VIDEO_ID | Nachrichten
Garage | camera.garage
Pegel Neckar | https://example.org/cam.jpg | Lokal
```

- YouTube links become a privacy embed that loads only after a tap. Some in-app web views block YouTube embeds.
- `.m3u8` streams use native HLS playback. Desktop Chrome may not support this; add the stream as a `camera.*` entity (generic camera) instead.
- Image URLs are reloaded every 30 seconds.
- Stream addresses change and have their own terms of use, so none are included. Please check each one yourself.

**Extra map layers**

| Option | Source | Shows |
| --- | --- | --- |
| Autobahnen (`A8, A81`, max. 8) | Autobahn GmbH API | Webcam stills, closures, traffic warnings within twice the local radius |
| Pegelstände | PEGELONLINE | Gauges in the local radius at flood mark 1 or higher |
| Strahlung | BfS ODL | Stations with 0.3 uSv/h or more |

**My routes.** One line per route in "Meine Strecken": `A81 | Feuerbach, Ludwigsburg`. The keywords are exits or places as they appear in the reports (umlauts are optional); a line with only `A8` covers the whole motorway. Reports and webcams of your routes appear even outside the local radius, marked "Meine Strecke", with delay and speed, and the panel shows the route webcam images.

**Testing alerts.** Call the service `lage_monitor.test_alert` (Developer tools > Actions) to fire a test event with `type: test`. For ready-made push messages import the blueprint *Lage Monitor – Ereignis melden* from `blueprints/automation/lage_monitor/alert_notify.yaml` and pick an action, for example a notification with the message `{{ trigger.event.data.title }}`.

**Automations.** Changes are published as the `lage_monitor_alert` event with `type` (`status_change`, `score_drop`, `new_official_alert`, `flood_level`, `radiation_elevated`, `route_delay`, `test`), `direction` (`worse`/`better`), `title` and type-specific fields:

```yaml
automation:
  - alias: Lage verschlechtert
    triggers:
      - trigger: event
        event_type: lage_monitor_alert
        event_data:
          direction: worse
    actions:
      - action: notify.mobile_app_mein_handy
        data:
          message: "{{ trigger.event.data.title }}"
```

Or enter a notify service in the options to be notified without writing an automation.

## Recommended next steps

1. Add optional conflict feeds such as ACLED or UCDP
2. Add NASA FIRMS for fire and heat anomalies (needs a free MAP_KEY)
3. Add OpenSky-backed air activity when real movement data is desired
4. Add optional generated briefings only when explicitly enabled

See also `ROADMAP.md` for the current project roadmap and planned intelligence features.
