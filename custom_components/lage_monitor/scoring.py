"""Pure scoring helpers for Lage Monitor.

This module intentionally has no Home Assistant imports so it can be unit
tested without a running Home Assistant instance.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import math
import re
import statistics

from . import geo
from .const import KEYWORD_WEIGHTS, MILITARY_KEYWORDS, NATIONAL_PRIORITY_KEYWORDS

# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

# Keywords that are safe to match inside German compounds
# ("Terroranschlag", "Raketenangriff", "Grossbrand" ...).
COMPOUND_SAFE: frozenset[str] = frozenset(
    {
        "anschlag",
        "terror",
        "terrorismus",
        "explosion",
        "schuesse",
        "schüsse",
        "amok",
        "geiselnahme",
        "messerangriff",
        "brandanschlag",
        "großbrand",
        "grossbrand",
        "ausschreitungen",
        "unruhen",
        "evakuierung",
        "wohnungseinbruch",
        "angriff",
        "kriegsschiff",
        "bundeswehr",
        "luftwaffe",
    }
)

# Short or ambiguous words: whole word only (plus plural/genitive endings).
EXACT_WORD: frozenset[str] = frozenset(
    {"nato", "usa", "iran", "china", "israel", "tote", "marine", "ausfall"}
)

# Custom patterns where a plain substring would be wrong.
# "Kostenexplosion" / "Preisexplosion" are economics, not an explosion.
CUSTOM_PATTERNS: dict[str, str] = {
    "explosion": r"(?<!kosten)(?<!preis)(?<!preise)(?<!zahlen)(?<!mieten)explosion",
}

# Hits that are never "just a word in a sports or business headline".
STRONG_KEYWORDS: frozenset[str] = frozenset(
    {
        "anschlag",
        "terror",
        "terrorismus",
        "explosion",
        "schuesse",
        "schüsse",
        "messerangriff",
        "amok",
        "geiselnahme",
        "brandanschlag",
        "evakuierung",
        "großbrand",
        "grossbrand",
        "attentat",
        "detonation",
        "bomb",
        "spreng",
        "massenpanik",
    }
)

# Priority keywords that only force a high score together with other signals.
WEAK_PRIORITY: frozenset[str] = frozenset(
    {"angriff", "menschenmenge", "gewalttat", "ausschreitungen", "unruhen"}
)
WEAK_PRIORITY_MIN_WEIGHT = 13  # e.g. "angriff" (7) + "verletzte" (6)
PRIORITY_FLOOR = 24

# On police feeds the word "polizei" carries no information.
POLICE_FEED_NEUTRAL: frozenset[str] = frozenset({"polizei"})

# Routine police notices should remain visible as context, but must not rank
# like public-impact incidents. Priority/strong terms bypass this cap.
ROUTINE_POLICE_SCORE_CAP = 7

SPORT_MARKERS: tuple[str, ...] = (
    "bundesliga", "fußball", "fussball", "dfb", "champions league", "europa league",
    "handball", "basketball", "eishockey", "formel 1", "tennis", "spieltag",
    "pokal", "trainer", "olympia", "stürmer", "abwehrspieler", "wm-qualifikation",
)
FINANCE_MARKERS: tuple[str, ...] = (
    "aktie", "dax", "börse", "kurs", "umsatz", "konjunktur", "anleger",
    "gewinneinbruch", "auftragseingang", "absatz", "quartalszahlen",
)
DEESCALATION_MARKERS: tuple[str, ...] = (
    "fehlalarm", "entwarnung", "probealarm", "übung", "blindgänger",
    "weltkriegsbombe", "entschärft", "bestätigt sich nicht",
)
NEGATION_RE = re.compile(
    r"(?<!\w)kein(?:e|en|er|em)?\s+(?:\w+\s+){0,2}"
    r"(?:anschlag|terror|gefahr|explosion|hinweis)"
)

DAMPEN_CONTEXT = 0.2
DAMPEN_DEESCALATION = 0.4
DAMPEN_NEGATION = 0.3

DE_TOKENS: tuple[str, ...] = (
    "deutschland", "berlin", "hamburg", "nrw", "bayern", "nordrhein-westfalen",
    "baden-württemberg", "niedersachsen", "sachsen", "thüringen", "brandenburg",
    "hessen", "rheinland-pfalz", "saarland", "schleswig-holstein",
    "mecklenburg-vorpommern", "bremen", "münchen", "köln", "frankfurt",
    "stuttgart", "bundestag", "bundesregierung", "bundeswehr",
)
WORLD_TOKENS: tuple[str, ...] = (
    "ukraine", "russland", "china", "usa", "iran", "israel", "gaza", "syrien",
    "nordkorea", "taiwan", "kreml", "pentagon", "washington", "moskau", "kiew",
    "peking", "teheran", "libanon", "jemen",
)
NEIGHBOR_TOKENS: tuple[str, ...] = (
    "polen", "tschechien", "österreich", "schweiz", "frankreich", "niederlande",
    "belgien", "luxemburg", "dänemark", "litauen", "lettland", "estland",
    "ostsee", "baltikum", "kaliningrad",
)


def _compile_keyword(keyword: str) -> re.Pattern[str]:
    """Build a matching pattern for one keyword."""
    if keyword in CUSTOM_PATTERNS:
        return re.compile(CUSTOM_PATTERNS[keyword])
    escaped = re.escape(keyword)
    if keyword in COMPOUND_SAFE:
        return re.compile(escaped)
    if keyword in EXACT_WORD:
        return re.compile(rf"(?<!\w){escaped}(?:e|en|s)?(?!\w)")
    # Default: must start a word ("Einbruch", "Einbruchsserie" yes,
    # "Kurseinbruch" no), with an optional ending.
    return re.compile(rf"(?<!\w){escaped}\w{{0,12}}")


def _compile_all(keywords: Iterable[str]) -> dict[str, re.Pattern[str]]:
    return {keyword: _compile_keyword(keyword) for keyword in keywords}


_KEYWORD_PATTERNS = _compile_all(KEYWORD_WEIGHTS)
_MILITARY_PATTERNS = _compile_all(MILITARY_KEYWORDS)
_PRIORITY_PATTERNS = _compile_all(NATIONAL_PRIORITY_KEYWORDS)


def _token_regex(tokens: Iterable[str]) -> re.Pattern[str]:
    return re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(token) for token in tokens) + r")(?!\w)"
    )


_DE_RE = _token_regex(DE_TOKENS)
_WORLD_RE = _token_regex(WORLD_TOKENS)
_NEIGHBOR_RE = _token_regex(NEIGHBOR_TOKENS)


def _hits(patterns: dict[str, re.Pattern[str]], text: str) -> list[str]:
    return [keyword for keyword, pattern in patterns.items() if pattern.search(text)]


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


@dataclass(slots=True)
class ScoreResult:
    """Result of scoring a single text item."""

    score: int
    keywords: list[str] = field(default_factory=list)
    priority_keywords: list[str] = field(default_factory=list)
    military_keywords: list[str] = field(default_factory=list)
    military_score: int = 0
    region: str = "de"
    near_abroad: bool = False
    dampened: bool = False
    state: str | None = None  # Bundesland code (e.g. "NW") when known


def classify_region(text: str, source: str) -> tuple[str, bool]:
    """Return ("de" | "world", near_abroad) using token majority, not order."""
    counts = geo.count_by_country(text)
    # Tokens and gazetteer overlap, so take the larger of the two per side.
    de_hits = max(len(_DE_RE.findall(text)), counts.get("DE", 0))
    world_hits = max(
        len(_WORLD_RE.findall(text)),
        sum(n for code, n in counts.items() if code != "DE" and code not in geo.NEIGHBOR_COUNTRIES),
    )
    near_abroad = bool(_NEIGHBOR_RE.search(text)) or any(
        code in geo.NEIGHBOR_COUNTRIES for code in counts
    )

    if source.startswith(("presseportal", "custom_press_")):
        return "de", near_abroad
    default = "world" if source == "tagesschau_ausland" else "de"
    if world_hits > de_hits:
        return "world", near_abroad
    if de_hits > 0 and de_hits >= world_hits:
        return "de", near_abroad
    return default, near_abroad


def score_text(title: str, summary: str, source: str) -> ScoreResult:
    """Score one feed item (title + summary) from a given source."""
    text = f"{title} {summary}".lower()

    is_police_feed = source.startswith("presseportal") or source.startswith("custom_press_")
    neutral = POLICE_FEED_NEUTRAL if is_police_feed else frozenset()

    matched = [kw for kw in _hits(_KEYWORD_PATTERNS, text) if kw not in neutral]
    priority = _hits(_PRIORITY_PATTERNS, text)
    military = _hits(_MILITARY_PATTERNS, text)

    weight_sum = sum(KEYWORD_WEIGHTS[kw] for kw in matched)
    score = weight_sum

    strong_hit = any(kw in STRONG_KEYWORDS for kw in (*matched, *priority))

    factor = 1.0
    if not strong_hit and (
        _contains_any(text, SPORT_MARKERS) or _contains_any(text, FINANCE_MARKERS)
    ):
        factor = min(factor, DAMPEN_CONTEXT)
    if _contains_any(text, DEESCALATION_MARKERS):
        factor = min(factor, DAMPEN_DEESCALATION)
    if NEGATION_RE.search(text):
        factor = min(factor, DAMPEN_NEGATION)

    if factor == 1.0:
        strong_priority = [kw for kw in priority if kw not in WEAK_PRIORITY]
        weak_priority = [kw for kw in priority if kw in WEAK_PRIORITY]
        if strong_priority or (weak_priority and weight_sum >= WEAK_PRIORITY_MIN_WEIGHT):
            score = max(score, PRIORITY_FLOOR)

    region, near_abroad = classify_region(text, source)

    if source == "tagesschau_ausland":
        score += 2
    if is_police_feed:
        score += 3
    if _DE_RE.search(text) or _WORLD_RE.search(text):
        score += 2

    if factor < 1.0:
        score = int(score * factor)

    if is_police_feed and not strong_hit and not priority:
        score = min(score, ROUTINE_POLICE_SCORE_CAP)

    state = None
    dienst = geo.parse_dienststelle(title)
    if dienst:
        state = dienst[0]
    else:
        located = geo.locate(title, summary)
        if located is not None and located.country == "DE":
            state = located.state

    military_score = sum(MILITARY_KEYWORDS[kw] for kw in military)
    if factor < 1.0:
        military_score = int(military_score * max(factor, DAMPEN_DEESCALATION))

    return ScoreResult(
        score=min(score, 100),
        keywords=list(dict.fromkeys([*matched, *priority])),
        priority_keywords=priority,
        military_keywords=military,
        military_score=min(military_score, 100),
        region=region,
        near_abroad=near_abroad,
        dampened=factor < 1.0,
        state=state,
    )


# ---------------------------------------------------------------------------
# Clustering, decay and corroboration
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "der", "die", "das", "und", "oder", "mit", "von", "den", "dem", "des",
        "ein", "eine", "einer", "einem", "für", "auf", "nach", "bei", "aus",
        "ist", "sind", "wird", "wurde", "worden", "nicht", "sich", "auch",
        "über", "unter", "zum", "zur", "im", "am", "als", "wie", "nur",
    }
)
_WORD_RE = re.compile(r"\w{3,}")


def title_tokens(title: str) -> frozenset[str]:
    """Return a normalised token set used for near-duplicate detection."""
    return frozenset(
        word for word in _WORD_RE.findall(title.lower()) if word not in _STOPWORDS
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_items(items: Sequence[dict], threshold: float = 0.5) -> list[list[dict]]:
    """Greedy near-duplicate clustering by title token overlap.

    Items are visited from highest to lowest score, so the first item of
    every cluster is its most severe member.
    """
    ordered = sorted(items, key=lambda item: int(item.get("score") or 0), reverse=True)
    clusters: list[tuple[frozenset[str], list[dict]]] = []
    for item in ordered:
        tokens = title_tokens(str(item.get("title") or ""))
        for cluster_tokens, members in clusters:
            if _jaccard(tokens, cluster_tokens) >= threshold:
                members.append(item)
                break
        else:
            clusters.append((tokens, [item]))
    return [members for _, members in clusters]


def decay_factor(age_hours: float, half_life_hours: float = 12.0) -> float:
    """Exponential time decay: 1.0 now, 0.5 after one half-life."""
    if age_hours <= 0:
        return 1.0
    return 0.5 ** (age_hours / half_life_hours)


def aggregate_risk(
    items: Sequence[dict],
    now: datetime | None = None,
    *,
    half_life_hours: float = 12.0,
    corroboration_step: float = 0.15,
    corroboration_cap: float = 1.45,
) -> float:
    """Sum item scores with de-duplication, decay and corroboration.

    * Near-duplicate headlines count once (the most severe member).
    * Older items weigh less (``published_dt`` key, timezone-aware datetime).
    * A story reported by several *distinct sources* gets a bounded bonus.

    The result does not grow just because more copies of one story are fetched.
    """
    total = 0.0
    for members in cluster_items(items):
        best = members[0]
        weight = 1.0
        published = best.get("published_dt")
        if now is not None and isinstance(published, datetime):
            age_hours = (now - published).total_seconds() / 3600
            weight = decay_factor(age_hours, half_life_hours)
        sources = {str(member.get("source") or "") for member in members}
        corroboration = min(
            corroboration_cap, 1.0 + corroboration_step * (len(sources) - 1)
        )
        total += int(best.get("score") or 0) * weight * corroboration
    return total


# ---------------------------------------------------------------------------
# Baseline deviation
# ---------------------------------------------------------------------------


def baseline_deviation(
    current: float, history: Sequence[float], min_samples: int = 12
) -> dict[str, float | str] | None:
    """Compare ``current`` with the usual level using a robust z-score.

    Returns None while there are too few samples. Median/MAD are used so a
    single past spike does not distort what counts as "normal".
    """
    values = [float(v) for v in history if v is not None and not math.isnan(float(v))]
    if len(values) < min_samples:
        return None
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    scale = 1.4826 * mad
    if scale < 1.0:  # near-constant history: avoid exploding z-scores
        scale = 1.0
    z = (current - median) / scale
    if z >= 2.0:
        label = "deutlich über Normalniveau"
    elif z >= 1.0:
        label = "über Normalniveau"
    elif z <= -1.0:
        label = "unter Normalniveau"
    else:
        label = "im Normalbereich"
    return {"z": round(z, 2), "median": round(median, 1), "label": label}
