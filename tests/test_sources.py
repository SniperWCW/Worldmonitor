"""Tests for the Autobahn, PEGELONLINE and BfS source parsers."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
if "lm" not in sys.modules:
    pkg = types.ModuleType("lm")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["lm"] = pkg

from lm.sources import autobahn, bfs, pegel  # noqa: E402


class AutobahnTests(unittest.TestCase):
    def test_parse_roads_validates_dedupes_and_caps(self):
        self.assertEqual(["A8", "A81"], autobahn.parse_roads("a8, A81 ; A8"))
        self.assertEqual([], autobahn.parse_roads("B27, ../etc, A"))
        self.assertEqual(autobahn.MAX_ROADS, len(autobahn.parse_roads(",".join(f"A{i}" for i in range(1, 30)))))

    def test_road_url_rejects_bad_input(self):
        self.assertTrue(autobahn.road_url("A8", "webcam").endswith("/A8/services/webcam"))
        with self.assertRaises(ValueError):
            autobahn.road_url("A8/../x", "webcam")
        with self.assertRaises(ValueError):
            autobahn.road_url("A8", "other")

    def test_webcams_need_coordinates_and_image(self):
        payload = {
            "webcam": [
                {
                    "identifier": "abc",
                    "title": "A8 | Leonberg",
                    "subtitle": "Blickrichtung Stuttgart",
                    "coordinate": {"lat": "48.80", "long": "9.01"},
                    "imageurl": "https://example.org/cam.jpg",
                    "linkurl": "javascript:alert(1)",
                },
                {"identifier": "no-image", "coordinate": {"lat": "48.8", "long": "9.0"}},
                {"identifier": "no-coord", "imageurl": "https://example.org/x.jpg"},
            ]
        }
        items = autobahn.normalize_webcams(payload, "A8")
        self.assertEqual(1, len(items))
        self.assertEqual("webcams", items[0]["layer"])
        self.assertEqual("", items[0]["link"])  # javascript: link dropped
        self.assertAlmostEqual(48.80, items[0]["latitude"])

    def test_closures_are_serious_and_future_ones_informational(self):
        payload = {
            "closure": [
                {"identifier": "1", "title": "A8 | Sperrung", "coordinate": {"lat": 48.8, "long": 9.0}},
                {"identifier": "2", "title": "A8 | später", "future": True, "coordinate": {"lat": 48.8, "long": 9.1}},
            ]
        }
        items = autobahn.normalize_traffic(payload, "A8", "closure")
        self.assertEqual([2, 0], [i["severity"] for i in items])

    def test_wrapper_key_may_vary(self):
        payload = {"unexpected": [{"identifier": "1", "coordinate": {"lat": 1, "long": 2}, "title": "t"}]}
        self.assertEqual(1, len(autobahn.normalize_traffic(payload, "A1", "warning")))

    def test_garbage_payload(self):
        self.assertEqual([], autobahn.normalize_webcams(None, "A8"))
        self.assertEqual([], autobahn.normalize_traffic("x", "A8", "warning"))


def station(value, marks, uuid="u1", unit="cm"):
    return {
        "uuid": uuid,
        "longname": "STUTTGART",
        "latitude": 48.78,
        "longitude": 9.18,
        "water": {"longname": "NECKAR"},
        "timeseries": [
            {
                "shortname": "W",
                "unit": unit,
                "currentMeasurement": {"timestamp": "2026-10-30T12:00:00+01:00", "value": value, "trend": 1},
                "characteristicValues": [{"shortname": k, "value": v} for k, v in marks.items()],
            }
        ],
    }


class PegelTests(unittest.TestCase):
    MARKS = {"M_I": 300, "M_II": 400, "M_III": 500}

    def test_flood_level(self):
        marks = {"m_i": 300, "m_ii": 400, "m_iii": 500}
        self.assertEqual(0, pegel.flood_level(299, marks))
        self.assertEqual(1, pegel.flood_level(300, marks))
        self.assertEqual(3, pegel.flood_level(900, marks))
        self.assertEqual(0, pegel.flood_level(900, {}))

    def test_only_stations_above_a_mark_are_reported(self):
        payload = [station(250, self.MARKS, "low"), station(420, self.MARKS, "high")]
        items = pegel.normalize_stations(payload)
        self.assertEqual(1, len(items))
        self.assertEqual(2, items[0]["level"])
        self.assertEqual(2, items[0]["severity"])
        self.assertIn("Meldestufe 2", items[0]["detail"])

    def test_stations_without_marks_are_skipped(self):
        self.assertEqual([], pegel.normalize_stations([station(900, {})]))

    def test_url_clamps_radius(self):
        self.assertIn("radius=100", pegel.stations_url(48.0, 9.0, 500))
        self.assertIn("radius=10&", pegel.stations_url(48.0, 9.0, 1))


def odl(value, status=1, unit="µSv/h", name="Stuttgart"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [9.18, 48.78]},
        "properties": {"id": "DEZ1", "name": name, "value": value, "unit": unit, "site_status": status, "end_measure": "2026-10-30T11:00:00Z"},
    }


class BfsTests(unittest.TestCase):
    def test_severity_thresholds(self):
        self.assertEqual(0, bfs.severity_for(0.12))
        self.assertEqual(1, bfs.severity_for(0.3))
        self.assertEqual(2, bfs.severity_for(1.0))
        self.assertEqual(3, bfs.severity_for(50))

    def test_only_elevated_working_stations(self):
        payload = {"features": [odl(0.1), odl(0.45, name="Hoch"), odl(5.0, status=2, name="Defekt"), odl(0.9, unit="nSv/h")]}
        items = bfs.normalize_stations(payload)
        self.assertEqual(["Hoch: 0.45 µSv/h"], [i["title"] for i in items])
        self.assertEqual(48.78, items[0]["latitude"])  # GeoJSON order is lon, lat

    def test_garbage(self):
        self.assertEqual([], bfs.normalize_stations({"features": [{"properties": None}]}))


if __name__ == "__main__":
    unittest.main()
