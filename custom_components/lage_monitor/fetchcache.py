"""Resilient fetching: min-interval cache, conditional requests, backoff, stale fallback.

Pure Python (no Home Assistant / aiohttp imports) so it can be unit tested.

Why this exists: a failed source must not look like "nothing happened".
Previously a failing feed returned an empty list and was reported as ok, so
the situation score drifted towards "calm" during an outage. Here a failure
returns the last good value (flagged ``stale``) for a bounded time.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")

STATE_FRESH = "fresh"  # downloaded just now
STATE_CACHED = "cached"  # within min_interval, no request made
STATE_NOT_MODIFIED = "not_modified"  # server answered 304
STATE_STALE = "stale"  # request failed / backing off, old value served
STATE_ERROR = "error"  # failed and nothing usable cached


class NotModified(Exception):
    """Raised by a fetch callback when the server answered 304."""


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """How often a source may be queried and how long old data stays usable."""

    min_interval: float = 0.0  # seconds without a new request after success
    max_stale: float = 3 * 3600  # how long a cached value may replace a failure
    backoff_base: float = 60.0  # first retry delay after a failure
    backoff_max: float = 1800.0  # upper bound for the retry delay


@dataclass(slots=True)
class FetchResult(Generic[T]):
    """Outcome of one cached fetch."""

    value: T | None
    state: str
    age: float = 0.0  # seconds since the value was last confirmed fresh
    error: str = ""
    failures: int = 0

    @property
    def ok(self) -> bool:
        """True when the value is current (fresh, cached or not modified)."""
        return self.state in (STATE_FRESH, STATE_CACHED, STATE_NOT_MODIFIED)

    @property
    def stale(self) -> bool:
        return self.state == STATE_STALE

    def status(self, items: int) -> dict[str, Any]:
        """Status dict for the dashboard (keeps the legacy keys)."""
        return {
            "ok": self.ok,
            "items": items,
            "error": self.error,
            "state": self.state,
            "stale": self.stale,
            "age_seconds": int(self.age),
            "failures": self.failures,
        }


@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    etag: str | None
    last_modified: str | None
    confirmed_at: float


@dataclass(slots=True)
class _Failure:
    count: int
    next_try: float
    error: str


# fetch(etag, last_modified) -> (value, etag, last_modified); may raise NotModified
Fetcher = Callable[[str | None, str | None], Awaitable[tuple[T, str | None, str | None]]]


class ResilientCache:
    """Keyed cache with min-interval, conditional requests and backoff."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, _Entry[Any]] = {}
        self._failures: dict[str, _Failure] = {}

    def failure_count(self, key: str) -> int:
        failure = self._failures.get(key)
        return failure.count if failure else 0

    def prune(self, valid_keys: set[str], prefix: str = "") -> None:
        """Drop entries under ``prefix`` that are no longer needed."""
        for store in (self._entries, self._failures):
            for key in [k for k in store if k.startswith(prefix) and k not in valid_keys]:
                del store[key]

    async def get(
        self,
        key: str,
        fetch: Fetcher[T],
        policy: SourcePolicy | None = None,
    ) -> FetchResult[T]:
        """Return the value for ``key``, fetching only when allowed and needed."""
        policy = policy or SourcePolicy()
        now = self._clock()
        entry: _Entry[T] | None = self._entries.get(key)
        failure = self._failures.get(key)

        if entry is not None and failure is None:
            age = now - entry.confirmed_at
            if age < policy.min_interval:
                return FetchResult(entry.value, STATE_CACHED, age)

        if failure is not None and now < failure.next_try:
            return self._fallback(entry, failure, policy, now)

        try:
            value, etag, last_modified = await fetch(
                entry.etag if entry else None,
                entry.last_modified if entry else None,
            )
        except NotModified:
            if entry is None:  # server sent 304 without a validator: treat as failure
                return self._register_failure(key, None, "304 ohne Cache", policy, now)
            entry.confirmed_at = now
            self._failures.pop(key, None)
            return FetchResult(entry.value, STATE_NOT_MODIFIED, 0.0)
        except Exception as err:  # noqa: BLE001 - any source error must degrade gracefully
            return self._register_failure(key, entry, _describe(err), policy, now)

        self._entries[key] = _Entry(value, etag, last_modified, now)
        self._failures.pop(key, None)
        return FetchResult(value, STATE_FRESH, 0.0)

    def _register_failure(
        self,
        key: str,
        entry: _Entry[Any] | None,
        error: str,
        policy: SourcePolicy,
        now: float,
    ) -> FetchResult[Any]:
        previous = self._failures.get(key)
        count = (previous.count if previous else 0) + 1
        delay = min(policy.backoff_max, policy.backoff_base * 2 ** (count - 1))
        failure = _Failure(count, now + delay, error)
        self._failures[key] = failure
        return self._fallback(entry, failure, policy, now)

    @staticmethod
    def _fallback(
        entry: _Entry[Any] | None,
        failure: _Failure,
        policy: SourcePolicy,
        now: float,
    ) -> FetchResult[Any]:
        if entry is not None:
            age = now - entry.confirmed_at
            if age <= policy.max_stale:
                return FetchResult(entry.value, STATE_STALE, age, failure.error, failure.count)
        return FetchResult(None, STATE_ERROR, 0.0, failure.error, failure.count)


def _describe(err: Exception) -> str:
    text = str(err).strip()
    return f"{type(err).__name__}: {text}" if text else type(err).__name__
