"""Minimal, polite HTTP client built on the standard library.

Safeguards learned from the earlier project:
  * a wall-clock budget, because a slow but succeeding source can otherwise
    consume a whole Colab session without ever failing;
  * a consecutive-failure circuit breaker;
  * Retry-After is honoured for 429 and 503;
  * no failure is silent: every give-up raises SourceUnavailable with a reason.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional


class SourceUnavailable(RuntimeError):
    """Raised when a source cannot be used for this run."""


class PoliteClient:
    def __init__(self, user_agent: str, timeout: float = 60.0,
                 min_interval: float = 0.0, max_consecutive_failures: int = 5,
                 time_budget_seconds: float = 3600.0, headers: Optional[Dict[str, str]] = None,
                 opener=None):
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_failures = max_consecutive_failures
        self.budget = time_budget_seconds
        self.headers = dict(headers or {})
        self._opener = opener or urllib.request.urlopen  # injectable for tests
        self._started = time.monotonic()
        self._last_request = 0.0
        self._failures = 0

    def _wait_turn(self) -> None:
        gap = time.monotonic() - self._last_request
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)

    def _check_budget(self) -> None:
        if time.monotonic() - self._started > self.budget:
            raise SourceUnavailable("time budget exhausted for this run")

    def get(self, url: str, params: Optional[Dict[str, str]] = None,
            accept: str = "*/*") -> bytes:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        while True:
            self._check_budget()
            self._wait_turn()
            req = urllib.request.Request(url, headers={
                "User-Agent": self.user_agent, "Accept": accept, **self.headers})
            self._last_request = time.monotonic()
            try:
                with self._opener(req, timeout=self.timeout) as resp:
                    body = resp.read()
                self._failures = 0
                return body
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 503):
                    wait = _retry_after(exc, default=30.0)
                    self._fail(f"HTTP {exc.code}; waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue
                if 400 <= exc.code < 500:
                    raise SourceUnavailable(f"HTTP {exc.code} for {url}") from exc
                self._fail(f"HTTP {exc.code}")
                time.sleep(min(60, 2 ** self._failures))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self._fail(f"{type(exc).__name__}: {exc}")
                time.sleep(min(60, 2 ** self._failures))

    def get_json(self, url: str, params: Optional[Dict[str, str]] = None) -> dict:
        return json.loads(self.get(url, params, accept="application/json").decode("utf-8"))

    def _fail(self, reason: str) -> None:
        self._failures += 1
        print(f"[http] failure {self._failures}/{self.max_failures}: {reason}")
        if self._failures >= self.max_failures:
            raise SourceUnavailable(f"circuit breaker tripped after {self._failures} failures: {reason}")


def _retry_after(exc: urllib.error.HTTPError, default: float) -> float:
    try:
        value = exc.headers.get("Retry-After") if exc.headers else None
        return max(1.0, float(value)) if value else default
    except (TypeError, ValueError):
        return default
