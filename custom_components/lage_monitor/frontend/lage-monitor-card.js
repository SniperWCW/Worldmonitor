const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const DEFAULT_CONFIG = {
  entity: "sensor.germany_score",
  alerts_entity: "sensor.active_alerts",
  stability_entity: "sensor.stability_index",
  military_entity: "sensor.military_signal_score",
  title: "Lage Monitor",
  limit: 5,
  zoom: 6,
  map_height: 320,
  show_map: true,
  show_keywords: true,
  show_military: true
};

let leafletLoader;

function ensureLeaflet() {
  if (window.L) {
    return Promise.resolve(window.L);
  }
  if (leafletLoader) {
    return leafletLoader;
  }

  leafletLoader = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = LEAFLET_CSS;
      document.head.appendChild(css);
    }

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve(window.L);
    script.onerror = reject;
    document.head.appendChild(script);
  });

  return leafletLoader;
}

class LageMonitorCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
  }

  set hass(hass) {
    const config = this._config || DEFAULT_CONFIG;
    const stateObj = hass.states[config.entity];
    if (!stateObj) {
      this.innerHTML = `<ha-card><div class="card-content">Entity ${config.entity} not found.</div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes;
    const headlines = (attrs.headlines || []).slice(0, config.limit);
    const alerts = (attrs.alerts || []).slice(0, 4);
    const keywords = (attrs.top_keywords || []).slice(0, 5);
    const markers = attrs.map_markers || [];
    const militaryItems = (attrs.military_items || []).slice(0, 4);
    const stability = hass.states[config.stability_entity]?.state;
    const military = hass.states[config.military_entity]?.state;
    const activeAlerts = hass.states[config.alerts_entity]?.state || alerts.length;

    this.innerHTML = `
      <ha-card header="${config.title}">
        <div class="wrapper">
          <div class="score-row">
            <div class="score-block">
              <div class="label">Deutschland</div>
              <div class="value">${stateObj.state}</div>
            </div>
            <div class="score-block">
              <div class="label">Aktive Warnungen</div>
              <div class="value">${activeAlerts}</div>
            </div>
          </div>
          <div class="score-row three">
            <div class="score-block compact">
              <div class="label">Stabilitaetsindex</div>
              <div class="value small">${stability ?? "-"}</div>
            </div>
            <div class="score-block compact">
              <div class="label">Militaersignal</div>
              <div class="value small">${military ?? "-"}</div>
            </div>
            <div class="score-block compact">
              <div class="label">Marker</div>
              <div class="value small">${markers.length}</div>
            </div>
          </div>
          ${config.show_map ? `
            <div class="section">
              <div class="section-title">Lagekarte</div>
              <div id="map" style="min-height:${Number(config.map_height) || 320}px"></div>
              <div class="map-note">Kartengrundlage: OpenStreetMap. Fuer groessere Nutzung sollten wir spaeter einen eigenen oder geeigneten Tile-Provider einplanen.</div>
            </div>
          ` : ""}
          <div class="section">
            <div class="section-title">Top-Ereignisse</div>
            ${headlines.map((item) => `
              <div class="item">
                <div class="item-top">
                  <span class="badge">${item.score}</span>
                  <span class="source">${item.source}</span>
                </div>
                <a href="${item.link || "#"}" target="_blank" rel="noreferrer">${item.title}</a>
                <div class="summary">${item.summary || ""}</div>
              </div>
            `).join("")}
          </div>
          <div class="section">
            <div class="section-title">Amtliche Warnungen</div>
            ${alerts.length ? alerts.map((item) => `
              <div class="alert-item">
                <span class="source">${item.source}</span>
                <span>${item.title || "Warnung ohne Titel"}</span>
              </div>
            `).join("") : `<div class="empty">Keine Warnungen vorhanden</div>`}
          </div>
          ${config.show_military ? `
            <div class="section">
              <div class="section-title">Militaerische Aktivitaet</div>
              ${militaryItems.length ? militaryItems.map((item) => `
                <div class="alert-item">
                  <span class="source">${item.source}</span>
                  <span>${item.title}</span>
                </div>
              `).join("") : `<div class="empty">Noch keine militaerischen Signalereignisse erkannt</div>`}
            </div>
          ` : ""}
          ${config.show_keywords ? `
            <div class="section">
              <div class="section-title">Schluesselbegriffe</div>
              <div class="chips">
                ${keywords.map((item) => `<span class="chip">${item.keyword} (${item.count})</span>`).join("")}
              </div>
            </div>
          ` : ""}
        </div>
      </ha-card>
    `;

    if (config.show_map) {
      this._renderMap(markers, config.zoom);
    }
  }

  getCardSize() {
    return 8;
  }

  async _renderMap(markers, zoom) {
    const mapRoot = this.querySelector("#map");
    if (!mapRoot) {
      return;
    }

    if (!markers.length) {
      mapRoot.innerHTML = `<div class="empty map-empty">Keine geokodierten Warnungen verfuegbar</div>`;
      return;
    }

    const L = await ensureLeaflet();
    if (this._map) {
      this._map.remove();
      this._map = null;
    }

    this._map = L.map(mapRoot, { zoomControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18
    }).addTo(this._map);

    const bounds = [];
    for (const marker of markers) {
      const lat = Number(marker.latitude);
      const lon = Number(marker.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        continue;
      }
      const leafletMarker = L.marker([lat, lon]).addTo(this._map);
      leafletMarker.bindPopup(`
        <strong>${marker.title || "Warnung"}</strong><br>
        ${marker.source || ""}<br>
        ${marker.severity || ""}
      `);
      bounds.push([lat, lon]);
    }

    if (bounds.length === 1) {
      this._map.setView(bounds[0], zoom || 6);
    } else if (bounds.length > 1) {
      this._map.fitBounds(bounds, { padding: [24, 24] });
    } else {
      this._map.setView([51.1657, 10.4515], zoom || 6);
    }
  }

  static getConfigElement() {
    return document.createElement("lage-monitor-card-editor");
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }
}

class LageMonitorCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
    this._render();
  }

  _render() {
    const config = this._config || DEFAULT_CONFIG;
    this.innerHTML = `
      <div class="editor">
        ${this._field("title", "Titel", config.title)}
        ${this._field("limit", "Anzahl Ereignisse", config.limit, "number")}
        ${this._field("zoom", "Karten-Zoom", config.zoom, "number")}
        ${this._field("map_height", "Kartenhoehe", config.map_height, "number")}
        ${this._field("entity", "Score-Entity", config.entity)}
        ${this._field("alerts_entity", "Alerts-Entity", config.alerts_entity)}
        ${this._field("stability_entity", "Stabilitaets-Entity", config.stability_entity)}
        ${this._field("military_entity", "Militaer-Entity", config.military_entity)}
        ${this._toggle("show_map", "Karte anzeigen", config.show_map)}
        ${this._toggle("show_keywords", "Schluesselbegriffe anzeigen", config.show_keywords)}
        ${this._toggle("show_military", "Militaerbereich anzeigen", config.show_military)}
      </div>
    `;

    this.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", (event) => this._valueChanged(event));
    });
  }

  _field(key, label, value, type = "text") {
    return `
      <label class="editor-row">
        <span>${label}</span>
        <input data-key="${key}" type="${type}" value="${value ?? ""}">
      </label>
    `;
  }

  _toggle(key, label, checked) {
    return `
      <label class="editor-row checkbox">
        <span>${label}</span>
        <input data-key="${key}" type="checkbox" ${checked ? "checked" : ""}>
      </label>
    `;
  }

  _valueChanged(event) {
    const target = event.target;
    const key = target.dataset.key;
    let value;

    if (target.type === "checkbox") {
      value = target.checked;
    } else if (target.type === "number") {
      value = Number(target.value);
    } else {
      value = target.value;
    }

    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config }
    }));
  }
}

customElements.define("lage-monitor-card", LageMonitorCard);
customElements.define("lage-monitor-card-editor", LageMonitorCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "lage-monitor-card",
  name: "Lage Monitor Card",
  description: "Shows a Germany/world situation overview with alerts and top headlines.",
  preview: true
});

const style = document.createElement("style");
style.textContent = `
  :host {
    display: block;
  }
  .wrapper {
    padding: 16px;
  }
  .score-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .score-row.three {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .score-block {
    background: var(--ha-card-background, rgba(255,255,255,0.04));
    border: 1px solid var(--divider-color);
    border-radius: 12px;
    padding: 12px;
  }
  .score-block.compact {
    padding: 10px 12px;
  }
  .label {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    margin-bottom: 4px;
  }
  .value {
    font-size: 1.8rem;
    font-weight: 700;
  }
  .value.small {
    font-size: 1.3rem;
  }
  .section {
    margin-top: 14px;
  }
  .section-title {
    font-weight: 700;
    margin-bottom: 8px;
  }
  .item, .alert-item {
    border-top: 1px solid var(--divider-color);
    padding: 10px 0;
  }
  .item-top {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 4px;
  }
  .badge {
    background: #b42318;
    color: white;
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.75rem;
  }
  .source {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    text-transform: uppercase;
  }
  .summary {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
    margin-top: 4px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  #map {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--divider-color);
  }
  .map-note {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    margin-top: 8px;
  }
  .chip {
    border: 1px solid var(--divider-color);
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 0.8rem;
  }
  .empty {
    color: var(--secondary-text-color);
  }
  .map-empty {
    padding: 16px;
  }
  .editor {
    display: grid;
    gap: 12px;
    padding: 16px 0;
  }
  .editor-row {
    display: grid;
    gap: 6px;
  }
  .editor-row.checkbox {
    grid-template-columns: 1fr auto;
    align-items: center;
  }
  .editor input {
    padding: 8px;
    border-radius: 8px;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color);
    color: var(--primary-text-color);
  }
`;

if (!document.head.querySelector('style[data-lage-monitor-style="1"]')) {
  style.dataset.lageMonitorStyle = "1";
  document.head.appendChild(style);
}
