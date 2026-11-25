"""Shared monotonic cooldown and spacing for the new review window only."""
import json
from pathlib import Path
import threading
import time
from qamc.transport_helpers import atomic_json
from proposals.qamc_protocol_alignment.transport import SamplingTransportError


class SharedGate:
    def __init__(self,path,spacing=3.1,cooldown=301,mono=None,wall=None,sleep=None):
        if spacing<3.1 or cooldown<300:raise ValueError('Pacing cannot be weakened')
        self.path=Path(path);self.spacing=spacing;self.duration=cooldown
        self.mono=mono or time.monotonic;self.wall=wall or time.time;self.sleep=sleep or time.sleep
        self.lock=threading.RLock();now=self.mono();self.next=now;self.until=now;self.hard=None;self.reservations=0
        if self.path.exists():
            value=json.loads(self.path.read_text());self.hard=value['hard_stop'];self.reservations=value['reservations']
            # Preserve elapsed-time waits across same-boot process restarts,
            # even if wall time advanced. A reset clock does not create a
            # many-day wait: fall back conservatively to one full cooldown.
            remaining=value['cooldown_until_mono']-now
            if remaining>self.duration+5:remaining=self.duration
            self.until=now+max(0,remaining,value['cooldown_until_utc']-self.wall())
            self.next=now+max(0,min(self.spacing,value['next_at_utc']-self.wall()))

    def _save(self):
        now=self.mono();wall=self.wall()
        atomic_json(self.path,{'cooldown_until_mono':self.until,
            'cooldown_until_utc':wall+max(0,self.until-now),'next_at_utc':wall+max(0,self.next-now),
            'hard_stop':self.hard,'reservations':self.reservations,'cooldown_seconds':self.duration,
            'spacing_seconds':self.spacing,'updated_utc':wall})

    def _check(self,stopped):
        if stopped():raise SamplingTransportError('operator_stop_no_dispatch')
        if self.hard:raise SamplingTransportError('retained_quota_or_auth_stop_no_dispatch')

    def wait_ready(self,stopped=lambda:False):
        while True:
            with self.lock:
                self._check(stopped);delay=max(self.next,self.until)-self.mono()
                if delay<=0:return
            self.sleep(min(.25,delay))

    def reserve_if_ready(self,stopped=lambda:False):
        with self.lock:
            self._check(stopped);now=self.mono()
            if now<max(self.next,self.until):return False
            self.next=now+self.spacing;self.reservations+=1;self._save();return True

    def cooldown_locked(self):
        self.until=max(self.until,self.mono()+self.duration);self._save()


class PacedControl:
    """Keep the sampler's SQL control and add a shared elapsed-time floor."""
    def __init__(self,underlying,gate):self.underlying,self.gate=underlying,gate
    def __getattr__(self,name):return getattr(self.underlying,name)
    def wait(self,stopped=lambda:False):
        while True:
            self.gate.wait_ready(stopped);self.underlying.wait(stopped)
            if self.gate.reserve_if_ready(stopped):return
    def cooldown(self):
        with self.gate.lock:
            self.underlying.cooldown()
            self.gate.cooldown_locked()
    def stop(self,reason):
        with self.gate.lock:
            self.underlying.stop(reason);self.gate.hard=reason;self.gate._save()
    def close(self):self.underlying.close()
