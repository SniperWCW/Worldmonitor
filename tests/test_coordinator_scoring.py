"""Regression tests for regional aggregation and quality metadata."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

try:
    import test_coordinator_resilience as base
except ImportError:
    from tests import test_coordinator_resilience as base


class CoordinatorScoringTests(unittest.TestCase):
    def setUp(self):
        self.c = base.make_coordinator()
        self.now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)

    def item(self, title, score, region, source="news", age_hours=0):
        return {
            "title": title,
            "summary": "",
            "score": score,
            "region": region,
            "source": source,
            "published_dt": self.now - timedelta(hours=age_hours),
            "keywords": [],
            "military_score": 0,
        }

    def test_world_scope_excludes_domestic_items(self):
        items = [
            self.item("Deutsches Ereignis", 90, "de"),
            self.item("Internationales Ereignis", 12, "world"),
        ]
        germany, world = self.c._split_scope_items(items)
        self.assertEqual(["Deutsches Ereignis"], [item["title"] for item in germany])
        self.assertEqual(["Internationales Ereignis"], [item["title"] for item in world])

    def test_official_alert_is_not_double_counted_as_germany_news(self):
        items = [self.item("Warnung", 20, "de", source="mowas")]
        germany, _world = self.c._split_scope_items(items)
        self.assertEqual([], germany)

    def test_duplicate_headlines_do_not_raise_normalized_risk(self):
        single = [self.item("Explosion in Chemiewerk", 20, "world")]
        duplicates = single * 4
        one = self.c._normalize_aggregate_risk(single, self.now, scale=60, cap=100)
        many = self.c._normalize_aggregate_risk(duplicates, self.now, scale=60, cap=100)
        self.assertEqual(one, many)

    def test_old_event_has_less_weight(self):
        fresh = [self.item("Sturm über Region", 20, "world")]
        old = [self.item("Sturm über Region", 20, "world", age_hours=12)]
        self.assertGreater(
            self.c._normalize_aggregate_risk(fresh, self.now, scale=60, cap=100),
            self.c._normalize_aggregate_risk(old, self.now, scale=60, cap=100),
        )

    def test_combined_risks_are_bounded_without_simple_addition(self):
        self.assertEqual(44, self.c._combine_risks(20, 30))
        self.assertEqual(100, self.c._combine_risks(100, 30))

    def test_data_quality_is_separate_metadata(self):
        status = {
            "a": {"ok": True, "stale": False},
            "b": {"ok": False, "stale": True},
        }
        freshness = [
            {"label": "Frisch"},
            {"label": "Cache (veraltet)"},
        ]
        quality = self.c._build_data_quality(
            status,
            freshness,
            [self.item("DE", 10, "de", source="a")],
            [],
            [],
        )
        self.assertEqual(2, quality["total_sources"])
        self.assertEqual(1, quality["healthy_sources"])
        self.assertEqual(1, quality["stale_sources"])
        self.assertLess(quality["score"], 80)

    def test_theme_event_count_uses_clusters_not_duplicate_signals(self):
        items = [
            self.item("Trinkwasser fällt in Musterstadt aus", 16, "de", source="a"),
            self.item("Trinkwasser fällt in Musterstadt aus", 15, "de", source="b"),
        ]
        themes = self.c._build_theme_scores(items, self.now)
        self.assertEqual(1, themes["infrastructure"]["events"])

    def test_status_threshold_matches_frontend_boundary(self):
        summary = self.c._build_local_analysis_summary(67, [], 25, 0)
        self.assertEqual("Aufmerksam", summary["status"]["label"])
        self.assertIn("aufmerksam", summary["headline"])

    def test_structured_items_expose_theme_metadata(self):
        item = self.c._build_structured_item(
            title="Trinkwasserversorgung ausgefallen",
            summary="Störung im Wassernetz",
            source="mowas",
            published="",
            score=12,
            region="de",
            latitude=None,
            longitude=None,
        )
        self.assertIn("infrastructure", item["themes"])

    def test_local_radius_excludes_remote_mowas_even_with_keyword_hit(self):
        remote = {
            "title": "MoWaS-Warnung für Stuttgart und Umgebung",
            "source": "mowas",
            "latitude": 48.603,
            "longitude": 11.625,
        }
        filtered = self.c._filter_alerts_by_radius(
            [remote],
            (48.7758, 9.1829),
            25,
            "local",
            ["Stuttgart"],
        )
        self.assertEqual([], filtered)

    def test_local_radius_keeps_nearby_mowas(self):
        nearby = {
            "title": "MoWaS-Warnung im Stadtgebiet",
            "source": "mowas",
            "latitude": 48.80,
            "longitude": 9.20,
        }
        filtered = self.c._filter_alerts_by_radius(
            [nearby],
            (48.7758, 9.1829),
            25,
            "local",
        )
        self.assertEqual([nearby], filtered)

    def test_alert_text_is_only_fallback_without_coordinates(self):
        unresolved = {
            "title": "Abkochgebot",
            "source": "mowas",
            "affected_regions": "Stuttgart-Mitte",
            "latitude": None,
            "longitude": None,
        }
        filtered = self.c._filter_alerts_by_radius(
            [unresolved],
            (48.7758, 9.1829),
            25,
            "local",
            ["Stuttgart"],
        )
        self.assertEqual([unresolved], filtered)

    def test_local_headlines_do_not_override_remote_coordinates(self):
        remote = {
            "title": "Abkochgebot für Stuttgart",
            "source": "mowas",
            "severity": "Warnung",
            "latitude": 48.603,
            "longitude": 11.625,
        }
        selected = self.c._select_local_alerts_for_headlines(
            [remote],
            ["Stuttgart"],
            (48.7758, 9.1829),
            25,
            "local",
        )
        self.assertEqual([], selected)


if __name__ == "__main__":
    unittest.main()
