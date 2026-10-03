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
    getItem() { return null; },
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
        military_items_world: [],
        analysis_summary: {
          local: { headline: "Im Umkreis aktuell ruhig.", changes: [] }
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
        diagnostics: { alert_radius_km: 25 },
        last_update: "2026-10-03T12:00:00+00:00",
        top_keywords: []
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

console.log("frontend smoke test passed");
