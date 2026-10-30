"""Tests for alert event detection."""

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

from lm import alerting  # noqa: E402


def run(state, now=0.0, status="good", score=80, alerts=(), layers=(), drop=15, cooldown=3600.0, route_delay=0):
    return alerting.detect(
        state,
        now=now,
        status=status,
        score=score,
        local_alerts=list(alerts),
        layer_items=list(layers),
        drop_threshold=drop,
        cooldown_s=cooldown,
        route_delay_min=route_delay,
    )


class AlertingTests(unittest.TestCase):
    def test_first_snapshot_only_seeds(self):
        state = alerting.AlertState()
        events = run(state, status="bad", score=10, alerts=[{"source": "mowas", "title": "x"}])
        self.assertEqual([], events)
        self.assertTrue(state.seeded)

    def test_status_change_both_directions(self):
        state = alerting.AlertState()
        run(state, status="good", score=80)
        worse = run(state, now=10, status="bad", score=30, drop=0)
        self.assertEqual(["status_change"], [e["type"] for e in worse])
        self.assertEqual("worse", worse[0]["direction"])
        better = run(state, now=20, status="good", score=80, drop=0)
        self.assertEqual("better", better[0]["direction"])

    def test_score_drop(self):
        state = alerting.AlertState()
        run(state, status="good", score=90)
        events = run(state, now=10, status="good", score=72, drop=15)
        self.assertEqual(["score_drop"], [e["type"] for e in events])
        self.assertEqual([], run(state, now=20, status="good", score=70, drop=15))  # only 2 points

    def test_drop_disabled(self):
        state = alerting.AlertState()
        run(state, score=90)
        self.assertEqual([], run(state, now=1, score=10, drop=0))

    def test_new_official_alert_fires_once(self):
        state = alerting.AlertState()
        run(state)
        alert = {"source": "mowas", "identifier": "id-1", "title": "Gefahr"}
        first = run(state, now=1, alerts=[alert])
        self.assertEqual(["new_official_alert"], [e["type"] for e in first])
        self.assertEqual([], run(state, now=2, alerts=[alert]))

    def test_flood_only_on_increase(self):
        state = alerting.AlertState()
        run(state)
        item = {"layer": "water", "key": "pegel:1", "title": "Stuttgart", "level": 1}
        self.assertEqual(["flood_level"], [e["type"] for e in run(state, now=1, layers=[item])])
        self.assertEqual([], run(state, now=2, layers=[item]))
        item2 = {**item, "level": 2}
        events = run(state, now=3, layers=[item2])
        self.assertEqual(2, events[0]["level"])

    def test_radiation_once_per_station(self):
        state = alerting.AlertState()
        run(state)
        item = {"layer": "radiation", "key": "odl:1", "title": "Mess", "value": 0.5}
        self.assertEqual(1, len(run(state, now=1, layers=[item])))
        self.assertEqual([], run(state, now=2, layers=[item]))

    def test_route_delay_fires_once_for_new_jams_on_my_route(self):
        state = alerting.AlertState()
        run(state, route_delay=15)
        jam = {"layer": "road", "kind": "warning", "key": "warning:1", "title": "A81 | X", "on_route": True, "delay_min": 20, "road": "A81"}
        small = {**jam, "key": "warning:2", "delay_min": 5}
        elsewhere = {**jam, "key": "warning:3", "on_route": False}
        events = run(state, now=1, layers=[jam, small, elsewhere], route_delay=15)
        self.assertEqual(["route_delay"], [e["type"] for e in events])
        self.assertEqual(20, events[0]["delay_min"])
        self.assertEqual([], run(state, now=2, layers=[jam], route_delay=15))
        self.assertEqual([], run(state, now=3, layers=[{**jam, "key": "warning:9"}], route_delay=0))  # disabled

    def test_cooldown_suppresses_flapping(self):
        state = alerting.AlertState()
        run(state, status="good", score=80)
        self.assertEqual(1, len(run(state, now=10, status="bad", score=30, drop=0)))
        run(state, now=20, status="good", score=80, drop=0)
        self.assertEqual([], run(state, now=30, status="bad", score=30, drop=0))  # inside cooldown
        run(state, now=40, status="good", score=80, drop=0)
        self.assertEqual(1, len(run(state, now=4000, status="bad", score=30, drop=0)))  # after cooldown


if __name__ == "__main__":
    unittest.main()
