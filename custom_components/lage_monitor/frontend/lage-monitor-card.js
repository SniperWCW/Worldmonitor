const DEFAULT_CENTER = [51.1657, 10.4515];
const GERMANY_BOUNDS = {
  north: 55.1,
  south: 47.2,
  west: 5.5,
  east: 15.6
};
const ENTITY_CANDIDATES = {
  entity: ["sensor.germany_score", "sensor.deutschland_lage_score"],
  alerts_entity: ["sensor.active_alerts", "sensor.aktive_warnungen"],
  stability_entity: ["sensor.stability_index", "sensor.stabilitaetsindex", "sensor.stabilitatsindex"],
  military_entity: [
    "sensor.military_signal_score",
    "sensor.militärisches_aktivitätssignal",
    "sensor.militaerisches_aktivitaetssignal"
  ]
};
const DEFAULT_CONFIG = {
  title: "Lage Monitor",
  limit: 5,
  zoom: 6,
  map_height: 320,
  show_map: true,
  show_keywords: true,
  show_military: true
};

const CARD_STYLE = `
  :host {
    display: block;
  }
  ha-card {
    overflow: hidden;
    border-radius: 22px;
  }
  .shell {
    padding: 18px;
    background:
      radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 38%),
      radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 30%),
      var(--ha-card-background, var(--card-background-color, #fff));
  }
  .hero {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 14px;
    margin-bottom: 16px;
  }
  .hero-main {
    padding: 18px;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.06);
    border: 1px solid rgba(148, 163, 184, 0.2);
  }
  .title {
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin: 0 0 8px;
  }
  .sub {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
    margin-bottom: 16px;
  }
  .score {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .score-value {
    font-size: 3rem;
    line-height: 1;
    font-weight: 800;
  }
  .score-label {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
  }
  .hero-side {
    display: grid;
    gap: 12px;
  }
  .metric {
    padding: 14px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.18);
    backdrop-filter: blur(6px);
  }
  .metric-label {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .grid {
    display: grid;
    gap: 16px;
  }
  .panel {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.72);
    overflow: hidden;
  }
  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 14px 16px 10px;
  }
  .panel-title {
    font-size: 1rem;
    font-weight: 700;
  }
  .panel-note {
    color: var(--secondary-text-color);
    font-size: 0.76rem;
  }
  .panel-body {
    padding: 0 16px 16px;
  }
  .panel-body.tight {
    padding-top: 6px;
  }
  .items {
    display: grid;
    gap: 12px;
  }
  .item {
    padding-top: 12px;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
  }
  .item:first-child {
    border-top: 0;
    padding-top: 0;
  }
  .item-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .badge {
    min-width: 2.1rem;
    padding: 2px 8px;
    border-radius: 999px;
    background: linear-gradient(135deg, #dc2626, #f97316);
    color: white;
    font-size: 0.75rem;
    text-align: center;
    font-weight: 700;
  }
  .source {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .link {
    color: var(--primary-text-color);
    text-decoration: none;
    font-weight: 600;
    line-height: 1.4;
  }
  .summary {
    color: var(--secondary-text-color);
    font-size: 0.92rem;
    line-height: 1.45;
    margin-top: 6px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip {
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.84);
    font-size: 0.82rem;
  }
  .empty {
    color: var(--secondary-text-color);
    font-size: 0.92rem;
  }
  #map {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.2);
    background:
      linear-gradient(180deg, rgba(191, 219, 254, 0.55), rgba(226, 232, 240, 0.88)),
      radial-gradient(circle at 20% 18%, rgba(37, 99, 235, 0.16), transparent 28%);
    position: relative;
  }
  .map-frame {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: inherit;
    background:
      linear-gradient(90deg, rgba(255, 255, 255, 0.28) 1px, transparent 1px),
      linear-gradient(rgba(255, 255, 255, 0.28) 1px, transparent 1px);
    background-size: 36px 36px;
  }
  .map-shape {
    position: absolute;
    inset: 10% 18% 8%;
    border-radius: 48% 42% 44% 40% / 26% 30% 42% 34%;
    background:
      linear-gradient(180deg, rgba(148, 163, 184, 0.24), rgba(148, 163, 184, 0.16)),
      rgba(255, 255, 255, 0.36);
    border: 1px solid rgba(148, 163, 184, 0.2);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
  }
  .map-label {
    position: absolute;
    top: 14px;
    left: 16px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(15, 23, 42, 0.56);
  }
  .map-marker {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 999px;
    border: 2px solid rgba(255, 255, 255, 0.95);
    background: linear-gradient(135deg, #dc2626, #f97316);
    box-shadow: 0 8px 18px rgba(220, 38, 38, 0.24);
    transform: translate(-50%, -50%);
  }
  .map-marker.secondary {
    background: linear-gradient(135deg, #2563eb, #38bdf8);
    box-shadow: 0 8px 18px rgba(37, 99, 235, 0.24);
  }
  .map-empty {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 18px;
    text-align: center;
    color: var(--secondary-text-color);
    font-size: 0.9rem;
  }
  .panel.collapsible {
    overflow: hidden;
  }
  .panel-toggle {
    width: 100%;
    padding: 0;
    border: 0;
    background: transparent;
    cursor: pointer;
    text-align: left;
  }
  .panel-head.toggle::after {
    content: "▾";
    font-size: 0.92rem;
    color: var(--secondary-text-color);
    transition: transform 0.18s ease;
  }
  .panel.collapsible.collapsed .panel-head.toggle::after {
    transform: rotate(-90deg);
  }
  .count-pill {
    min-width: 1.9rem;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.08);
    color: var(--secondary-text-color);
    font-size: 0.76rem;
    text-align: center;
  }
  .editor {
    display: grid;
    gap: 14px;
    padding: 10px 0 18px;
  }
  .editor-section {
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 18px;
    padding: 14px;
    background: rgba(255, 255, 255, 0.74);
  }
  .editor-title {
    font-weight: 700;
    margin-bottom: 10px;
    font-size: 0.98rem;
  }
  .editor-help {
    color: var(--secondary-text-color);
    font-size: 0.82rem;
    line-height: 1.45;
    margin-bottom: 10px;
  }
  .editor-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .editor-grid.single {
    grid-template-columns: 1fr;
  }
  .editor-row {
    display: grid;
    gap: 5px;
  }
  .editor-label {
    font-size: 0.84rem;
    color: var(--secondary-text-color);
  }
  .editor input[type="text"],
  .editor input[type="number"] {
    width: 100%;
    box-sizing: border-box;
    min-height: 42px;
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.24);
    background: rgba(255, 255, 255, 0.92);
    color: var(--primary-text-color);
    font: inherit;
  }
  .editor-toggle-grid {
    display: grid;
    gap: 10px;
    margin-top: 10px;
  }
  .editor-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 44px;
    padding: 10px 12px;
    border-radius: 14px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.84);
  }
  @media (max-width: 640px) {
    .hero,
    .editor-grid {
      grid-template-columns: 1fr;
    }
    .shell {
      padding: 14px;
    }
    .title {
      font-size: 1.65rem;
    }
    .score-value {
      font-size: 2.5rem;
    }
  }
`;

function resolveEntityId(hass, explicitValue, candidates) {
  if (explicitValue && hass.states[explicitValue]) {
    return explicitValue;
  }
  for (const candidate of candidates) {
    if (hass.states[candidate]) {
      return candidate;
    }
  }
  return explicitValue || candidates[0];
}

function mergeConfigWithDefaults(hass, config) {
  const merged = { ...DEFAULT_CONFIG, ...config };
  return {
    ...merged,
    entity: resolveEntityId(hass, merged.entity, ENTITY_CANDIDATES.entity),
    alerts_entity: resolveEntityId(hass, merged.alerts_entity, ENTITY_CANDIDATES.alerts_entity),
    stability_entity: resolveEntityId(hass, merged.stability_entity, ENTITY_CANDIDATES.stability_entity),
    military_entity: resolveEntityId(hass, merged.military_entity, ENTITY_CANDIDATES.military_entity)
  };
}

function getHomeCenter(hass) {
  const zoneHome = hass.states["zone.home"];
  const lat = zoneHome?.attributes?.latitude;
  const lon = zoneHome?.attributes?.longitude;
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    return [Number(lat), Number(lon)];
  }
  return DEFAULT_CENTER;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function toNumberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function resolveAlertCount(rawState, alertItems) {
  const attributeCount = Array.isArray(alertItems) ? alertItems.length : 0;
  const entityCount = toNumberOrNull(rawState);
  if (entityCount === null) {
    return attributeCount;
  }
  if (entityCount === 0 && attributeCount > 0) {
    return attributeCount;
  }
  return entityCount;
}

function buildMapPoints(markers, homeCenter) {
  const points = [];
  for (const marker of markers) {
    const lat = Number(marker.latitude);
    const lon = Number(marker.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      continue;
    }
    const top = clamp(((GERMANY_BOUNDS.north - lat) / (GERMANY_BOUNDS.north - GERMANY_BOUNDS.south)) * 100, 6, 94);
    const left = clamp(((lon - GERMANY_BOUNDS.west) / (GERMANY_BOUNDS.east - GERMANY_BOUNDS.west)) * 100, 6, 94);
    points.push({
      top,
      left,
      title: marker.title || "Warnung",
      source: marker.source || "",
      severity: marker.severity || "",
      variant: marker.source === "fallback" ? "secondary" : ""
    });
  }

  if (!points.length && Array.isArray(homeCenter) && homeCenter.length === 2) {
    const [lat, lon] = homeCenter;
    points.push({
      top: clamp(((GERMANY_BOUNDS.north - lat) / (GERMANY_BOUNDS.north - GERMANY_BOUNDS.south)) * 100, 6, 94),
      left: clamp(((lon - GERMANY_BOUNDS.west) / (GERMANY_BOUNDS.east - GERMANY_BOUNDS.west)) * 100, 6, 94),
      title: "Home-Position",
      source: "fallback",
      severity: "Keine geokodierten Warnungen",
      variant: "secondary"
    });
  }

  return points;
}

function renderCollapsiblePanel(panelKey, title, countLabel, content, open = false) {
  return `
    <div class="panel collapsible ${open ? "" : "collapsed"}" data-panel-key="${panelKey}">
      <button class="panel-toggle" type="button" data-panel-key="${panelKey}" aria-expanded="${open ? "true" : "false"}">
        <div class="panel-head toggle">
          <div class="panel-title">${title}</div>
          <div class="panel-note"><span class="count-pill">${countLabel}</span></div>
        </div>
      </button>
      ${open ? `<div class="panel-body tight">${content}</div>` : ""}
    </div>
  `;
}

class LageMonitorCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._panelState = {
      headlines: false,
      alerts: false,
      military: false
    };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
  }

  set hass(hass) {
    this._hass = hass;
    const config = mergeConfigWithDefaults(hass, this._config || DEFAULT_CONFIG);
    const stateObj = hass.states[config.entity];
    if (!stateObj) {
      this.shadowRoot.innerHTML = `<style>${CARD_STYLE}</style><ha-card><div class="shell"><div class="empty">Entity ${config.entity} not found.</div></div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes;
    const headlines = (attrs.headlines || []).slice(0, config.limit);
    const alertItems = attrs.alerts || [];
    const alerts = alertItems.slice(0, 10);
    const keywords = (attrs.top_keywords || []).slice(0, 6);
    const markers = attrs.map_markers || [];
    const militaryItems = (attrs.military_items || []).slice(0, 10);
    const stability = hass.states[config.stability_entity]?.state ?? "-";
    const military = hass.states[config.military_entity]?.state ?? "-";
    const activeAlerts = resolveAlertCount(hass.states[config.alerts_entity]?.state, alertItems);
    const homeCenter = getHomeCenter(hass);
    const mapPoints = buildMapPoints(markers, homeCenter);
    const mapMarkup = mapPoints.length ? mapPoints.map((point) => `
      <div
        class="map-marker ${point.variant}"
        style="top:${point.top}%;left:${point.left}%"
        title="${[point.title, point.source, point.severity].filter(Boolean).join(" | ")}"
      ></div>
    `).join("") : `<div class="map-empty">Noch keine geokodierten Warnungen verfuegbar.</div>`;

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLE}</style>
      <ha-card>
        <div class="shell">
          <div class="hero">
            <div class="hero-main">
              <div class="title">${config.title}</div>
              <div class="sub">Lageueberblick fuer Deutschland und relevante Ereignisse</div>
              <div class="score">
                <div class="score-value">${stateObj.state}</div>
                <div class="score-label">Deutschland Lage-Score</div>
              </div>
            </div>
            <div class="hero-side">
              <div class="metric">
                <div class="metric-label">Aktive Warnungen</div>
                <div class="metric-value">${activeAlerts}</div>
              </div>
              <div class="metric">
                <div class="metric-label">Stabilitaet</div>
                <div class="metric-value">${stability}</div>
              </div>
              <div class="metric">
                <div class="metric-label">Militaersignal</div>
                <div class="metric-value">${military}</div>
              </div>
            </div>
          </div>
          <div class="grid">
            ${config.show_map ? `
              <div class="panel">
                <div class="panel-head">
                  <div class="panel-title">Lagekarte</div>
                  <div class="panel-note">${mapPoints.length} Marker</div>
                </div>
                <div class="panel-body">
                  <div id="map" style="min-height:${Number(config.map_height) || 320}px">
                    <div class="map-frame" style="min-height:${Number(config.map_height) || 320}px">
                      <div class="map-shape"></div>
                      <div class="map-label">Deutschland Uebersicht</div>
                      ${mapMarkup}
                    </div>
                  </div>
                </div>
              </div>
            ` : ""}
            ${renderCollapsiblePanel(
              "headlines",
              "Top-Ereignisse",
              `${headlines.length} Eintraege`,
              `
                <div class="items">
                  ${headlines.length ? headlines.map((item) => `
                    <div class="item">
                      <div class="item-top">
                        <span class="badge">${item.score}</span>
                        <span class="source">${item.source}</span>
                      </div>
                      <a class="link" href="${item.link || "#"}" target="_blank" rel="noreferrer">${item.title}</a>
                      <div class="summary">${item.summary || ""}</div>
                    </div>
                  `).join("") : `<div class="empty">Noch keine Ereignisse verfuegbar</div>`}
                </div>
              `,
              this._panelState.headlines
            )}
            ${renderCollapsiblePanel(
              "alerts",
              "Amtliche Warnungen",
              `${activeAlerts}`,
              `
                <div class="items">
                  ${alerts.length ? alerts.map((item) => `
                    <div class="item">
                      <div class="item-top">
                        <span class="source">${item.source}</span>
                      </div>
                      <div class="link">${item.title || "Warnung ohne Titel"}</div>
                    </div>
                  `).join("") : `<div class="empty">Keine Warnungen vorhanden</div>`}
                </div>
              `,
              this._panelState.alerts
            )}
            ${config.show_military ? `
              ${renderCollapsiblePanel(
                "military",
                "Militaerische Aktivitaet",
                `${militaryItems.length}`,
                `
                  <div class="items">
                    ${militaryItems.length ? militaryItems.map((item) => `
                      <div class="item">
                        <div class="item-top">
                          <span class="source">${item.source}</span>
                        </div>
                        <div class="link">${item.title}</div>
                      </div>
                    `).join("") : `<div class="empty">Noch keine militaerischen Signalereignisse erkannt</div>`}
                  </div>
                `,
                this._panelState.military
              )}
            ` : ""}
            ${config.show_keywords ? `
              <div class="panel">
                <div class="panel-head">
                  <div class="panel-title">Schluesselbegriffe</div>
                </div>
                <div class="panel-body">
                  <div class="chips">
                    ${keywords.length ? keywords.map((item) => `<span class="chip">${item.keyword} (${item.count})</span>`).join("") : `<span class="empty">Noch keine Schlagwoerter</span>`}
                  </div>
                </div>
              </div>
            ` : ""}
          </div>
        </div>
      </ha-card>
    `;
    this._bindPanelToggles();
  }

  getCardSize() {
    return 8;
  }

  _bindPanelToggles() {
    this.shadowRoot.querySelectorAll(".panel-toggle").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const key = button.dataset.panelKey;
        this._panelState[key] = !this._panelState[key];
        this.hass = this._hass;
      });
    });
  }

  static getConfigElement() {
    return document.createElement("lage-monitor-card-editor");
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }
}

class LageMonitorCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
    this._render();
  }

  _render() {
    const config = this._config || DEFAULT_CONFIG;
    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLE}</style>
      <div class="editor">
        <div class="editor-section">
          <div class="editor-title">Allgemein</div>
          <div class="editor-grid single">
            ${this._field("title", "Titel", config.title)}
            ${this._field("limit", "Anzahl Ereignisse", config.limit, "number")}
          </div>
        </div>
        <div class="editor-section">
          <div class="editor-title">Karte</div>
          <div class="editor-grid single">
            ${this._field("zoom", "Karten-Zoom", config.zoom, "number")}
            ${this._field("map_height", "Kartenhoehe", config.map_height, "number")}
          </div>
          <div class="editor-toggle-grid">
            ${this._toggle("show_map", "Karte anzeigen", config.show_map)}
            ${this._toggle("show_keywords", "Schluesselbegriffe anzeigen", config.show_keywords)}
            ${this._toggle("show_military", "Militaerbereich anzeigen", config.show_military)}
          </div>
        </div>
        <div class="editor-section">
          <div class="editor-title">Entitaeten</div>
          <div class="editor-help">Normalerweise musst du hier nichts aendern. Die Karte erkennt deutsche und englische Standard-Entity-IDs automatisch.</div>
          <div class="editor-grid single">
            ${this._field("entity", "Score-Entity", config.entity || "")}
            ${this._field("alerts_entity", "Alerts-Entity", config.alerts_entity || "")}
            ${this._field("stability_entity", "Stabilitaets-Entity", config.stability_entity || "")}
            ${this._field("military_entity", "Militaer-Entity", config.military_entity || "")}
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", (event) => this._valueChanged(event));
    });
  }

  _field(key, label, value, type = "text") {
    return `
      <label class="editor-row">
        <span class="editor-label">${label}</span>
        <input data-key="${key}" type="${type}" value="${value ?? ""}">
      </label>
    `;
  }

  _toggle(key, label, checked) {
    return `
      <label class="editor-toggle">
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
      value = target.value || undefined;
    }

    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true
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
