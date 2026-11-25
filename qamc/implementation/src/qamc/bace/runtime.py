"""Durable step identities and a bounded gateway using the existing transport."""
import fcntl
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from qamc.b7_api import Gateway, CallError
from qamc.common import sha, canonical
from qamc.rate_limit import RateLimitGate


@contextmanager
def runner_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


class Steps:
    """Persist STARTED before doing any work; crash recovery never resends it.

    A retained incomplete step needs an explicit reconciliation, not a new key.
    Failed/unknown steps are reliability outcomes and have no semantic score.
    """
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(self.path,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS steps (key TEXT PRIMARY KEY, input_hash TEXT NOT NULL, status TEXT NOT NULL, result TEXT, error TEXT)')
        self.db.commit()

    def run(self,key,input_value,make):
        digest=sha(input_value)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT input_hash,status,result,error FROM steps WHERE key=?',(key,)).fetchone()
            if row:
                self.db.commit()
                if row[0]!=digest:raise ValueError('Frozen step input changed')
                if row[1]=='OK':return json.loads(row[2])
                raise RuntimeError('Retained step '+row[1]+': '+key)
            self.db.execute('INSERT INTO steps VALUES (?,?,?,?,?)',(key,digest,'STARTED',None,None));self.db.commit()
        try:
            result=make()
        except Exception as exc:
            with self.lock:
                self.db.execute('UPDATE steps SET status=?,error=? WHERE key=?',('FAILED',type(exc).__name__+': '+str(exc),key));self.db.commit()
            raise
        with self.lock:
            self.db.execute('UPDATE steps SET status=?,result=? WHERE key=?',('OK',canonical(result),key));self.db.commit()
        return result


class BaceGateway(Gateway):
    def __init__(self,path,*,request_cap,config=None,concurrency=8,spacing_seconds=6.1):
        if type(request_cap) is not int or request_cap<1:
            raise ValueError('Explicit positive pilot request cap required')
        self.request_cap=request_cap;self.reserved=set();self.budget_lock=threading.RLock()
        super().__init__(path,concurrency=concurrency,config=config,model='qwen3.8-flash')
        self.rate=RateLimitGate(spacing_seconds=spacing_seconds)

    def _complete_attempt(self,key,system,payload,max_tokens=4096):
        # Called for normal, 429-recovery and schema-repair requests alike.
        # One process owns runner_lock; threads share these reservations.
        with self.budget_lock,self.lock:
            prior=self._request_row(key)
            imported=self.db.execute('SELECT 1 FROM cache_imports WHERE key=?',(key,)).fetchone()
            if prior or imported:
                cached=True
            else:
                cached=False
                registered={r[0] for r in self.db.execute('SELECT key FROM requests')}
                occupied=len(registered)+len(self.reserved-registered)
                if occupied>=self.request_cap:raise CallError('bace_request_cap_no_dispatch')
                self.reserved.add(key)
        try:
            return super()._complete_attempt(key,system,payload,max_tokens)
        finally:
            if not cached:
                with self.budget_lock:self.reserved.discard(key)
