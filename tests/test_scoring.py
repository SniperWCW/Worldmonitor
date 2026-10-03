"""Unit tests for lage_monitor.scoring (no Home Assistant needed).

Run from the repository root:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest

# Load the package without executing its __init__ (which imports Home Assistant).
PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
pkg = types.ModuleType("lm")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["lm"] = pkg

from lm import scoring  # noqa: E402


def score(title: str, summary: str = "", source: str = "tagesschau_all"):
    return scoring.score_text(title, summary, source)


class KeywordMatchingTests(unittest.TestCase):
    def test_word_boundary_avoids_compound_false_positive(self):
        self.assertNotIn("einbruch", score("Kurseinbruch an der Börse").keywords)

    def test_real_burglary_matches(self):
        self.assertIn("einbruch", score("Einbruch in Supermarkt").keywords)
        self.assertIn("einbruch", score("Einbruchsserie im Landkreis").keywords)

    def test_nato_not_inside_other_words(self):
        self.assertEqual([], score("Senator besucht Berlin").military_keywords)
        self.assertIn("nato", score("Nato-Gipfel beginnt").military_keywords)

    def test_compound_terror_attack_matches(self):
        self.assertIn("anschlag", score("Terroranschlag in der Innenstadt").keywords)
        self.assertGreaterEqual(score("Terroranschlag in der Innenstadt").score, 24)

    def test_cost_explosion_is_not_explosion(self):
        self.assertNotIn("explosion", score("Kostenexplosion bei Bahnprojekt").keywords)
        self.assertIn("explosion", score("Explosion in Chemiewerk").keywords)


class ContextTests(unittest.TestCase):
    def test_sports_attack_is_dampened(self):
        football = score("Bundesliga: Angriff der Bayern überrollt Gegner")
        real = score("Angriff mit Messer: drei Verletzte")
        self.assertTrue(football.dampened)
        self.assertLess(football.score, 8)
        self.assertGreaterEqual(real.score, 24)

    def test_terror_in_sports_context_is_not_dampened(self):
        result = score("Anschlag vor dem Bundesliga-Spiel", source="tagesschau_all")
        self.assertFalse(result.dampened)
        self.assertGreaterEqual(result.score, 24)

    def test_negation_and_false_alarm(self):
        self.assertTrue(score("Keine Hinweise auf einen Anschlag").dampened)
        self.assertTrue(score("Fehlalarm: Explosion war Übung").dampened)

    def test_ww2_bomb_disposal_not_top_priority(self):
        self.assertLess(score("Weltkriegsbombe entschärft, Evakuierung beendet").score, 24)

    def test_weak_priority_needs_corroboration(self):
        alone = score("Angriff auf Pressekonferenz im Parlament")
        with_injuries = score("Angriff auf Bahnhof: Verletzte")
        self.assertLess(alone.score, 24)
        self.assertGreaterEqual(with_injuries.score, 24)


class PoliceFeedTests(unittest.TestCase):
    def test_police_word_not_counted_on_police_feed(self):
        result = score("Polizei sucht Zeugen", source="presseportal_blaulicht")
        self.assertNotIn("polizei", result.keywords)

    def test_police_word_counts_elsewhere(self):
        self.assertIn("polizei", score("Polizei sperrt Straße").keywords)

    def test_police_feed_is_always_germany(self):
        self.assertEqual("de", score("Meldung zu USA und Iran", source="presseportal_blaulicht").region)

    def test_routine_traffic_accident_is_capped_below_relevant(self):
        result = score(
            "POL-S: Zwei leicht Verletzte nach Auffahrunfall",
            "Bei einem Verkehrsunfall wurden zwei Personen leicht verletzt.",
            source="presseportal_blaulicht",
        )
        self.assertLess(result.score, 8)

    def test_routine_witness_search_is_capped_below_relevant(self):
        result = score(
            "POL-S: Unklarer Unfallhergang - Zeugen gesucht",
            source="presseportal_blaulicht",
        )
        self.assertLess(result.score, 8)

    def test_public_impact_police_incident_is_not_capped(self):
        result = score(
            "POL-K: Explosion und Evakuierung nach Großbrand",
            source="presseportal_blaulicht",
        )
        self.assertGreaterEqual(result.score, 8)


class RegionTests(unittest.TestCase):
    def test_majority_decides_not_order(self):
        text = "Berlin und Bayern diskutieren, Ukraine am Rande"
        self.assertEqual("de", scoring.classify_region(text.lower(), "tagesschau_all")[0])

    def test_world_when_world_dominates(self):
        text = "russland und china und iran verhandeln in berlin"
        self.assertEqual("world", scoring.classify_region(text, "tagesschau_all")[0])

    def test_usa_not_inside_other_words(self):
        self.assertEqual("de", scoring.classify_region("hausarzt in hessen", "tagesschau_all")[0])

    def test_near_abroad_flag(self):
        self.assertTrue(scoring.classify_region("drohne über litauen", "ntv_top")[1])
        self.assertFalse(scoring.classify_region("regen in hessen", "ntv_top")[1])


class GeoRegionTests(unittest.TestCase):
    def test_city_names_decide_region_without_tokens(self):
        self.assertEqual("world", scoring.classify_region("raketenangriff auf kiew und charkiw", "tagesschau_all")[0])
        self.assertEqual("de", scoring.classify_region("brand in dortmund und bochum", "ntv_top")[0])

    def test_neighbour_country_sets_near_abroad_not_world(self):
        region, near = scoring.classify_region("unfall bei prag", "ntv_top")
        self.assertEqual("de", region)  # source default, nothing German or far away
        self.assertTrue(near)

    def test_state_is_exposed(self):
        self.assertEqual("NW", score("POL-DO: Einbruch", source="presseportal_blaulicht").state)
        self.assertEqual("BY", score("Sturm über Bayern").state)
        self.assertIsNone(score("Allgemeine Meldung").state)


class GazetteerRegionTests(unittest.TestCase):
    def test_gazetteer_cities_decide_region(self):
        self.assertEqual("de", scoring.classify_region("brand in essen und bochum", "tagesschau_all")[0])
        self.assertEqual("world", scoring.classify_region("angriff auf kiew und charkiw", "tagesschau_all")[0])

    def test_neighbour_country_sets_near_abroad_without_becoming_world(self):
        region, near = scoring.classify_region("drohne ueber polen gesichtet", "tagesschau_all")
        self.assertTrue(near)
        self.assertEqual("de", region)  # default for a non-foreign-desk source

    def test_interessen_is_not_a_german_hit(self):
        region, near = scoring.classify_region("streit um interessen und adressen", "tagesschau_ausland")
        self.assertEqual(("world", False), (region, near))

    def test_score_text_exposes_state(self):
        self.assertEqual("HH", score("POL-HH: Einbruch in Wohnung", source="presseportal_blaulicht").state)
        self.assertEqual("BY", score("Sturm ueber Bayern").state)
        self.assertIsNone(score("Gipfeltreffen in Warschau").state)


class AggregationTests(unittest.TestCase):
    def test_duplicates_count_once(self):
        items = [
            {"title": "Explosion in Chemiewerk bei Köln", "score": 20, "source": "a"},
            {"title": "Explosion im Chemiewerk bei Köln", "score": 20, "source": "a"},
            {"title": "Explosion in Chemiewerk bei Köln", "score": 20, "source": "a"},
        ]
        self.assertEqual(20.0, scoring.aggregate_risk(items))

    def test_corroboration_bonus_is_bounded(self):
        base = {"title": "Explosion in Chemiewerk bei Köln", "score": 20}
        two = [dict(base, source="s1"), dict(base, source="s2")]
        many = [dict(base, source=f"s{i}") for i in range(10)]
        self.assertAlmostEqual(23.0, scoring.aggregate_risk(two))
        self.assertAlmostEqual(20 * 1.45, scoring.aggregate_risk(many))

    def test_decay_halves_after_half_life(self):
        now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        items = [{"title": "Alt", "score": 20, "source": "a",
                  "published_dt": now - timedelta(hours=12)}]
        self.assertAlmostEqual(10.0, scoring.aggregate_risk(items, now))

    def test_distinct_stories_add_up(self):
        items = [
            {"title": "Explosion in Chemiewerk", "score": 20, "source": "a"},
            {"title": "Hochwasser an der Elbe steigt", "score": 10, "source": "b"},
        ]
        self.assertEqual(30.0, scoring.aggregate_risk(items))


class BaselineTests(unittest.TestCase):
    def test_too_few_samples(self):
        self.assertIsNone(scoring.baseline_deviation(50, [10, 11, 12]))

    def test_spike_is_flagged(self):
        history = [10, 12, 11, 9, 10, 13, 11, 10, 12, 11, 10, 9, 11]
        result = scoring.baseline_deviation(40, history)
        self.assertEqual("deutlich über Normalniveau", result["label"])

    def test_normal_level(self):
        history = [30, 32, 31, 29, 30, 33, 31, 30, 32, 31, 30, 29, 31]
        self.assertEqual("im Normalbereich", scoring.baseline_deviation(31, history)["label"])

    def test_constant_history_does_not_explode(self):
        result = scoring.baseline_deviation(12, [10] * 20)
        self.assertLess(abs(result["z"]), 5)


if __name__ == "__main__":
    unittest.main()
