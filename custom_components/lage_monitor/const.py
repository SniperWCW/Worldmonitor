"""Constants for Lage Monitor."""

from __future__ import annotations

DOMAIN = "lage_monitor"
FRONTEND_BASE_URL = f"/{DOMAIN}_frontend"
CARD_FILENAME = "lage-monitor-card.js"
CARD_RESOURCE_VERSION = "0.1.32"
CARD_RESOURCE_URL = f"{FRONTEND_BASE_URL}/{CARD_FILENAME}?v={CARD_RESOURCE_VERSION}"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_NINA_ARS = "nina_ars"
CONF_WARN_AREA = "warn_area"
CONF_INCLUDE_POLICE = "include_police"
CONF_INCLUDE_PRESS = "include_press"
CONF_INCLUDE_NEWS = "include_news"
CONF_WARN_MOWAS = "warn_mowas"
CONF_WARN_DWD = "warn_dwd"
CONF_WARN_LHP = "warn_lhp"
CONF_WARN_POLICE = "warn_police"
CONF_NEWS_LIMIT = "news_limit"
CONF_POLICE_COUNT_MODE = "police_count_mode"
CONF_FOCUS_MODE = "focus_mode"
CONF_LOCAL_KEYWORDS = "local_keywords"
CONF_CUSTOM_PRESS_FEEDS = "custom_press_feeds"
CONF_ALERT_RADIUS_KM = "alert_radius_km"

DEFAULT_SCAN_INTERVAL = 300
DEFAULT_NINA_ARS = ""
DEFAULT_WARN_AREA = ""
DEFAULT_INCLUDE_POLICE = True
DEFAULT_INCLUDE_PRESS = True
DEFAULT_INCLUDE_NEWS = True
DEFAULT_WARN_MOWAS = True
DEFAULT_WARN_DWD = True
DEFAULT_WARN_LHP = True
DEFAULT_WARN_POLICE = True
DEFAULT_NEWS_LIMIT = 20
DEFAULT_POLICE_COUNT_MODE = "all"
DEFAULT_FOCUS_MODE = "germany"
DEFAULT_LOCAL_KEYWORDS = ""
DEFAULT_CUSTOM_PRESS_FEEDS = ""
DEFAULT_ALERT_RADIUS_KM = 50

ATTR_ALERTS = "alerts"
ATTR_HEADLINES = "headlines"
ATTR_LOCAL_HEADLINES = "local_headlines"
ATTR_GERMANY_HEADLINES = "germany_headlines"
ATTR_WORLD_HEADLINES = "world_headlines"
ATTR_SOURCES = "sources"
ATTR_LAST_UPDATE = "last_update"
ATTR_SCORE_BREAKDOWN = "score_breakdown"
ATTR_TOP_KEYWORDS = "top_keywords"
ATTR_MAP_MARKERS = "map_markers"
ATTR_MILITARY_ITEMS = "military_items"
ATTR_MILITARY_ITEMS_GERMANY = "military_items_germany"
ATTR_MILITARY_ITEMS_WORLD = "military_items_world"
ATTR_MILITARY_SIGNAL_GERMANY = "military_signal_germany"
ATTR_MILITARY_SIGNAL_WORLD = "military_signal_world"
ATTR_SOURCE_STATUS = "source_status"
ATTR_DIAGNOSTICS = "diagnostics"
ATTR_HOME_COORDINATES = "home_coordinates"
ATTR_ANALYSIS_SUMMARY = "analysis_summary"
ATTR_RISK_DRIVERS = "risk_drivers"
ATTR_SCORE_TREND = "score_trend"
ATTR_GLOBAL_SCORE = "global_score"
ATTR_LOCAL_SCORE = "local_score"
ATTR_GERMANY_RISK_SCORE = "germany_risk_score"
ATTR_GLOBAL_RISK_SCORE = "global_risk_score"
ATTR_LOCAL_RISK_SCORE = "local_risk_score"
ATTR_RISK_COMPONENTS = "risk_components"
ATTR_HISTORY_SUMMARY = "history_summary"
ATTR_SOURCE_FRESHNESS = "source_freshness"

WARNUNG_BUND_BASE_URL = "https://warnung.bund.de/api31"
WARNUNG_BUND_ASSETS_BASE_URL = "https://warnung.bund.de/assets/json"

GERMAN_NEWS_FEEDS: dict[str, str] = {
    "tagesschau_all": "https://www.tagesschau.de/infoservices/alle-meldungen-100~rss2.xml",
    "tagesschau_inland": "https://www.tagesschau.de/inland/index~rss2.xml",
    "tagesschau_ausland": "https://www.tagesschau.de/ausland/index~rss2.xml",
    "ntv_top": "https://www.n-tv.de/rss",
    "stern_politik": "https://www.stern.de/feed/standard/politik/",
    "welt_politik": "https://www.welt.de/politik/?service=Rss",
}

PRESSEPORTAL_FEEDS: dict[str, str] = {
    "presseportal_blaulicht": "https://www.presseportal.de/rss/polizei/typ/1.rss2",
    "presseportal_storys": "https://www.presseportal.de/rss/presseportal.rss2?langid=1",
}

POLICE_COUNT_MODE_ALL = "all"
POLICE_COUNT_MODE_RELEVANT = "relevant"
FOCUS_MODE_GERMANY = "germany"
FOCUS_MODE_LOCAL = "local"

KEYWORD_WEIGHTS: dict[str, int] = {
    "anschlag": 12,
    "terror": 12,
    "terrorismus": 12,
    "explosion": 10,
    "schuesse": 10,
    "schüsse": 10,
    "messerangriff": 10,
    "amok": 10,
    "geiselnahme": 10,
    "unruhen": 8,
    "ausschreitungen": 8,
    "brandanschlag": 8,
    "angriff": 7,
    "einbruch": 6,
    "eingebrochen": 6,
    "einbrecher": 6,
    "wohnungseinbruch": 8,
    "zeugen gesucht": 3,
    "diebstahl": 4,
    "gewalt": 7,
    "verletzte": 6,
    "tote": 9,
    "polizei": 4,
    "evakuierung": 6,
    "warnung": 6,
    "großbrand": 8,
    "grossbrand": 8,
    "störung": 3,
    "stoerung": 3,
    "ausfall": 4,
    "drohung": 6,
    "gefährdung": 6,
    "gefährlich": 5,
}

# These events must remain visible even when the monitor is focused on Home.
NATIONAL_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "anschlag",
    "attentat",
    "terror",
    "explosion",
    "detonation",
    "bomb",
    "spreng",
    "amok",
    "geiselnahme",
    "messerangriff",
    "menschenmenge",
    "massenpanik",
    "ausschreitungen",
    "unruhen",
    "gewalttat",
    "angriff",
)

MILITARY_KEYWORDS: dict[str, int] = {
    "bundeswehr": 6,
    "drohne": 5,
    "drone": 5,
    "fighter jet": 8,
    "flotten": 6,
    "kriegsschiff": 8,
    "luftwaffe": 8,
    "marine": 7,
    "militär": 8,
    "militaer": 8,
    "missile": 8,
    "nato": 5,
    "rakete": 8,
    "russian military": 8,
    "soldaten": 6,
    "truppen": 7,
}
