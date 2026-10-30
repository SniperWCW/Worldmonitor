"""Tests for the optional map layer orchestration."""

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

import asyncio  # noqa: E402

from lm import layers  # noqa: E402
from lm.fetchcache import STATE_ERROR, STATE_FRESH, FetchResult  # noqa: E402

HOME = (48.78, 9.18)


def cam(identifier, lat, lon):
    return {"identifier": identifier, "title": identifier, "coordinate": {"lat": str(lat), "long": str(lon)}, "imageurl": "https://example.org/i.jpg"}


class FakeFetch:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.timeouts = {}

    async def __call__(self, key, url, min_interval, max_stale, timeout=None):
        self.calls.append(key)
        self.timeouts[key] = timeout
        value = self.responses.get(key)
        if value is None:
            return FetchResult(None, STATE_ERROR, error="down", failures=1)
        return FetchResult(value, STATE_FRESH)


class LayerTests(unittest.TestCase):
    def test_disabled_does_nothing(self):
        fetch = FakeFetch({})
        items, status = asyncio.run(layers.fetch_layers(layers.LayerConfig(), HOME, 50, fetch))
        self.assertEqual(([], {}), (items, status))
        self.assertEqual([], fetch.calls)

    def test_autobahn_filters_by_radius_and_reports_status(self):
        fetch = FakeFetch(
            {
                "layer:autobahn:A8:webcam": {"webcam": [cam("near", 48.80, 9.20), cam("far", 53.5, 10.0)]},
                "layer:autobahn:A8:closure": {"closure": []},
                # warning request fails
            }
        )
        cfg = layers.LayerConfig(autobahn_roads=("A8",))
        items, status = asyncio.run(layers.fetch_layers(cfg, HOME, 50, fetch))
        self.assertEqual(["webcam:near"], [i["key"] for i in items])
        self.assertIn("distance_km", items[0])
        self.assertFalse(status["autobahn"]["ok"])  # one of three requests failed
        self.assertIn("down", status["autobahn"]["error"])
        self.assertEqual(3, len(fetch.calls))

    def test_traffic_is_deduplicated_and_future_works_dropped(self):
        def closure(identifier, title, lat, future=False):
            return {"identifier": identifier, "title": title, "future": future, "coordinate": {"lat": str(lat), "long": "9.0"}}

        fetch = FakeFetch(
            {
                "layer:autobahn:A81:webcam": {"webcam": []},
                "layer:autobahn:A81:closure": {
                    "closure": [
                        closure("1", "DEGES Ausbau", 48.70),
                        closure("2", "DEGES Ausbau", 48.71),  # same measure, other ramp
                        closure("3", "Sperrung Tunnel", 48.80),
                        closure("4", "Nächste Woche", 48.79, future=True),
                    ]
                },
                "layer:autobahn:A81:warning": {"warning": []},
            }
        )
        cfg = layers.LayerConfig(autobahn_roads=("A81",))
        items, _ = asyncio.run(layers.fetch_layers(cfg, HOME, 50, fetch))
        self.assertEqual(["Sperrung Tunnel", "DEGES Ausbau"], [i["title"] for i in items])

    def test_radiation_uses_long_timeout_and_wide_radius(self):
        def station(sid, lon, lat):
            return {
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"id": sid, "name": sid, "value": 0.6, "unit": "µSv/h", "site_status": 1},
            }

        # ~60 km from Stuttgart (inside 100 km) and ~400 km away (outside)
        payload = {"features": [station("nah", 9.2, 49.3), station("fern", 13.4, 52.5)]}
        fetch = FakeFetch({"layer:odl": payload})
        items, _ = asyncio.run(layers.fetch_layers(layers.LayerConfig(radiation=True), HOME, 25, fetch))
        self.assertEqual(["odl:nah"], [i["key"] for i in items])
        self.assertEqual(60, fetch.timeouts["layer:odl"])

    def test_one_failing_layer_does_not_break_others(self):
        odl = {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [9.2, 48.8]},
                    "properties": {"id": "x", "name": "Hoch", "value": 0.6, "unit": "µSv/h", "site_status": 1},
                }
            ]
        }
        fetch = FakeFetch({"layer:odl": odl})
        cfg = layers.LayerConfig(water=True, radiation=True)
        items, status = asyncio.run(layers.fetch_layers(cfg, HOME, 50, fetch))
        self.assertEqual(["radiation"], [i["layer"] for i in items])
        self.assertFalse(status["pegelonline"]["ok"])
        self.assertTrue(status["bfs_odl"]["ok"])

    def test_water_needs_home(self):
        fetch = FakeFetch({})
        items, status = asyncio.run(layers.fetch_layers(layers.LayerConfig(water=True), (None, None), 50, fetch))
        self.assertEqual([], items)
        self.assertEqual([], fetch.calls)
        self.assertIn("Home", status["pegelonline"]["error"])


if __name__ == "__main__":
    unittest.main()
