const LEAFLET_JS = "/lage_monitor_frontend/vendor/leaflet.js";
const LEAFLET_CSS = "/lage_monitor_frontend/vendor/leaflet.css";
const DEFAULT_CENTER = [51.1657, 10.4515];
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
  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }
  ha-card {
    overflow: hidden;
    border-radius: 22px;
    position: relative;
    isolation: isolate;
    contain: paint;
  }
  .shell {
    padding: 18px;
    background:
      radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 38%),
      radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 30%),
      var(--ha-card-background, var(--card-background-color, #fff));
  }
  .hero {
    display: block;
    margin-bottom: 16px;
    min-width: 0;
  }
  .hero-topline {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .updated {
    color: var(--secondary-text-color);
    font-size: 0.74rem;
    white-space: nowrap;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    margin: 16px 0 14px;
    padding: 5px;
    border-radius: 15px;
    background: rgba(15, 23, 42, 0.07);
  }
  .scope-tab {
    min-width: 0;
    min-height: 44px;
    padding: 8px 10px;
    border: 0;
    border-radius: 11px;
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
  }
  .scope-tab.active {
    color: var(--primary-text-color);
    background: var(--ha-card-background, var(--card-background-color, #fff));
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
  }
  .focus-summary {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 14px 18px;
    align-items: center;
  }
  .focus-score {
    min-width: 92px;
    font-size: 2.35rem;
    line-height: 1;
    font-weight: 850;
    letter-spacing: -0.05em;
  }
  .focus-score small {
    display: block;
    margin-top: 5px;
    color: var(--secondary-text-color);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0;
  }
  .focus-score .score-denominator {
    font-size: 0.9rem;
    font-weight: 750;
    letter-spacing: 0;
  }
  .focus-copy {
    min-width: 0;
  }
  .focus-status {
    font-size: 0.76rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .focus-headline {
    margin-top: 5px;
    font-size: 1.05rem;
    font-weight: 750;
    line-height: 1.35;
  }
  .focus-driver {
    margin-top: 7px;
    color: var(--secondary-text-color);
    font-size: 0.84rem;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
  }
  .sparkline-wrap {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
  }
  .sparkline {
    display: block;
    width: 100%;
    height: 42px;
  }
  .sparkline polyline {
    fill: none;
    stroke: var(--primary-color, #2563eb);
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .trend-copy {
    color: var(--secondary-text-color);
    font-size: 0.75rem;
    line-height: 1.35;
    text-align: right;
  }
  .signal-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-top: 14px;
  }
  .signal-card {
    min-width: 0;
    padding: 10px 11px;
    border-radius: 13px;
    background: rgba(255, 255, 255, 0.68);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .signal-label {
    color: var(--secondary-text-color);
    font-size: 0.68rem;
    line-height: 1.2;
  }
  .signal-value {
    margin-top: 4px;
    font-size: 0.92rem;
    font-weight: 800;
    overflow-wrap: anywhere;
  }
  .change-list {
    display: grid;
    gap: 7px;
    margin: 14px 0 0;
    padding: 0;
    list-style: none;
  }
  .change-list li {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px;
    color: var(--secondary-text-color);
    font-size: 0.82rem;
    line-height: 1.4;
  }
  .change-list li::before {
    content: "→";
    color: var(--primary-color, #2563eb);
    font-weight: 800;
  }
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 9px;
  }
  .theme-card {
    appearance: none;
    width: 100%;
    min-width: 0;
    padding: 11px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.18);
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
  }
  .theme-card:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--primary-color, #2563eb) 45%, transparent);
  }
  .theme-card:focus-visible {
    outline: 2px solid var(--primary-color, #2563eb);
    outline-offset: 2px;
  }
  .theme-card.active {
    border-color: var(--primary-color, #2563eb);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color, #2563eb) 18%, transparent);
    transform: translateY(-1px);
  }
  .theme-card:disabled {
    cursor: default;
    opacity: 0.58;
  }
  .theme-name {
    color: var(--secondary-text-color);
    font-size: 0.72rem;
  }
  .theme-risk {
    margin-top: 5px;
    font-size: 1.15rem;
    font-weight: 800;
  }
  .risk-track {
    height: 4px;
    margin-top: 8px;
    overflow: hidden;
    border-radius: 99px;
    background: rgba(148, 163, 184, 0.2);
  }
  .risk-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #22c55e, #f59e0b 55%, #dc2626);
  }
  .trend-pending {
    margin-top: 12px;
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    line-height: 1.35;
  }
  .event-actions {
    display: flex;
    justify-content: center;
    margin-top: 12px;
  }
  .event-more {
    appearance: none;
    padding: 8px 14px;
    border: 1px solid rgba(37, 99, 235, 0.28);
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.07);
    color: var(--primary-color, #2563eb);
    font: inherit;
    font-size: 0.8rem;
    font-weight: 750;
    cursor: pointer;
  }
  .secondary-events {
    margin-top: 14px;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
    padding-top: 10px;
  }
  .secondary-events summary {
    color: var(--secondary-text-color);
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 700;
  }
  .quality-summary {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 10px 14px;
    align-items: center;
    margin-bottom: 12px;
    padding: 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.95);
  }
  .quality-score {
    font-size: 1.55rem;
    font-weight: 850;
  }
  .quality-copy {
    color: var(--secondary-text-color);
    font-size: 0.82rem;
    line-height: 1.4;
  }
  .event-time {
    color: var(--secondary-text-color);
    font-size: 0.76rem;
  }
  .summary.clamped {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .hero-main {
    padding: 18px;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.06);
    border: 1px solid rgba(148, 163, 184, 0.2);
    min-width: 0;
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
  .status-line {
    margin-top: 12px;
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    line-height: 1.4;
  }
  .hero-assessment {
    display: grid;
    gap: 6px;
    margin-top: 14px;
  }
  .hero-assessment-meta {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    line-height: 1.4;
  }
  .score {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .score-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 8px;
  }
  .metric-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-top: 12px;
  }
  .score-card {
    padding: 14px 16px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.18);
    min-width: 0;
  }
  .score-card-label {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .score-card-value {
    font-size: 2rem;
    line-height: 1;
    font-weight: 800;
  }
  .score-value {
    font-size: 3rem;
    line-height: 1;
    font-weight: 800;
  }
  .score-value.state-good,
  .metric-value.state-good,
  .focus-score.state-good,
  .focus-status.state-good {
    color: #15803d;
  }
  .score-value.state-medium,
  .metric-value.state-medium,
  .focus-score.state-medium,
  .focus-status.state-medium {
    color: #b45309;
  }
  .score-value.state-bad,
  .metric-value.state-bad,
  .focus-score.state-bad,
  .focus-status.state-bad {
    color: #b91c1c;
  }
  .score-label {
    color: var(--secondary-text-color);
    font-size: 0.9rem;
  }
  .metric {
    padding: 14px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.18);
    backdrop-filter: blur(6px);
    min-width: 0;
  }
  .metric-label {
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1.2;
  }
  .metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .grid {
    display: grid;
    gap: 16px;
    min-width: 0;
  }
  .panel {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.72);
    overflow: hidden;
    min-width: 0;
  }
  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 14px 16px 10px;
    min-width: 0;
  }
  .panel-title {
    font-size: 1rem;
    font-weight: 700;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .panel-note {
    color: var(--secondary-text-color);
    font-size: 0.76rem;
  }
  .panel-body {
    padding: 0 16px 16px;
    min-width: 0;
  }
  .panel-body.tight {
    padding-top: 6px;
  }
  .items {
    display: grid;
    gap: 12px;
    min-width: 0;
  }
  .split-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
    min-width: 0;
  }
  .split-section-title {
    font-size: 0.9rem;
    font-weight: 700;
    margin-bottom: 10px;
  }
  .item {
    padding-top: 12px;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
    min-width: 0;
  }
  .item:first-child {
    border-top: 0;
    padding-top: 0;
  }
  .item-top {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
    min-width: 0;
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
    overflow-wrap: anywhere;
  }
  .link {
    color: var(--primary-text-color);
    text-decoration: none;
    font-weight: 600;
    line-height: 1.4;
    display: block;
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .summary {
    color: var(--secondary-text-color);
    font-size: 0.92rem;
    line-height: 1.45;
    margin-top: 6px;
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .item-meta {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    line-height: 1.4;
    margin-top: 6px;
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .alert-summary {
    white-space: pre-line;
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
    height: var(--lage-monitor-map-height, 320px);
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.2);
    background: rgba(226, 232, 240, 0.65);
    position: relative;
    isolation: isolate;
    contain: paint;
    z-index: 0;
  }
  .map-status {
    margin-top: 10px;
    color: var(--secondary-text-color);
    font-size: 0.82rem;
    line-height: 1.4;
  }
  .map-selection {
    margin-top: 12px;
    padding: 12px 14px;
    border-radius: 14px;
    background: rgba(239, 246, 255, 0.82);
    border: 1px solid rgba(37, 99, 235, 0.16);
  }
  .map-selection-title {
    font-size: 0.9rem;
    font-weight: 700;
    margin-bottom: 4px;
  }
  .map-selection-items {
    display: grid;
    gap: 8px;
    margin-top: 10px;
  }
  .map-selection-item {
    padding-top: 8px;
    border-top: 1px solid rgba(148, 163, 184, 0.2);
    font-size: 0.86rem;
    line-height: 1.35;
  }
  .map-selection-item a {
    color: var(--primary-color, #1d4ed8);
    font-weight: 600;
    text-decoration: none;
  }
  .map-selection-item a:hover {
    text-decoration: underline;
  }
  .map-selection-meta {
    color: var(--secondary-text-color);
    font-size: 0.76rem;
    margin-top: 3px;
  }
  .analysis-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.9fr);
    gap: 16px;
  }
  .analysis-copy {
    display: grid;
    gap: 10px;
  }
  .analysis-lead {
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.45;
  }
  .analysis-text {
    color: #475569;
    font-size: 0.88rem;
    line-height: 1.48;
  }
  .analysis-side {
    display: grid;
    gap: 10px;
    align-content: start;
  }
  .assessment-stack {
    display: grid;
    gap: 12px;
  }
  .assessment-panel {
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 16px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.9));
    overflow: hidden;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  }
  .assessment-panel.collapsed .assessment-body {
    display: none;
  }
  .assessment-head {
    display: grid;
    gap: 10px;
    padding: 16px 16px 14px;
  }
  .assessment-head-main {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  .assessment-title-wrap {
    min-width: 0;
    display: grid;
    gap: 4px;
  }
  .assessment-title {
    font-size: 1.08rem;
    font-weight: 800;
  }
  .assessment-score {
    color: var(--secondary-text-color);
    font-size: 0.84rem;
    line-height: 1.3;
  }
  .assessment-meta {
    color: #64748b;
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .assessment-headline {
    color: var(--primary-text-color);
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.4;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .assessment-body {
    padding: 0 16px 16px;
    display: grid;
    gap: 8px;
  }
  .assessment-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 7px 11px;
    border-radius: 999px;
    border: 1px solid transparent;
    font-size: 0.76rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .assessment-pill.state-good {
    color: #166534;
    background: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.18);
  }
  .assessment-pill.state-medium {
    color: #9a3412;
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.18);
  }
  .assessment-pill.state-bad {
    color: #b91c1c;
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.18);
  }
  .assessment-drivers {
    display: grid;
    gap: 10px;
  }
  .trend-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    background: rgba(15, 23, 42, 0.08);
  }
  .trend-pill.up {
    color: #15803d;
    background: rgba(34, 197, 94, 0.14);
  }
  .trend-pill.down {
    color: #b91c1c;
    background: rgba(239, 68, 68, 0.14);
  }
  .trend-pill.stable {
    color: #475569;
    background: rgba(148, 163, 184, 0.14);
  }
  .driver-list {
    display: grid;
    gap: 10px;
  }
  .driver-item {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 10px;
    align-items: start;
    padding: 10px 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .driver-value {
    min-width: 2rem;
    color: #b91c1c;
    font-size: 1rem;
    font-weight: 800;
  }
  .driver-body {
    min-width: 0;
  }
  .driver-title {
    font-size: 0.88rem;
    font-weight: 700;
    line-height: 1.35;
  }
  .driver-detail {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    line-height: 1.35;
    margin-top: 2px;
  }
  .component-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
  }
  .component-card {
    padding: 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .component-label {
    color: var(--secondary-text-color);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .component-value {
    margin-top: 6px;
    font-size: 1.35rem;
    font-weight: 800;
    line-height: 1;
  }
  .component-note {
    margin-top: 6px;
    color: var(--secondary-text-color);
    font-size: 0.78rem;
    line-height: 1.35;
  }
  .method-note {
    color: var(--secondary-text-color);
    font-size: 0.82rem;
    line-height: 1.45;
  }
  .mini-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
  }
  .mini-card {
    padding: 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .mini-card-title {
    font-size: 0.84rem;
    font-weight: 700;
  }
  .mini-card-value {
    margin-top: 6px;
    font-size: 1.1rem;
    font-weight: 800;
  }
  .mini-card-meta {
    margin-top: 6px;
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    line-height: 1.35;
  }
  .freshness-list {
    display: grid;
    gap: 10px;
  }
  .freshness-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px 10px;
    align-items: start;
    padding: 10px 12px;
    border-radius: 14px;
    background: rgba(248, 250, 252, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .freshness-title {
    font-size: 0.86rem;
    font-weight: 700;
    line-height: 1.35;
  }
  .freshness-meta {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    line-height: 1.35;
    margin-top: 2px;
  }
  .freshness-badge {
    padding: 6px 9px;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 700;
    white-space: nowrap;
    background: rgba(148, 163, 184, 0.14);
    color: #475569;
  }
  .freshness-badge.fresh {
    color: #15803d;
    background: rgba(34, 197, 94, 0.14);
  }
  .freshness-badge.delayed {
    color: #b45309;
    background: rgba(245, 158, 11, 0.16);
  }
  .freshness-badge.old,
  .freshness-badge.error {
    color: #b91c1c;
    background: rgba(239, 68, 68, 0.14);
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
  .leaflet-container {
    overflow: hidden;
    outline: 0;
    font: inherit;
    background: rgba(226, 232, 240, 0.65);
  }
  .leaflet-pane,
  .leaflet-tile,
  .leaflet-marker-icon,
  .leaflet-marker-shadow,
  .leaflet-tile-container,
  .leaflet-pane > svg,
  .leaflet-pane > canvas,
  .leaflet-zoom-box,
  .leaflet-image-layer,
  .leaflet-layer {
    position: absolute;
    left: 0;
    top: 0;
  }
  .leaflet-pane {
    z-index: 400;
  }
  .leaflet-tile-pane {
    z-index: 200;
  }
  .leaflet-overlay-pane {
    z-index: 400;
  }
  .leaflet-shadow-pane {
    z-index: 500;
  }
  .leaflet-marker-pane {
    z-index: 600;
  }
  .leaflet-tooltip-pane {
    z-index: 650;
  }
  .leaflet-popup-pane {
    z-index: 700;
  }
  .leaflet-map-pane,
  .leaflet-tile-container {
    width: 100%;
    height: 100%;
  }
  .leaflet-container img,
  .leaflet-container .leaflet-tile {
    max-width: none !important;
    max-height: none !important;
  }
  .leaflet-tile {
    visibility: hidden;
    display: block;
  }
  .leaflet-tile-loaded {
    visibility: inherit;
  }
  .leaflet-zoom-animated {
    transform-origin: 0 0;
  }
  .leaflet-control {
    position: relative;
    z-index: 800;
    pointer-events: auto;
  }
  .leaflet-top,
  .leaflet-bottom {
    position: absolute;
    z-index: 1000;
    pointer-events: none;
  }
  .leaflet-top {
    top: 0;
  }
  .leaflet-right {
    right: 0;
  }
  .leaflet-bottom {
    bottom: 0;
  }
  .leaflet-left {
    left: 0;
  }
  .leaflet-control {
    float: left;
    clear: both;
  }
  .leaflet-right .leaflet-control {
    float: right;
  }
  .leaflet-top .leaflet-control {
    margin-top: 10px;
  }
  .leaflet-bottom .leaflet-control {
    margin-bottom: 10px;
  }
  .leaflet-left .leaflet-control {
    margin-left: 10px;
  }
  .leaflet-right .leaflet-control {
    margin-right: 10px;
  }
  .leaflet-popup-content-wrapper,
  .leaflet-popup-tip {
    background: rgba(15, 23, 42, 0.92);
    color: #fff;
  }
  .leaflet-popup-content {
    margin: 10px 12px;
    line-height: 1.4;
    font-size: 0.84rem;
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
    .editor-grid,
    .split-grid,
    .analysis-grid {
      grid-template-columns: 1fr;
    }
    .shell {
      padding: 12px;
    }
    .hero-main,
    .metric {
      padding: 14px;
    }
    .panel-head {
      padding: 12px 12px 8px;
    }
    .panel-body {
      padding: 0 12px 12px;
    }
    .title {
      font-size: 1.5rem;
      line-height: 1.1;
    }
    .sub {
      font-size: 0.84rem;
      margin-bottom: 12px;
    }
    .score-value {
      font-size: 2.2rem;
    }
    .score-grid,
    .metric-grid,
    .theme-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .score-card,
    .metric {
      padding: 12px;
    }
    .score-card-label,
    .metric-label {
      font-size: 0.7rem;
      letter-spacing: 0.05em;
    }
    .score-card-value {
      font-size: 1.55rem;
    }
    .score {
      flex-direction: column;
      align-items: flex-start;
      gap: 6px;
    }
    .metric-value {
      font-size: 1.05rem;
    }
    .link {
      font-size: 0.98rem;
      line-height: 1.35;
    }
    .summary,
    .item-meta {
      font-size: 0.88rem;
      line-height: 1.4;
    }
    .analysis-lead {
      font-size: 0.96rem;
    }
  }
  @media (max-width: 420px) {
    .shell {
      padding: 10px;
    }
    .hero-main,
    .map-selection,
    .editor-section {
      padding: 12px;
    }
    .score-grid,
    .metric-grid {
      gap: 8px;
    }
    .focus-summary {
      grid-template-columns: 78px minmax(0, 1fr);
      gap: 12px;
    }
    .focus-score {
      min-width: 0;
      font-size: 1.95rem;
    }
    .signal-strip {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
    }
    .signal-card {
      padding: 8px 7px;
    }
    .signal-label {
      font-size: 0.6rem;
    }
    .signal-value {
      font-size: 0.76rem;
      line-height: 1.2;
    }
    .panel {
      border-radius: 16px;
    }
    .panel-head {
      gap: 8px;
    }
    .panel-title {
      font-size: 0.95rem;
    }
    .count-pill,
    .badge {
      min-width: 1.7rem;
      padding: 2px 6px;
    }
    .score-card,
    .metric {
      padding: 10px;
    }
    .score-card-value {
      font-size: 1.35rem;
    }
    .metric-value {
      font-size: 0.95rem;
    }
  }
`;

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

    const existingScript = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(window.L), { once: true });
      existingScript.addEventListener("error", reject, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve(window.L);
    script.onerror = reject;
    document.head.appendChild(script);
  }).catch((error) => {
    leafletLoader = null;
    throw error;
  });

  return leafletLoader;
}

function resolveEntityId(hass, explicitValue, candidates) {
  if (explicitValue && hass.states[explicitValue]) {
    return explicitValue;
  }
  for (const candidate of candidates) {
    if (hass.states[candidate]) {
      return candidate;
    }
  }
  const fuzzyMatch = findMatchingEntityId(hass, [explicitValue, ...candidates].filter(Boolean));
  if (fuzzyMatch) {
    return fuzzyMatch;
  }
  return explicitValue || candidates[0];
}

function normalizeEntityToken(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

function getEntitySearchTokens(values) {
  const tokens = new Set();
  for (const value of values) {
    const raw = String(value || "");
    if (!raw) {
      continue;
    }
    tokens.add(normalizeEntityToken(raw));
    const entityIdPart = raw.includes(".") ? raw.split(".").pop() : raw;
    tokens.add(normalizeEntityToken(entityIdPart));
  }
  return [...tokens].filter(Boolean);
}

function findMatchingEntityId(hass, values) {
  const wantedTokens = getEntitySearchTokens(values);
  if (!wantedTokens.length) {
    return null;
  }

  for (const [entityId, stateObj] of Object.entries(hass.states)) {
    const entityIdToken = normalizeEntityToken(entityId);
    const objectIdToken = normalizeEntityToken(entityId.split(".").pop());
    const friendlyNameToken = normalizeEntityToken(stateObj?.attributes?.friendly_name);
    if (wantedTokens.some((token) => token && (
      entityIdToken === token ||
      objectIdToken === token ||
      friendlyNameToken === token
    ))) {
      return entityId;
    }
  }

  return null;
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

function toNumberOrNull(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
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

function getScoreState(value, positiveHigh = false) {
  const numeric = toNumberOrNull(value);
  if (numeric === null) {
    return { className: "", label: "" };
  }
  if (positiveHigh) {
    if (numeric >= 70) {
      return { className: "state-good", label: "Gruen: hoch ist gut" };
    }
    if (numeric >= 40) {
      return { className: "state-medium", label: "Gelb: mittel" };
    }
    return { className: "state-bad", label: "Rot: niedrig ist kritisch" };
  }
  if (numeric <= 35) {
    return { className: "state-good", label: "Gruen: niedrig ist ruhig" };
  }
  if (numeric <= 70) {
    return { className: "state-medium", label: "Gelb: erhöht" };
  }
  return { className: "state-bad", label: "Rot: hoch ist kritisch" };
}

function getAssessmentStatus(score) {
  const numeric = toNumberOrNull(score);
  if (numeric === null) {
    return { className: "", label: "Keine Einordnung" };
  }
  if (numeric >= 70) {
    return { className: "state-good", label: "Ruhig" };
  }
  if (numeric >= 40) {
    return { className: "state-medium", label: "Aufmerksam" };
  }
  return { className: "state-bad", label: "Belastet" };
}

function getSummaryStatus(summary, score) {
  const key = String(summary?.status?.key || "");
  const label = String(summary?.status?.label || "");
  const classNames = { good: "state-good", medium: "state-medium", bad: "state-bad" };
  if (classNames[key] && label) {
    return { className: classNames[key], label };
  }
  return getAssessmentStatus(score);
}

function getAggregateScore(values) {
  const numericValues = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
  if (!numericValues.length) {
    return null;
  }
  return Math.round(numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length);
}

function getMetricDeltaLabel(metric) {
  if (!metric || typeof metric !== "object") {
    return "Trend 24h: Keine Daten | 7d: Keine Daten";
  }
  const label24h = String(metric.label_24h || "Keine Daten");
  const label7d = String(metric.label_7d || "Keine Daten");
  return `Trend 24h: ${label24h} | 7d: ${label7d}`;
}

function renderHeroAssessment(score, trendLabel) {
  const state = getAssessmentStatus(score);
  return `
    <div class="hero-assessment">
      <span class="assessment-pill ${state.className}">${state.label}: ${formatOutOfHundred(score)}</span>
      <div class="hero-assessment-meta">${escapeHtml(trendLabel || "Trend: Keine Daten")}</div>
    </div>
  `;
}

function formatOutOfHundred(value) {
  const numeric = toNumberOrNull(value);
  if (numeric === null) {
    return escapeHtml(value ?? "-");
  }
  return `${numeric}/100`;
}

function formatLastUpdate(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "Unbekannt";
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "short",
    timeStyle: "medium"
  }).format(date);
}

function renderMetric(title, value, options = {}) {
  const { positiveHigh = false, showOutOfHundred = false } = options;
  const state = getScoreState(value, positiveHigh);
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(title)}</div>
      <div class="metric-value ${state.className}">${showOutOfHundred ? formatOutOfHundred(value) : escapeHtml(value)}</div>
    </div>
  `;
}

function formatDelta(value) {
  const numeric = toNumberOrNull(value);
  if (numeric === null) {
    return "Keine Daten";
  }
  if (numeric > 0) {
    return `+${numeric}`;
  }
  return `${numeric}`;
}

function renderTrendMiniCard(title, metric) {
  return `
    <div class="mini-card">
      <div class="mini-card-title">${escapeHtml(title)}</div>
      <div class="mini-card-value">${formatOutOfHundred(metric?.current ?? "-")}</div>
      <div class="mini-card-meta">24h: ${escapeHtml(metric?.label_24h || formatDelta(metric?.delta_24h))}</div>
      <div class="mini-card-meta">7d: ${escapeHtml(metric?.label_7d || formatDelta(metric?.delta_7d))}</div>
    </div>
  `;
}

function getFreshnessClass(label) {
  const normalized = String(label || "").toLowerCase();
  if (normalized === "frisch") {
    return "fresh";
  }
  if (normalized === "verzoegert" || normalized === "verzögert") {
    return "delayed";
  }
  if (normalized === "alt") {
    return "old";
  }
  if (normalized === "fehler") {
    return "error";
  }
  return "";
}

function renderFreshnessItem(item) {
  const age = Number.isFinite(Number(item?.age_minutes)) ? `${Number(item.age_minutes)} min` : "ohne Zeit";
  const items = Number(item?.items || 0);
  const error = String(item?.error || "").trim();
  return `
    <div class="freshness-item">
      <div>
        <div class="freshness-title">${escapeHtml(item?.source || "Quelle")}</div>
        <div class="freshness-meta">${items} Treffer, letzte Aktivitaet: ${escapeHtml(age)}</div>
        ${error ? `<div class="freshness-meta">${escapeHtml(error)}</div>` : ""}
      </div>
      <div class="freshness-badge ${getFreshnessClass(item?.label)}">${escapeHtml(item?.label || "Unbekannt")}</div>
    </div>
  `;
}

function getTrendState(trend) {
  const direction = String(trend?.direction || "stable");
  if (direction === "up") {
    return { className: "up", label: "Verbessert" };
  }
  if (direction === "down") {
    return { className: "down", label: "Verschlechtert" };
  }
  return { className: "stable", label: "Stabil" };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeHttpLink(value) {
  const link = String(value ?? "").trim();
  return /^https?:\/\//i.test(link) ? link : "";
}

function buildMapPoints(markers, homeCenter) {
  const points = [];
  for (const marker of markers) {
    const lat = Number(marker.latitude);
    const lon = Number(marker.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      continue;
    }
    points.push({
      key: marker.key || `${marker.kind || "cluster"}:${lat}:${lon}`,
      latitude: lat,
      longitude: lon,
      title: marker.title || "Meldung",
      source: marker.source || "",
      severity: marker.severity || "",
      count: Number(marker.count) || 1,
      kind: marker.kind || "cluster",
      titles: Array.isArray(marker.titles) ? marker.titles : [],
      items: Array.isArray(marker.items) ? marker.items : [],
      themes: Array.isArray(marker.themes) ? marker.themes : [],
      region: marker.region || "de",
      local: Boolean(marker.local),
      variant: marker.kind === "home" ? "secondary" : ""
    });
  }

  if (!points.some((point) => point.kind === "home") && Array.isArray(homeCenter) && homeCenter.length === 2) {
    const [lat, lon] = homeCenter;
    points.push({
      key: `home:${lat}:${lon}`,
      latitude: lat,
      longitude: lon,
      title: "Home-Position",
      source: "fallback",
      severity: "Keine geokodierten Warnungen",
      count: 1,
      kind: "home",
      titles: [],
      items: [],
      themes: [],
      region: "local",
      local: true,
      variant: "secondary"
    });
  }

  return points;
}

function getRealMarkerCount(points) {
  return points.filter((point) => point.kind !== "home").length;
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

function getRegionSummary(summary, key) {
  const region = summary?.[key];
  return region && typeof region === "object" ? region : {};
}

function renderScoreCard(label, value, options = {}) {
  const { positiveHigh = true } = options;
  const state = getScoreState(value, positiveHigh);
  return `
    <div class="score-card">
      <div class="score-card-label">${escapeHtml(label)}</div>
      <div class="score-card-value ${state.className}">${formatOutOfHundred(value)}</div>
    </div>
  `;
}

function renderAssessmentPanel(panelKey, regionLabel, score, summary, metaLabel, open = false) {
  const state = getSummaryStatus(summary, score);
  const headline = escapeHtml(summary?.headline || "Keine aktuelle Lagebewertung verfügbar.");
  const drivers = escapeHtml(summary?.drivers || "");
  const outlook = escapeHtml(summary?.outlook || "");
  const meta = escapeHtml(metaLabel || "KI-Einschaetzung");
  return `
    <div class="assessment-panel collapsible ${open ? "" : "collapsed"}" data-panel-key="${panelKey}">
      <button class="panel-toggle" type="button" data-panel-key="${panelKey}" aria-expanded="${open ? "true" : "false"}">
        <div class="assessment-head">
          <div class="assessment-head-main">
            <div class="assessment-title-wrap">
              <div class="assessment-title">${escapeHtml(regionLabel)}</div>
              <div class="assessment-score">${formatOutOfHundred(score)}</div>
              <div class="assessment-meta">${meta}</div>
            </div>
            <span class="assessment-pill ${state.className}">${state.label}</span>
          </div>
          <div class="assessment-headline">${headline}</div>
        </div>
      </button>
      <div class="assessment-body">
        ${drivers ? `<div class="analysis-text">${drivers}</div>` : ""}
        ${outlook ? `<div class="analysis-text">${outlook}</div>` : ""}
      </div>
    </div>
  `;
}

const SOURCE_LABELS = {
  tagesschau_all: "Tagesschau",
  tagesschau_inland: "Tagesschau Inland",
  tagesschau_ausland: "Tagesschau Ausland",
  ntv_top: "n-tv",
  stern_politik: "Stern Politik",
  welt_politik: "WELT Politik",
  presseportal_blaulicht: "Presseportal Blaulicht",
  presseportal_storys: "Presseportal",
  mowas: "MoWaS",
  biwapp: "BIWAPP",
  katwarn: "KATWARN",
  dwd: "DWD",
  lhp: "Länderwarnsystem",
  police: "Polizei",
  usgs: "USGS",
  eonet: "NASA EONET"
};

function formatSource(source) {
  const raw = String(source || "Quelle");
  if (SOURCE_LABELS[raw]) {
    return SOURCE_LABELS[raw];
  }
  const custom = raw.match(/^custom_press_(\d+)$/);
  if (custom) {
    return `Eigene Pressequelle ${custom[1]}`;
  }
  return raw.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPublished(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function renderSparkline(values) {
  const series = Array.isArray(values)
    ? values.map(Number).filter((value) => Number.isFinite(value)).slice(-28)
    : [];
  if (series.length < 2) {
    return `<div class="empty">Trendlinie erscheint nach weiteren Messpunkten.</div>`;
  }
  const width = 240;
  const height = 42;
  const points = series.map((value, index) => {
    const x = (index / Math.max(1, series.length - 1)) * width;
    const y = height - (Math.min(100, Math.max(0, value)) / 100) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Verlauf der letzten sieben Tage"><polyline points="${points}"></polyline></svg>`;
}

function renderEventItem(item) {
  const score = Number(item?.score);
  const link = safeHttpLink(item?.link);
  const title = escapeHtml(item?.title || "Meldung ohne Titel");
  const published = formatPublished(item?.published);
  const titleMarkup = link
    ? `<a class="link" href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${title}</a>`
    : `<div class="link">${title}</div>`;
  return `
    <div class="item">
      <div class="item-top">
        ${Number.isFinite(score) ? `<span class="badge">${score}</span>` : ""}
        <span class="source">${escapeHtml(formatSource(item?.source))}</span>
        ${published ? `<span class="event-time">${escapeHtml(published)}</span>` : ""}
      </div>
      ${titleMarkup}
      ${item?.summary ? `<div class="summary clamped">${escapeHtml(item.summary)}</div>` : ""}
    </div>
  `;
}

const THEME_FILTER_KEYWORDS = {
  security: ["anschlag", "terror", "angriff", "gewalt", "amok", "geisel", "schüsse", "schuesse", "messer", "explosion", "unruhen"],
  infrastructure: ["ausfall", "blackout", "strom", "energie", "wasser", "trinkwasser", "bahn", "brücke", "bruecke", "verkehr", "netz", "internet", "versorgung"],
  nature: ["erdbeben", "hochwasser", "überschwemm", "ueberschwemm", "sturm", "orkan", "waldbrand", "wildfire", "hitze", "glatteis", "schnee", "vulkan"],
  military: ["militär", "militaer", "bundeswehr", "nato", "drohne", "rakete", "soldaten", "truppen", "luftwaffe", "marine"]
};

function itemMatchesTheme(item, theme) {
  if (!theme) {
    return true;
  }
  if (Array.isArray(item?.themes) && item.themes.includes(theme)) {
    return true;
  }
  const haystack = `${item?.title || ""} ${item?.summary || ""} ${(item?.keywords || []).join(" ")} ${(item?.military_keywords || []).join(" ")}`.toLowerCase();
  return (THEME_FILTER_KEYWORDS[theme] || []).some((keyword) => haystack.includes(keyword));
}

function renderThemeGrid(themes, activeTheme = "") {
  const labels = {
    security: "Sicherheit",
    infrastructure: "Infrastruktur",
    nature: "Natur",
    military: "Militär"
  };
  return `<div class="theme-grid">${Object.entries(labels).map(([key, label]) => {
    const risk = Math.min(100, Math.max(0, Number(themes?.[key]?.risk) || 0));
    const events = Number(themes?.[key]?.events) || 0;
    return `
      <button class="theme-card ${activeTheme === key ? "active" : ""}" type="button" data-theme="${key}" aria-pressed="${activeTheme === key ? "true" : "false"}" ${events ? "" : "disabled"}>
        <div class="theme-name">${label}</div>
        <div class="theme-risk">${risk}<small>/100</small></div>
        <div class="risk-track"><div class="risk-fill" style="width:${risk}%"></div></div>
        <div class="event-time">${events} Signal${events === 1 ? "" : "e"}</div>
      </button>
    `;
  }).join("")}</div>`;
}

function filterMapPoints(points, focus, theme = "") {
  const themeFiltered = theme
    ? points.filter((point) => point.kind === "home" || itemMatchesTheme(point, theme) || point.items.some((item) => itemMatchesTheme(item, theme)))
    : points;
  if (focus === "world") {
    return themeFiltered.filter((point) => point.kind !== "home" && point.region === "world");
  }
  if (focus === "local") {
    return themeFiltered.filter((point) => point.kind === "home" || point.local);
  }
  return themeFiltered.filter((point) => point.kind === "home" || point.region !== "world");
}

class LageMonitorCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._panelState = {
      focus: "local",
      map: false,
      alerts: false,
      military: false,
      data: false,
      eventsExpanded: false,
      theme: ""
    };
    this._lastMarkup = "";
    this._lastMapSignature = "";
    this._map = null;
    this._mapLayer = null;
    this._mapMarkersLayer = null;
    this._mapResizeObserver = null;
    this._mapHost = null;
    this._mapRenderToken = 0;
    this._selectedMapPointKey = "";
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
  }

  connectedCallback() {
    this._mapRenderToken += 1;
  }

  disconnectedCallback() {
    this._mapRenderToken += 1;
    this._teardownMap();
  }

  set hass(hass) {
    this._hass = hass;
    this._restorePanelState();
    const config = mergeConfigWithDefaults(hass, this._config || DEFAULT_CONFIG);
    const stateObj = hass.states[config.entity];
    if (!stateObj) {
      this._teardownMap();
      this.shadowRoot.innerHTML = `<style>${CARD_STYLE}</style><ha-card><div class="shell"><div class="empty">Entity ${escapeHtml(config.entity)} wurde nicht gefunden.</div></div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes;
    const localHeadlines = (attrs.local_headlines || []).slice(0, config.limit);
    const germanyHeadlines = (attrs.germany_headlines || []).slice(0, config.limit);
    const worldHeadlines = (attrs.world_headlines || []).slice(0, config.limit);
    const alertItems = attrs.alerts || [];
    const localAlertItems = attrs.local_alerts || [];
    const keywords = (attrs.top_keywords || []).slice(0, 6);
    const markers = attrs.map_markers || [];
    const analysisSummary = attrs.analysis_summary || {};
    const historySummary = attrs.history_summary || {};
    const sourceFreshness = (attrs.source_freshness || []).slice(0, 8);
    const dataQuality = attrs.data_quality || {};
    const themeScores = attrs.theme_scores || {};
    const scopeCounts = attrs.scope_counts || {};
    const germanyScore = toNumberOrNull(stateObj.state);
    const globalScore = attrs.global_score ?? "-";
    const localScore = attrs.local_score ?? "-";
    const localRadiusKm = attrs.diagnostics?.alert_radius_km;
    const lastUpdate = formatLastUpdate(attrs.last_update);
    const activeAlerts = resolveAlertCount(hass.states[config.alerts_entity]?.state, alertItems);
    const homeCenter = getHomeCenter(hass);
    const allMapPoints = buildMapPoints(markers, homeCenter);
    const focus = ["local", "germany", "world"].includes(this._panelState.focus)
      ? this._panelState.focus
      : "local";
    const localLabel = Number.isFinite(Number(localRadiusKm)) ? `Umkreis ${localRadiusKm} km` : "Umkreis";
    const focusConfig = {
      local: {
        label: localLabel,
        score: localScore,
        summary: getRegionSummary(analysisSummary, "local"),
        history: historySummary.local || {},
        headlines: localHeadlines,
        themes: themeScores.local || {},
        military: (attrs.military_items_local || []).slice(0, 10),
        alerts: localAlertItems.slice(0, 10),
        alertCount: Number(scopeCounts.local?.alerts ?? localAlertItems.length) || 0
      },
      germany: {
        label: "Deutschland",
        score: germanyScore,
        summary: getRegionSummary(analysisSummary, "germany"),
        history: historySummary.germany || {},
        headlines: germanyHeadlines,
        themes: themeScores.germany || {},
        military: (attrs.military_items_germany || []).slice(0, 10),
        alerts: alertItems.slice(0, 10),
        alertCount: Number(scopeCounts.germany?.alerts ?? activeAlerts) || 0
      },
      world: {
        label: "Welt",
        score: globalScore,
        summary: getRegionSummary(analysisSummary, "world"),
        history: historySummary.world || {},
        headlines: worldHeadlines,
        themes: themeScores.world || {},
        military: (attrs.military_items_world || []).slice(0, 10),
        alerts: [],
        alertCount: Number(scopeCounts.world?.alerts) || 0
      }
    };
    const current = focusConfig[focus];
    const scoreState = getSummaryStatus(current.summary, current.score);
    const changes = Array.isArray(current.summary?.changes) ? current.summary.changes : [];
    const meaningfulChanges = changes.filter((item) => !String(item).toLowerCase().includes("noch keine"));
    const scopeSources = Number(dataQuality.scope_sources?.[focus]) || 0;
    const delta24h = current.history?.label_24h || formatDelta(current.history?.delta_24h);
    const activeTheme = current.themes?.[this._panelState.theme]?.events
      ? this._panelState.theme
      : "";
    const filteredHeadlines = current.headlines.filter((item) => itemMatchesTheme(item, activeTheme));
    const relevantEvents = filteredHeadlines.filter((item) => Number(item?.score) >= 8);
    const secondaryEvents = filteredHeadlines.filter((item) => {
      const score = Number(item?.score);
      return Number.isFinite(score) && score >= 4 && score < 8;
    });
    const visibleEvents = this._panelState.eventsExpanded ? relevantEvents : relevantEvents.slice(0, 3);
    const hiddenEventCount = Math.max(0, relevantEvents.length - visibleEvents.length);
    const historySeries = Array.isArray(current.history?.series)
      ? current.history.series.map(Number).filter(Number.isFinite)
      : [];
    const mapPoints = filterMapPoints(allMapPoints, focus, activeTheme);
    const realMarkerCount = getRealMarkerCount(mapPoints);
    const mapStatus = realMarkerCount > 0
      ? `${realMarkerCount} Kartenpunkt${realMarkerCount === 1 ? "" : "e"} im gewählten Fokus.`
      : "Für diesen Fokus liegen derzeit keine geokodierten Ereignisse vor.";
    const qualityScore = Number.isFinite(Number(dataQuality.score)) ? Number(dataQuality.score) : null;
    const qualityLabel = dataQuality.label ? String(dataQuality.label) : "unbekannt";
    const shouldRenderMap = Boolean(config.show_map && this._panelState.map);

    const markup = `
      <style>${CARD_STYLE}</style>
      <ha-card>
        <div class="shell">
          <div class="hero">
            <div class="hero-main">
              <div class="hero-topline">
                <div>
                  <div class="title">${escapeHtml(config.title)}</div>
                  <div class="sub">Automatische Lageeinschätzung · 100 = ruhig, 0 = kritisch</div>
                </div>
                <div class="updated">${escapeHtml(lastUpdate)}</div>
              </div>
              <div class="scope-tabs" role="tablist" aria-label="Lagefokus">
                ${Object.entries(focusConfig).map(([key, item]) => `
                  <button class="scope-tab ${focus === key ? "active" : ""}" type="button" role="tab" aria-selected="${focus === key ? "true" : "false"}" data-focus="${key}">${escapeHtml(item.label)}</button>
                `).join("")}
              </div>
              <div class="focus-summary">
                <div class="focus-score ${scoreState.className}">${toNumberOrNull(current.score) !== null ? `${toNumberOrNull(current.score)}<span class="score-denominator">/100</span>` : escapeHtml(current.score ?? "–")}<small>Lagewert</small></div>
                <div class="focus-copy">
                  <div class="focus-status ${scoreState.className}">${escapeHtml(scoreState.label)}</div>
                  <div class="focus-headline">${escapeHtml(current.summary?.headline || "Noch keine Lageeinschätzung verfügbar.")}</div>
                  ${current.summary?.drivers ? `<div class="focus-driver">${escapeHtml(current.summary.drivers)}</div>` : ""}
                </div>
                ${historySeries.length >= 2 ? `
                  <div class="sparkline-wrap">
                    ${renderSparkline(historySeries)}
                    <div class="trend-copy">24 h: ${escapeHtml(delta24h)}<br>7 Tage: ${escapeHtml(current.history?.label_7d || formatDelta(current.history?.delta_7d))}</div>
                  </div>
                ` : `<div class="trend-pending">→ Trend baut sich mit weiteren Updates auf.</div>`}
              </div>
              <div class="signal-strip">
                <div class="signal-card"><div class="signal-label">Datenqualität</div><div class="signal-value">${qualityScore === null ? "–" : `${qualityScore}/100`} · ${escapeHtml(qualityLabel)}</div></div>
                <div class="signal-card"><div class="signal-label">Quellen im Fokus</div><div class="signal-value">${scopeSources}</div></div>
                <div class="signal-card"><div class="signal-label">Amtliche Warnungen</div><div class="signal-value">${current.alertCount}</div></div>
              </div>
              ${meaningfulChanges.length ? `<ul class="change-list"><li>${escapeHtml(meaningfulChanges[0])}</li></ul>` : ""}
            </div>
          </div>
          <div class="grid">
            <div class="panel">
              <div class="panel-head">
                <div class="panel-title">Themenbelastung · ${escapeHtml(current.label)}</div>
                <div class="panel-note">0 = ruhig · 100 = hoch</div>
              </div>
              <div class="panel-body">
                ${renderThemeGrid(current.themes, activeTheme)}
              </div>
            </div>
            <div class="panel">
              <div class="panel-head">
                <div class="panel-title">Relevante Ereignisse</div>
                <div class="panel-note">${relevantEvents.length} Treffer${activeTheme ? " · gefiltert" : ""}</div>
              </div>
              <div class="panel-body">
                <div class="items">
                  ${visibleEvents.length ? visibleEvents.map(renderEventItem).join("") : `<div class="empty">Keine relevanten Ereignisse in diesem Fokus${activeTheme ? " und Thema" : ""}.</div>`}
                </div>
                ${hiddenEventCount ? `<div class="event-actions"><button class="event-more" type="button" data-event-action="expand">${hiddenEventCount} weitere anzeigen</button></div>` : ""}
                ${this._panelState.eventsExpanded && relevantEvents.length > 3 ? `<div class="event-actions"><button class="event-more" type="button" data-event-action="collapse">Weniger anzeigen</button></div>` : ""}
                ${secondaryEvents.length ? `
                  <details class="secondary-events">
                    <summary>Weitere Hinweise (${secondaryEvents.length})</summary>
                    <div class="items">${secondaryEvents.map(renderEventItem).join("")}</div>
                  </details>
                ` : ""}
              </div>
            </div>
            ${config.show_map ? `
              ${renderCollapsiblePanel(
                "map",
                `Lagekarte · ${escapeHtml(current.label)}`,
                `${realMarkerCount} Marker`,
                `
                  <div id="map" style="height:${Number(config.map_height) || 320}px; --lage-monitor-map-height:${Number(config.map_height) || 320}px"></div>
                  <div class="map-status">${mapStatus}</div>
                  <div class="map-selection" id="map-selection"></div>
                `,
                this._panelState.map
              )}
            ` : ""}
            ${renderCollapsiblePanel(
              "alerts",
              "Amtliche Warnungen",
              `${current.alertCount}`,
              `
                <div class="items">
                  ${current.alerts.length ? current.alerts.map((item) => `
                    <div class="item">
                      <div class="item-top">
                        <span class="source">${escapeHtml(item.source || "")}</span>
                      </div>
                      <div class="link">${escapeHtml(item.title || "Warnung ohne Titel")}</div>
                      ${item.affected_regions ? `<div class="item-meta">Betroffene Region: ${escapeHtml(item.affected_regions)}</div>` : ""}
                      ${item.description ? `<div class="summary alert-summary">${escapeHtml(item.description)}</div>` : ""}
                    </div>
                  `).join("") : `<div class="empty">Keine Warnungen in diesem Fokus vorhanden</div>`}
                </div>
              `,
              this._panelState.alerts
            )}
            ${config.show_military ? `
              ${renderCollapsiblePanel(
                "military",
                `Militärische Signale · ${escapeHtml(current.label)}`,
                `${current.military.length}`,
                `
                  <div class="items">
                    ${current.military.length ? current.military.map(renderEventItem).join("") : `<div class="empty">Keine militärischen Signalereignisse in diesem Fokus.</div>`}
                  </div>
                `,
                this._panelState.military
              )}
            ` : ""}
            ${renderCollapsiblePanel(
              "data",
              "Daten & Methodik",
              `${sourceFreshness.length} Quellen`,
              `
                <div class="quality-summary">
                  <div class="quality-score">${qualityScore === null ? "–" : `${qualityScore}/100`}</div>
                  <div class="quality-copy">Datenqualität ${escapeHtml(qualityLabel)} · ${Number(dataQuality.healthy_sources) || 0} von ${Number(dataQuality.total_sources) || 0} Quellen verfügbar · ${Number(dataQuality.stale_sources) || 0} veraltet · ${Number(dataQuality.error_sources) || 0} mit Fehler</div>
                </div>
                <div class="freshness-list">
                  ${sourceFreshness.length ? sourceFreshness.map(renderFreshnessItem).join("") : `<div class="empty">Keine Quelleninformationen verfügbar.</div>`}
                </div>
                ${config.show_keywords ? `
                  <div class="split-section-title" style="margin-top:14px">Schlüsselbegriffe</div>
                  <div class="chips">
                    ${keywords.length ? keywords.map((item) => `<span class="chip">${escapeHtml(item.keyword)} (${Number(item.count) || 0})</span>`).join("") : `<span class="empty">Noch keine Schlüsselbegriffe.</span>`}
                  </div>
                ` : ""}
                <div class="method-note" style="margin-top:14px">Die Lagewerte sind heuristische Orientierung, keine amtliche Gefahrenstufe. Ereignisse werden nach Ähnlichkeit zusammengeführt, nach Alter abgewertet und bei Bestätigung durch unabhängige Quellen moderat verstärkt. Themenwerte zeigen Belastung; der Lagewert zeigt Sicherheit.</div>
              `,
              this._panelState.data
            )}
          </div>
        </div>
      </ha-card>
    `;
    const mapSignature = JSON.stringify({
      zoom: Number(config.zoom) || 6,
      focus,
      theme: activeTheme,
      homeCenter,
      points: mapPoints.map((point) => ({
        latitude: Number(point.latitude),
        longitude: Number(point.longitude),
        key: point.key || "",
        kind: point.kind || "",
        count: Number(point.count) || 0,
        source: point.source || "",
        severity: point.severity || "",
        themes: Array.isArray(point.themes) ? point.themes : [],
        titles: Array.isArray(point.titles) ? point.titles.slice(0, 3) : [],
        items: Array.isArray(point.items) ? point.items.slice(0, 5) : []
      }))
    });
    const markupChanged = this._lastMarkup !== markup;

    if (markupChanged) {
      if (this._map) {
        this._teardownMap();
      }
      this.shadowRoot.innerHTML = markup;
      this._lastMarkup = markup;
      this._bindPanelToggles();
      this._bindScopeTabs();
      this._bindThemeFilters();
      this._bindEventActions();
    }

    if (shouldRenderMap && (markupChanged || !this._map || this._lastMapSignature !== mapSignature)) {
      const mapCenter = focus === "world" ? [20, 0] : homeCenter;
      const mapZoom = focus === "world" ? 2 : config.zoom;
      this._renderMap(mapPoints, mapCenter, mapZoom);
      this._lastMapSignature = mapSignature;
    } else if (shouldRenderMap) {
      this._refreshMapSize();
    } else {
      this._teardownMap();
      this._lastMapSignature = "";
    }
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
        this._persistPanelState();
        this.hass = this._hass;
      });
    });
  }

  _bindScopeTabs() {
    this.shadowRoot.querySelectorAll(".scope-tab").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const focus = button.dataset.focus;
        if (!["local", "germany", "world"].includes(focus) || focus === this._panelState.focus) {
          return;
        }
        this._panelState.focus = focus;
        this._panelState.theme = "";
        this._panelState.eventsExpanded = false;
        this._selectedMapPointKey = "";
        this._persistPanelState();
        this.hass = this._hass;
      });
    });
  }

  _bindThemeFilters() {
    this.shadowRoot.querySelectorAll(".theme-card[data-theme]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const theme = button.dataset.theme || "";
        this._panelState.theme = this._panelState.theme === theme ? "" : theme;
        this._panelState.eventsExpanded = false;
        this._selectedMapPointKey = "";
        this._persistPanelState();
        this.hass = this._hass;
      });
    });
  }

  _bindEventActions() {
    this.shadowRoot.querySelectorAll("[data-event-action]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        this._panelState.eventsExpanded = button.dataset.eventAction === "expand";
        this._persistPanelState();
        this.hass = this._hass;
      });
    });
  }

  _setMapSelection(point, markerCount) {
    const selection = this.shadowRoot.getElementById("map-selection");
    if (!selection) {
      return;
    }
    if (!point) {
      this._selectedMapPointKey = "";
      selection.innerHTML = `<div class="empty">Keinen Kartenpunkt ausgewählt.</div>`;
      return;
    }

    this._selectedMapPointKey = point.key || "";
    const items = Array.isArray(point.items) && point.items.length
      ? point.items
      : point.titles.map((title) => ({ title }));
    const label = point.kind === "home"
      ? "Home-Position"
      : `${point.count} Meldung${point.count === 1 ? "" : "en"} / News an diesem Punkt`;
    const itemMarkup = items.length
      ? items.slice(0, 5).map((item) => {
          const title = escapeHtml(item.title || "Warnung");
          const link = safeHttpLink(item.link);
          const titleMarkup = link
            ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${title}</a>`
            : `<span>${title}</span>`;
          const meta = [item.source, item.severity].filter(Boolean).map(escapeHtml).join(" | ");
          return `<div class="map-selection-item">${titleMarkup}${meta ? `<div class="map-selection-meta">${meta}</div>` : ""}</div>`;
        }).join("")
      : `<div class="empty">Zu diesem Kartenpunkt sind keine Detailmeldungen verfügbar.</div>`;

    selection.innerHTML = `
      <div class="map-selection-title">${escapeHtml(point.title || label)}</div>
      <div class="map-status">${escapeHtml(point.source || label)}${markerCount ? ` | ${markerCount} Kartenpunkte gesamt` : ""}</div>
      <div class="map-selection-items">${itemMarkup}</div>
    `;
  }

  async _renderMap(points, homeCenter, zoom) {
    const mapRoot = this.shadowRoot.getElementById("map");
    if (!mapRoot) {
      this._teardownMap();
      return;
    }

    const renderToken = ++this._mapRenderToken;

    try {
      const L = await ensureLeaflet();
      if (renderToken !== this._mapRenderToken || !this.isConnected) {
        return;
      }

      const mapHostChanged = this._mapHost !== mapRoot;
      if (!this._map || mapHostChanged) {
        this._teardownMap();
        this._map = L.map(mapRoot, {
          zoomControl: true,
          attributionControl: true,
          scrollWheelZoom: false
        });
        this._mapHost = mapRoot;
        this._mapLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 18
        }).addTo(this._map);
        this._mapMarkersLayer = L.layerGroup().addTo(this._map);

        if (typeof ResizeObserver !== "undefined") {
          this._mapResizeObserver = new ResizeObserver(() => {
            this._refreshMapSize();
          });
          this._mapResizeObserver.observe(mapRoot);
        }
      }

      if (!this._mapMarkersLayer) {
        this._mapMarkersLayer = L.layerGroup().addTo(this._map);
      } else {
        this._mapMarkersLayer.clearLayers();
      }

      const selectedPoint = points.find((point) => point.key === this._selectedMapPointKey)
        || points.find((point) => point.kind !== "home")
        || points.find((point) => point.kind === "home")
        || null;
      this._setMapSelection(selectedPoint, getRealMarkerCount(points));

      const bounds = [];
      for (const point of points) {
        const lat = Number(point.latitude);
        const lon = Number(point.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
          continue;
        }
        if (point.kind === "home") {
          const marker = L.circleMarker([lat, lon], {
            radius: 8,
            color: "#ffffff",
            weight: 3,
            fillColor: "#2563eb",
            fillOpacity: 0.96
          }).addTo(this._mapMarkersLayer).bindPopup(`
            <strong>Home</strong><br>
            ${escapeHtml(point.severity || "Home Assistant Fokus")}
          `);
          marker.on("click", () => this._setMapSelection(point, getRealMarkerCount(points)));
          if (point.key === this._selectedMapPointKey) {
            marker.openPopup();
          }
          bounds.push([lat, lon]);
          continue;
        }

        const radius = Math.min(22, 7 + Math.sqrt(Math.max(1, point.count || 1)) * 3.5);
        const items = Array.isArray(point.items) && point.items.length
          ? point.items
          : point.titles.map((title) => ({ title }));
        const popupItems = items.slice(0, 3).map((item) => {
          const title = escapeHtml(item.title || "Meldung");
          const link = safeHttpLink(item.link);
          return link
            ? `<br><a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${title}</a>`
            : `<br>${title}`;
        }).join("");
        const marker = L.circleMarker([lat, lon], {
          radius,
          color: "#b91c1c",
          weight: 2,
          fillColor: "#f97316",
          fillOpacity: 0.78,
          bubblingMouseEvents: false
        }).addTo(this._mapMarkersLayer).bindPopup(`
          <strong>${point.count} Meldung${point.count === 1 ? "" : "en"} / News</strong><br>
          ${escapeHtml(point.source || "")}
          ${popupItems}
        `);
        marker.on("click", () => this._setMapSelection(point, getRealMarkerCount(points)));
        if (point.key === this._selectedMapPointKey) {
          marker.openPopup();
        }
        bounds.push([lat, lon]);
      }

      const homePoint = points.find((point) => point.kind === "home");
      if (bounds.length > 1) {
        this._map.fitBounds(bounds, { padding: [24, 24] });
      } else if (bounds.length === 1) {
        this._map.setView(bounds[0], zoom || 6);
      } else if (homePoint) {
        this._map.setView([homePoint.latitude, homePoint.longitude], zoom || 6);
      } else {
        this._map.setView(homeCenter, zoom || 6);
      }

      this._refreshMapSize();
    } catch (_) {
      if (renderToken !== this._mapRenderToken) {
        return;
      }
      this._teardownMap();
      mapRoot.innerHTML = `<div class="empty" style="padding:16px">Karte konnte derzeit nicht geladen werden.</div>`;
    }
  }

  _teardownMap() {
    if (this._mapResizeObserver) {
      this._mapResizeObserver.disconnect();
      this._mapResizeObserver = null;
    }
    if (this._map) {
      this._map.remove();
      this._map = null;
    }
    this._mapLayer = null;
    this._mapMarkersLayer = null;
    this._mapHost = null;
  }

  _refreshMapSize() {
    requestAnimationFrame(() => {
      if (this._map) {
        this._map.invalidateSize(false);
      }
    });
    window.setTimeout(() => {
      if (this._map) {
        this._map.invalidateSize(false);
      }
    }, 250);
  }

  _getPanelStorageKey() {
    const config = this._config || DEFAULT_CONFIG;
    return `lage-monitor-card:${config.entity || "default"}:${config.title || "Lage Monitor"}:panels`;
  }

  _restorePanelState() {
    try {
      const raw = window.localStorage.getItem(this._getPanelStorageKey());
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw);
      this._panelState = {
        ...this._panelState,
        ...parsed
      };
    } catch (_) {
      // Ignore broken persisted panel state and keep defaults.
    }
  }

  _persistPanelState() {
    try {
      window.localStorage.setItem(this._getPanelStorageKey(), JSON.stringify(this._panelState));
    } catch (_) {
      // Ignore storage failures; collapsible panels still work for this session.
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
            ${this._field("map_height", "Kartenhöhe", config.map_height, "number")}
          </div>
          <div class="editor-toggle-grid">
            ${this._toggle("show_map", "Karte anzeigen", config.show_map)}
            ${this._toggle("show_keywords", "Schlüsselbegriffe anzeigen", config.show_keywords)}
            ${this._toggle("show_military", "Militärbereich anzeigen", config.show_military)}
          </div>
        </div>
        <div class="editor-section">
          <div class="editor-title">Entitäten</div>
          <div class="editor-help">Normalerweise musst du hier nichts ändern. Die Karte erkennt deutsche und englische Standard-Entity-IDs automatisch.</div>
          <div class="editor-grid single">
            ${this._field("entity", "Score-Entity", config.entity || "")}
            ${this._field("alerts_entity", "Alerts-Entity", config.alerts_entity || "")}
            ${this._field("stability_entity", "Stabilitäts-Entity", config.stability_entity || "")}
            ${this._field("military_entity", "Militär-Entity", config.military_entity || "")}
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
        <input data-key="${escapeHtml(key)}" type="${escapeHtml(type)}" value="${escapeHtml(value ?? "")}">
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
