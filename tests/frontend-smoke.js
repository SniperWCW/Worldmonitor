"use strict";

const assert = require("node:assert/strict");

const registry = new Map();
global.customElements = {
  define(name, value) {
    registry.set(name, value);
  }
};
global.window = {
  customCards: [],
  localStorage: {
    getItem() { return JSON.stringify({ infra: true, live: true }); },
    setItem() {}
  },
  setTimeout() {}
};
global.document = {
  querySelector() { return null; },
  createElement() {
    return { set rel(_value) {}, set href(_value) {}, onload: null, onerror: null };
  },
  head: { appendChild() {} }
};
global.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = {
      innerHTML: "",
      querySelectorAll() { return []; },
      getElementById() { return null; }
    };
  }
};

require("../custom_components/lage_monitor/frontend/lage-monitor-card.js");

const Card = registry.get("lage-monitor-card");
assert.ok(Card, "custom card should register");

const card = new Card();
card.setConfig({ title: "Lage <Monitor>" });
card.hass = {
  states: {
    "sensor.germany_score": {
      state: "72",
      attributes: {
        global_score: 58,
        local_score: 84,
        alerts: [],
        local_alerts: [],
        local_headlines: [{
          title: "<img src=x onerror=alert(1)>",
          summary: "<script>bad()</script>",
          source: "custom_press_1",
          link: "javascript:alert(1)",
          score: 12,
          published: "2026-10-03T12:00:00+00:00"
        }],
        germany_headlines: [],
        world_headlines: [],
        map_markers: [],
        military_items_germany: [],
        military_items_local: [],
        military_items_world: [],
        analysis_summary: {
          local: { headline: "Im Umkreis aktuell ruhig.", status: { key: "good", label: "Ruhig" }, changes: [] }
        },
        history_summary: { local: { series: [80, 84], label_24h: "+4", label_7d: "0" } },
        source_freshness: [],
        data_quality: {
          score: 75,
          label: "mittel",
          healthy_sources: 3,
          total_sources: 4,
          scope_sources: { local: 1, germany: 2, world: 1 }
        },
        theme_scores: { local: {} },
        scope_counts: { local: { alerts: 0, military: 0 } },
        diagnostics: { alert_radius_km: 25 },
        last_update: "2026-10-03T12:00:00+00:00",
        top_keywords: [],
        layer_items: [
          { layer: "road", key: "closure:1", title: "A8 | <b>Sperrung</b>", detail: "Vollsperrung", severity: 2, road: "A8", latitude: 48.8, longitude: 9.0, distance_km: 12.3 },
          { layer: "webcams", key: "webcam:1", title: "Cam", image: "javascript:alert(1)", severity: 0, latitude: 48.8, longitude: 9.0 },
          { layer: "webcams", key: "webcam:2", title: "Route <u>Cam</u>", image: "https://example.org/a.jpg", on_route: true, severity: 0, latitude: 48.8, longitude: 9.0 }
        ],
        live_streams: [
          { label: "Tagesschau <i>24</i>", type: "youtube", url: "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", region: "DE" },
          { label: "Garage", type: "camera", url: "camera.garage", region: "" }
        ]
      }
    },
    "sensor.active_alerts": { state: "0" },
    "sensor.stability_index": { state: "68" },
    "sensor.military_signal_score": { state: "80" },
    "zone.home": { attributes: { latitude: 48.7, longitude: 9.1 } }
  }
};

const html = card.shadowRoot.innerHTML;
assert.match(html, /Automatische Lageeinschätzung/);
assert.match(html, /Umkreis 25 km/);
assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
assert.doesNotMatch(html, /<script>bad\(\)<\/script>/);
assert.doesNotMatch(html, /href="javascript:/);
assert.match(html, /Eigene Pressequelle 1/);
assert.match(html, /Lage &lt;Monitor&gt;/);

assert.match(html, /Verkehr, Pegel &amp; Messwerte/);
assert.match(html, /Live &amp; Kameras/);
assert.match(html, /Kameras auf deinen Strecken/);
assert.match(html, /src="https:\/\/example.org\/a.jpg"/);
assert.doesNotMatch(html, /<u>Cam<\/u>/);
assert.doesNotMatch(html, /javascript:alert\(1\)" alt/);
assert.doesNotMatch(html, /<b>Sperrung<\/b>/);
assert.doesNotMatch(html, /<i>24<\/i>/);

console.log("frontend smoke test passed");
