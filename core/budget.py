from __future__ import annotations
import threading, time, datetime as dt
from collections import defaultdict, deque


class DailyTokenBudget:
    """In-memory per-instance cap (resets at 00:00 UTC and on restart). It is a guardrail, not billing: also set
    a provider-side spending limit and an AWS budget alarm."""

    def __init__(self, limit: int, clock=time.time):
        self.limit = limit
        self.clock = clock
        self.used = 0
        self.day = self._day()
        self.lock = threading.Lock()


    def _day(self):
        return dt.datetime.fromtimestamp(self.clock(), dt.timezone.utc).date()

    def _roll(self):
        d = self._day()
        if d != self.day:
            self.day, self.used = d, 0

    def can_spend(self) -> bool:
        with self.lock:
            self._roll()
            return self.used < self.limit

    def add(self, usage) -> None:
        with self.lock:
            self._roll()
            self.used += usage.input_tokens + usage.output_tokens


class RateLimiter:
    def __init__(self, per_minute: int, clock=time.time):
        self.per_minute, self.clock, self.hits, self.lock = per_minute, clock, defaultdict(deque), threading.Lock()

    def allow(self, key: str) -> bool:
        with self.lock:
            now, q = self.clock(), self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True
