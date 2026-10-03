"""Unit tests for lage_monitor.fetchcache (no Home Assistant needed)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
pkg = sys.modules.get("lm") or types.ModuleType("lm")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["lm"] = pkg

from lm.fetchcache import (  # noqa: E402
    NotModified,
    ResilientCache,
    SourcePolicy,
    STATE_CACHED,
    STATE_ERROR,
    STATE_FRESH,
    STATE_NOT_MODIFIED,
    STATE_STALE,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Source:
    """Scriptable fake source that records how often it was called."""

    def __init__(self) -> None:
        self.calls = 0
        self.seen_validators: list[tuple] = []
        self.mode = "ok"
        self.value = ["a"]

    async def __call__(self, etag, last_modified):
        self.calls += 1
        self.seen_validators.append((etag, last_modified))
        if self.mode == "fail":
            raise TimeoutError("boom")
        if self.mode == "304":
            raise NotModified
        return list(self.value), "etag-1", "Wed, 01 Oct 2026 10:00:00 GMT"


def run(coro):
    return asyncio.run(coro)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = ResilientCache(self.clock)
        self.src = Source()
        self.policy = SourcePolicy(min_interval=300, max_stale=3600, backoff_base=60, backoff_max=600)

    def get(self):
        return run(self.cache.get("k", self.src, self.policy))

    def test_first_fetch_is_fresh(self):
        result = self.get()
        self.assertEqual(STATE_FRESH, result.state)
        self.assertEqual(["a"], result.value)
        self.assertTrue(result.ok)

    def test_min_interval_avoids_second_request(self):
        self.get()
        self.clock.advance(100)
        result = self.get()
        self.assertEqual(STATE_CACHED, result.state)
        self.assertEqual(1, self.src.calls)

    def test_sends_validators_and_handles_304(self):
        self.get()
        self.clock.advance(400)
        self.src.mode = "304"
        result = self.get()
        self.assertEqual(STATE_NOT_MODIFIED, result.state)
        self.assertEqual(["a"], result.value)
        self.assertEqual(("etag-1", "Wed, 01 Oct 2026 10:00:00 GMT"), self.src.seen_validators[-1])
        self.assertTrue(result.ok)

    def test_failure_serves_stale_value_and_is_not_ok(self):
        self.get()
        self.clock.advance(400)
        self.src.mode = "fail"
        result = self.get()
        self.assertEqual(STATE_STALE, result.state)
        self.assertEqual(["a"], result.value)
        self.assertFalse(result.ok)
        self.assertIn("TimeoutError", result.error)
        self.assertEqual(1, result.failures)

    def test_failure_without_cache_is_error_not_empty_ok(self):
        self.src.mode = "fail"
        result = self.get()
        self.assertEqual(STATE_ERROR, result.state)
        self.assertIsNone(result.value)
        self.assertFalse(result.ok)

    def test_stale_expires_after_max_stale(self):
        self.get()
        self.src.mode = "fail"
        self.clock.advance(400)
        self.get()  # first failure
        self.clock.advance(4000)  # beyond max_stale and beyond backoff
        result = self.get()
        self.assertEqual(STATE_ERROR, result.state)

    def test_backoff_skips_requests_and_grows(self):
        self.get()
        self.src.mode = "fail"
        self.clock.advance(400)
        self.get()  # call 2 fails -> next retry in 60s
        calls = self.src.calls
        self.clock.advance(30)
        self.get()
        self.assertEqual(calls, self.src.calls, "must not retry during backoff")
        self.clock.advance(40)  # 70s since failure -> retry allowed
        self.get()  # fails again -> delay 120s
        self.assertEqual(calls + 1, self.src.calls)
        self.clock.advance(100)
        self.get()
        self.assertEqual(calls + 1, self.src.calls, "second backoff is longer")

    def test_backoff_is_capped(self):
        self.get()
        self.src.mode = "fail"
        self.clock.advance(400)
        for _ in range(10):
            self.get()
            self.clock.advance(601)
        self.assertLessEqual(self.cache._failures["k"].next_try - self.clock.now, 600)

    def test_recovery_resets_failures(self):
        self.get()
        self.src.mode = "fail"
        self.clock.advance(400)
        self.get()
        self.clock.advance(100)
        self.src.mode = "ok"
        self.src.value = ["b"]
        result = self.get()
        self.assertEqual(STATE_FRESH, result.state)
        self.assertEqual(["b"], result.value)
        self.assertEqual(0, self.cache.failure_count("k"))

    def test_prune_removes_unneeded_keys(self):
        run(self.cache.get("warn:1", self.src, self.policy))
        run(self.cache.get("warn:2", self.src, self.policy))
        self.cache.prune({"warn:2"}, prefix="warn:")
        self.assertNotIn("warn:1", self.cache._entries)
        self.assertIn("warn:2", self.cache._entries)

    def test_keys_are_independent(self):
        bad = Source()
        bad.mode = "fail"
        run(self.cache.get("bad", bad, self.policy))
        result = run(self.cache.get("good", self.src, self.policy))
        self.assertEqual(STATE_FRESH, result.state)

    def test_status_dict_keeps_legacy_keys(self):
        status = self.get().status(items=3)
        for key in ("ok", "items", "error"):
            self.assertIn(key, status)
        self.assertEqual(3, status["items"])


if __name__ == "__main__":
    unittest.main()
