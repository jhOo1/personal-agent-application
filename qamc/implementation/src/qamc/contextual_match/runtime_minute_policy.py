"""Explicit user-authorized 60-second pacing override, isolated from old code.

No request, model setting, sampling unit, score or retry policy is changed.
The underlying SQL wait and shared monotonic wait must use the same duration.
"""
from qamc.transport_helpers import atomic_json


class MinuteControl:
    def __init__(self, underlying, gate):
        if gate.duration != 60:
            raise ValueError('Explicit 60-second shared policy required')
        self.underlying, self.gate = underlying, gate

    def __getattr__(self, name):
        return getattr(self.underlying, name)

    def wait(self, stopped=lambda: False):
        while True:
            self.gate.wait_ready(stopped)
            self.underlying.wait(stopped)
            if self.gate.reserve_if_ready(stopped):
                return

    def cooldown(self):
        # Do not call the legacy SQL method: it hardcodes 300 seconds.
        with self.gate.lock, self.underlying.lock:
            self.underlying.db.execute('UPDATE dispatch SET cooldown_until=MAX(cooldown_until,?) WHERE id=1',
                                      (self.underlying.clock()+60,))
            self.underlying.db.commit()
            self.gate.cooldown_locked()

    def stop(self, reason):
        with self.gate.lock:
            self.underlying.stop(reason)
            self.gate.hard = reason
            self.gate._save()

    def close(self):
        self.underlying.close()


def activate(gate, latest_failure_end=0):
    """Preserve count, spacing and hard stops; recompute only the approved wait."""
    with gate.lock:
        before = {'duration':gate.duration, 'reservations':gate.reservations,
                  'hard_stop':gate.hard, 'until':gate.until, 'next':gate.next}
        gate.duration = 60
        gate.until = gate.mono()+max(0, latest_failure_end+60-gate.wall())
        gate._save()
        return before
