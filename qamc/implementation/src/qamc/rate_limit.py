"""Shared dispatch pacing and bounded, observable cooldown for known rate limits."""
from __future__ import annotations
import threading
import time


class DispatchStopped(RuntimeError):
    pass


class RateLimitGate:
    def __init__(self, spacing_seconds=2., cooldown_seconds=120., clock=None, sleeper=None):
        self.spacing = spacing_seconds
        self.cooldown = cooldown_seconds
        self.clock = clock or time.monotonic
        self.sleep = sleeper or time.sleep
        self.lock = threading.Lock()
        self.next_dispatch = 0.
        self.cooldown_until = 0.

    def rate_limited(self, retry_after=None):
        delay = self.cooldown
        if retry_after is not None:
            try:
                delay = max(delay, min(300., max(0., float(retry_after))))
            except (ValueError, TypeError):
                pass
        with self.lock:
            self.cooldown_until = max(self.cooldown_until, self.clock() + delay)
        return delay

    def wait_turn(self, stopped=lambda: False):
        # Sleep in short pieces so an operator/credential stop remains effective.
        while True:
            if stopped():
                raise DispatchStopped('operator_or_quota_stop_no_dispatch')
            with self.lock:
                now = self.clock()
                wait = max(self.next_dispatch, self.cooldown_until) - now
                if wait <= 0:
                    self.next_dispatch = now + self.spacing
                    return
            self.sleep(min(wait, 1.))
