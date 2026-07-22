"""Constants for Lage Monitor."""

from __future__ import annotations

DOMAIN = "lage_monitor"
FRONTEND_BASE_URL = f"/{DOMAIN}_frontend"
CARD_FILENAME = "lage-monitor-card.js"
CARD_RESOURCE_URL = f"{FRONTEND_BASE_URL}/{CARD_FILENAME}"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_NINA_ARS = "nina_ars"
CONF_INCLUDE_POLICE = "include_police"
CONF_INCLUDE_PRESS = "include_press"
CONF_INCLUDE_NEWS = "include_news"
CONF_NEWS_LIMIT = "news_limit"
CONF_POLICE_COUNT_MODE = "police_count_mode"
CONF_FOCUS_MODE = "focus_mode"
CONF_LOCAL_KEYWORDS = "local_keywords"
CONF_CUSTOM_PRESS_FEEDS = "custom_press_feeds"
CONF_ALERT_RADIUS_KM = "alert_radius_km"

DEFAULT_SCAN_INTERVAL = 300
DEFAULT_NINA_ARS = ""
DEFAULT_INCLUDE_POLICE = True
DEFAULT_INCLUDE_PRESS = True
DEFAULT_INCLUDE_NEWS = True
DEFAULT_NEWS_LIMIT = 20
DEFAULT_POLICE_COUNT_MODE = "all"
DEFAULT_FOCUS_MODE = "germany"
DEFAULT_LOCAL_KEYWORDS = ""
DEFAULT_CUSTOM_PRESS_FEEDS = ""
DEFAULT_ALERT_RADIUS_KM = 50

ATTR_ALERTS = "alerts"
ATTR_HEADLINES = "headlines"
ATTR_SOURCES = "sources"
ATTR_LAST_UPDATE = "last_update"
ATTR_SCORE_BREAKDOWN = "score_breakdown"
ATTR_TOP_KEYWORDS = "top_keywords"
ATTR_MAP_MARKERS = "map_markers"
ATTR_MILITARY_ITEMS = "military_items"
ATTR_SOURCE_STATUS = "source_status"
ATTR_DIAGNOSTICS = "diagnostics"
ATTR_HOME_COORDINATES = "home_coordinates"

NINA_BASE_URL = "https://nina.api.bund.dev"

GERMAN_NEWS_FEEDS: dict[str, str] = {
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
