"""Geo integration tests for the coordinator (Home Assistant stubbed)."""

from __future__ import annotations

import unittest

try:  # `unittest discover -s tests` imports modules top-level
    import test_coordinator_resilience as base
except ImportError:  # `python -m unittest tests.test_coordinator_geo`
    from tests import test_coordinator_resilience as base


def usgs(mag, lat, lon, place="Test"):
    return {
        "features": [
            {
                "properties": {"mag": mag, "place": place, "title": f"M {mag} - {place}", "time": 1_790_000_000_000},
                "geometry": {"coordinates": [lon, lat, 10]},
            }
        ]
    }


class CoordinatorGeoTests(unittest.TestCase):
    def setUp(self):
        self.c = base.make_coordinator()
        self.none = (None, None)

    def resolve(self, title, summary=""):
        item = {"title": title, "summary": summary}
        return self.c._resolve_news_coordinates(item, [], self.none)

    def test_is_in_germany_uses_polygon_not_bbox(self):
        self.assertTrue(self.c._is_in_germany(50.775, 6.084))  # Aachen
        for lat, lon in ((47.559, 7.588), (47.809, 13.055), (50.075, 14.438), (53.428, 14.553)):
            self.assertFalse(self.c._is_in_germany(lat, lon))

    def test_no_false_marker_for_interessen(self):
        self.assertEqual((None, None, ""), self.resolve("Streit um Interessen", "Es geht um Adressen."))

    def test_marker_for_city_in_title(self):
        lat, lon, label = self.resolve("Brand in Essen: zwei Verletzte")
        self.assertAlmostEqual(51.456, lat, places=2)
        self.assertEqual("News mit Ortsbezug", label)

    def test_marker_from_dienststelle_and_dateline(self):
        lat, _lon, _ = self.resolve("POL-HH: Zeugen gesucht", "Es kam zu einem Unfall.")
        self.assertAlmostEqual(53.551, lat, places=2)
        lat, _lon, _ = self.resolve("POL-DO: Unfall auf der A45", "Siegen (ots) - Am Montag ...")
        self.assertAlmostEqual(50.875, lat, places=2)  # dateline beats the Dienststelle city

    def test_state_fallback_is_labelled_approximate(self):
        _lat, _lon, label = self.resolve("POL-WES: Raub", "Unbekannte flüchteten.")
        self.assertEqual("Bundesland (ungefähr)", label)

    def test_direct_coordinates_still_win(self):
        item = {"title": "Brand in Essen", "latitude": 1.0, "longitude": 2.0, "severity": "M4.0"}
        self.assertEqual((1.0, 2.0, "M4.0"), self.c._resolve_news_coordinates(item, [], self.none))

    def test_usgs_neighbourhood_quake_is_included_as_world(self):
        items = self.c._normalize_usgs_items(usgs(3.6, 52.41, 16.93), self.none, 100)  # near Posen
        self.assertEqual(1, len(items))
        self.assertEqual("world", items[0]["region"])

    def test_usgs_small_quake_far_away_is_ignored(self):
        self.assertEqual([], self.c._normalize_usgs_items(usgs(3.6, 35.7, 139.7), self.none, 100))
        self.assertEqual([], self.c._normalize_usgs_items(usgs(3.0, 52.41, 16.93), self.none, 100))

    def test_usgs_german_quake_is_de(self):
        items = self.c._normalize_usgs_items(usgs(3.0, 50.775, 6.084), self.none, 100)
        self.assertEqual("de", items[0]["region"])

    def test_basel_quake_is_not_german_any_more(self):
        items = self.c._normalize_usgs_items(usgs(4.0, 47.559, 7.588), self.none, 100)
        self.assertEqual("world", items[0]["region"])

    def test_score_item_exposes_state(self):
        from lmc.feed import FeedItem

        scored = self.c._score_item(FeedItem("POL-HH: Einbruch in Wohnung", "http://x", "", "", "presseportal_blaulicht"))
        self.assertEqual("HH", scored["state"])
        scored = self.c._score_item(FeedItem("Sturm über Bayern", "http://x", "", "", "tagesschau_all"))
        self.assertEqual("BY", scored["state"])


if __name__ == "__main__":
    unittest.main()
