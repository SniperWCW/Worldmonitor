"""Resilience tests for the coordinator, using minimal Home Assistant stubs.

These run without Home Assistant. They exercise the real coordinator code
paths (feed fetch, stale fallback, update-failure handling) against fakes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"


def _install_stubs() -> None:
    def mod(name: str, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module
        return module

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.data = None

        def __class_getitem__(cls, item):
            return cls

    class Store:
        def __init__(self, *a, **k):
            pass

        async def async_load(self):
            return None

        async def async_save(self, data):
            return None

    dt_util = types.SimpleNamespace(
        now=lambda: datetime.now(timezone.utc),
        as_local=lambda d: d,
        as_utc=lambda d: d.astimezone(timezone.utc),
        parse_datetime=lambda v: None,
        utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
    )
    mod("homeassistant")
    mod("homeassistant.config_entries", ConfigEntry=object)
    mod("homeassistant.core", HomeAssistant=object)
    mod("homeassistant.helpers")
    mod("homeassistant.helpers.storage", Store=Store)
    mod(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=DataUpdateCoordinator,
        UpdateFailed=UpdateFailed,
    )
    mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: None)
    mod("homeassistant.util", dt=dt_util)
    sys.modules["homeassistant.util"].dt = dt_util
    mod("aiohttp", ClientTimeout=lambda total=None: ("timeout", total))


_install_stubs()
pkg = types.ModuleType("lmc")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["lmc"] = pkg

from lmc import coordinator as coord_mod  # noqa: E402
from lmc.feed import FeedItem  # noqa: E402
from lmc.fetchcache import NotModified  # noqa: E402

UpdateFailed = sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed


class FakeEntry:
    entry_id = "test"
    options: dict = {}
    data: dict = {"scan_interval": 300}


def make_coordinator():
    return coord_mod.LageMonitorCoordinator(object(), FakeEntry())


class FeedFallbackTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()
        self.clock = [1000.0]
        self.coordinator._cache._clock = lambda: self.clock[0]
        self.mode = "ok"
        self.calls = 0
        self.validators = []

        async def fake_fetch_feed(hass, url, source, limit, etag=None, last_modified=None):
            self.calls += 1
            self.validators.append(etag)
            if self.mode == "fail":
                raise TimeoutError("down")
            if self.mode == "304":
                raise NotModified
            return [FeedItem("Explosion in Werk", "http://x", "", "", source)], "e1", None

        self._orig = coord_mod.fetch_feed
        coord_mod.fetch_feed = fake_fetch_feed
        self.addCleanup(lambda: setattr(coord_mod, "fetch_feed", self._orig))

    def fetch(self, source="tagesschau_all"):
        return asyncio.run(self.coordinator._safe_fetch_feed("http://feed", source, 20))

    def test_outage_serves_stale_items_and_flags_them(self):
        items, status = self.fetch()
        self.assertTrue(status["ok"])
        self.clock[0] += 700
        self.mode = "fail"
        items, status = self.fetch()
        self.assertEqual(1, len(items), "last good items must survive an outage")
        self.assertFalse(status["ok"])
        self.assertTrue(status["stale"])
        self.assertIn("TimeoutError", status["error"])

    def test_failure_without_cache_reports_error_not_ok(self):
        self.mode = "fail"
        items, status = self.fetch()
        self.assertEqual([], items)
        self.assertFalse(status["ok"])
        self.assertEqual("error", status["state"])

    def test_news_feed_not_refetched_within_interval(self):
        self.fetch()
        self.clock[0] += 100
        self.fetch()
        self.assertEqual(1, self.calls)

    def test_police_feed_refetched_sooner_than_news(self):
        self.fetch("presseportal_blaulicht")
        self.clock[0] += 300
        self.fetch("presseportal_blaulicht")
        self.assertEqual(2, self.calls)

    def test_conditional_request_uses_etag(self):
        self.fetch()
        self.clock[0] += 700
        self.mode = "304"
        items, status = self.fetch()
        self.assertEqual("e1", self.validators[-1])
        self.assertTrue(status["ok"])
        self.assertEqual(1, len(items))


class UpdateFailureTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()

    def run_update(self):
        return asyncio.run(self.coordinator._async_update_data())

    def break_build(self):
        async def boom():
            raise ValueError("kaputt")

        self.coordinator._build_snapshot = boom

    def test_first_refresh_failure_raises_update_failed(self):
        self.break_build()
        with self.assertRaises(UpdateFailed):
            self.run_update()

    def test_later_failures_keep_data_flagged_stale_then_go_unavailable(self):
        from dataclasses import dataclass

        @dataclass
        class Snap:
            diagnostics: dict

        self.coordinator.data = Snap(diagnostics={"degraded": False})
        self.break_build()
        first = self.run_update()
        self.assertTrue(first.diagnostics["stale"])
        self.assertEqual(1, first.diagnostics["consecutive_failures"])
        self.assertIn("kaputt", first.diagnostics["last_error"])
        self.coordinator.data = first
        second = self.run_update()
        self.assertEqual(2, second.diagnostics["consecutive_failures"])
        self.assertEqual(first.diagnostics["stale_since"], second.diagnostics["stale_since"])
        self.coordinator.data = second
        with self.assertRaises(UpdateFailed):
            self.run_update()

    def test_recovery_clears_stale_state(self):
        from dataclasses import dataclass

        @dataclass
        class Snap:
            diagnostics: dict

        self.coordinator.data = Snap(diagnostics={"degraded": False})
        self.break_build()
        self.coordinator.data = self.run_update()

        good = Snap(diagnostics={"degraded": False, "stale": False})

        async def ok():
            return good

        self.coordinator._build_snapshot = ok
        result = self.run_update()
        self.assertIs(good, result)
        self.assertEqual(0, self.coordinator._consecutive_failures)
        self.assertIsNone(self.coordinator._stale_since)


if __name__ == "__main__":
    unittest.main()
