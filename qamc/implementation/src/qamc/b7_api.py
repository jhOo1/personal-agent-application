"""B7 transport snapshot of api.py, generalized only for an explicitly frozen model.
Original api.py and its historical experiments remain unchanged.
"""
from __future__ import annotations

import json
import re
import sqlite3
import socket
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .common import ROOT, canonical, dump, parse_object, sha, token_estimate
from .transport_helpers import NoRedirect, read_reference, sanitize
from .rate_limit import RateLimitGate
from .dns_transport import DNSCache, CachedDNSHTTPSHandler


class CallError(RuntimeError):
    pass


class Gateway:
    def __init__(self, run_dir: Path, concurrency: int = 10, max_input_bytes: int = 2_000_000,
                 config: dict | None = None, service_recovery: dict | None = None,
                 incomplete_recovery: dict | None = None, transport_settings: dict | None = None,
                 model: str = "qwen3.8-flash"):
        if model not in {"qwen3.8-flash", "qwen3.8-max"}:
            raise ValueError("B7 model must be explicitly supported and frozen")
        self.model = model
        self.root = Path(run_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config, self.reference_sha = read_reference() if config is None else (config, "offline_fixture")
        self.lock = threading.RLock()
        self._payload_condition = threading.Condition()
        self._inflight_payloads = set()
        self.slots = threading.BoundedSemaphore(concurrency)
        self.max_input_bytes = max_input_bytes
        self.rate = RateLimitGate()
        # A direct user restoration report starts a new, frozen recovery window.
        # It never clears partial/unknown failures, successful caches or old logs.
        frozen_config = ROOT / 'configs' / f'experiment_{self.root.parent.name}.json'
        frozen = json.loads(frozen_config.read_text()) if frozen_config.exists() else {}
        limits = transport_settings or frozen.get('transport_settings') or {'socket_timeout_seconds':600,'stream_observation_limit_seconds':1200}
        self.socket_timeout = float(limits['socket_timeout_seconds'])
        self.stream_limit = float(limits['stream_observation_limit_seconds'])
        if not 0 < self.socket_timeout <= self.stream_limit <= 3600:
            raise ValueError('invalid transport timeout limits')
        if service_recovery is None and frozen_config.exists():
            service_recovery = json.loads(frozen_config.read_text()).get('service_recovery')
        if incomplete_recovery is None and frozen_config.exists():
            incomplete_recovery = json.loads(frozen_config.read_text()).get('explicit_incomplete_recovery')
        self.incomplete_recovery = incomplete_recovery
        self.allowed_incomplete = {}
        if incomplete_recovery:
            not_before = incomplete_recovery.get('retry_not_before_utc')
            if not_before and time.time() < datetime.fromisoformat(not_before.replace('Z','+00:00')).timestamp():
                raise CallError('explicit_retry_wait_not_elapsed_no_dispatch')
            if incomplete_recovery.get('scope') != 'incomplete_pure_text_inference_once' or not incomplete_recovery.get('plan_id'):
                raise ValueError('incomplete recovery requires a frozen explicit request manifest')
            for item in incomplete_recovery['requests']:
                ledger=Path(item['ledger']).resolve()
                with sqlite3.connect(f'file:{ledger}?mode=ro',uri=True) as prior:
                    found=prior.execute('SELECT data FROM requests WHERE request_id=?',(item['request_id'],)).fetchone()
                old=json.loads(found[0]) if found else None
                if (not old or sha(old)!=item['row_sha256'] or old['payload_sha']!=item['payload_sha'] or old['key']!=item['key']
                        or old['status'] not in ('transport_error_delivery_unknown','protocol_error')
                        or old.get('usage') is not None or old.get('finish_reason')=='stop'):
                    raise ValueError('incomplete recovery source does not match unresolved transport failure')
                stream=ledger.parent/old['stream_path']
                visible_partial = stream.exists() and any((c.get('delta') or {}).get('content')
                     for line in stream.read_text().splitlines() for c in json.loads(line).get('choices',[]))
                if old['status']=='protocol_error':
                    # Only the exact saved upstream exception without any model
                    # content may be continued; other protocol failures stay final.
                    frames=[json.loads(line) for line in stream.read_text().splitlines()] if stream.exists() else []
                    messages=[str((frame.get('error') or {}).get('message','')) for frame in frames]
                    upstream_exception = (old.get('error') == 'stream_in_band_error' and old.get('returned_model') is None
                        and not visible_partial and len(frames) == 1 and all("KeyError: 'data'" in m for m in messages)
                        and item.get('upstream_error_stream_sha256') == sha(stream.read_bytes()))
                    # Explicitly permit one retry of a hashed, reasoning-only truncated
                    # stream. Provider work and prior token usage remain unknown.
                    empty_truncation = (old.get('error') == 'stream_missing_finish_reason' and bool(frames)
                        and not visible_partial and incomplete_recovery.get('allow_empty_truncation_once') is True
                        and item.get('truncated_stream_sha256') == sha(stream.read_bytes())
                        and all(not frame.get('error') and isinstance(frame.get('choices'), list)
                            and len(frame['choices']) == 1 and all(
                                c.get('finish_reason') is None and isinstance(c.get('delta'), dict)
                                and set(c['delta']) <= {'role', 'reasoning_content', 'reasoning'}
                                and c['delta'].get('role', 'assistant') == 'assistant'
                                for c in frame['choices']) for frame in frames))
                    # An explicitly authorized single restart may also quarantine a
                    # hashed stream ending in a narrowly identified upstream outage.
                    final_error = (frames[-1].get('error') or {}) if frames else {}
                    message = str(final_error.get('message', ''))
                    known_interrupt = (message.startswith('stream_interrupt:') and 'InvalidChunkLength' in message)
                    known_timeout = message == 'Async stream total timeout after 600s'
                    frozen_outage = (old.get('error') == 'stream_in_band_error' and bool(frames)
                        and all(not frame.get('error') for frame in frames[:-1])
                        and (known_interrupt or known_timeout)
                        and incomplete_recovery.get('allow_hashed_upstream_outage_once') is True
                        and incomplete_recovery.get('authorization', {}).get('authority') == 'direct_user_wait_then_retry'
                        and incomplete_recovery.get('authorization', {}).get('user_answer') == '等一段时间重试即可'
                        and item.get('upstream_outage_stream_sha256') == sha(stream.read_bytes()))
                    if not (upstream_exception or empty_truncation or frozen_outage):
                        raise ValueError('incomplete recovery source is not an approved frozen protocol failure')
                if visible_partial and not (item.get('quarantined_partial_sha256') == sha(stream.read_bytes())
                    and incomplete_recovery.get('allow_quarantined_partial_restart_once') is True
                    and incomplete_recovery.get('authorization',{}).get('user_answer') == '等一段时间重试即可'
                    and incomplete_recovery.get('authorization',{}).get('authority') == 'direct_user_wait_then_retry'):
                    raise ValueError('incomplete recovery manifest cannot include visible partial answers without explicit quarantined restart')
                self.allowed_incomplete[(str(Path(item['ledger']).resolve()), item['request_id'])] = item
        self.service_recovery = service_recovery
        self.recovery_cutoff = None
        if service_recovery is not None:
            if service_recovery.get('authority') != 'direct_user_service_restoration' or not service_recovery.get('epoch_id'):
                raise ValueError('service recovery requires explicit user restoration evidence')
            self.recovery_cutoff = datetime.fromisoformat(service_recovery['confirmed_at_utc'].replace('Z', '+00:00')).timestamp()
            if self.recovery_cutoff > time.time():
                raise ValueError('service recovery timestamp cannot be in the future')
        self.db = sqlite3.connect(self.root / "ledger.sqlite", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (request_id INTEGER PRIMARY KEY, key TEXT UNIQUE, payload_sha TEXT, data TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, data TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cache_imports (key TEXT PRIMARY KEY,payload_sha TEXT,data TEXT)")
        self.db.commit()
        self.dns_policy = frozen.get('dns_cache_settings') or {'ttl':300.,'max_stale':1800.,'retry_spacing':30.}
        self.dns = DNSCache(self.root / 'private_dns_cache.json', event=self.event, **self.dns_policy)
        self.disabled = any(json.loads(r[0]).get("disable_model") for r in self.db.execute("SELECT data FROM requests"))
        self.external_cache = {}
        self.external_failures = {}
        # Reuse only completed, byte-identical public requests from prior versions.
        # Such a reuse is an imported artifact, never a new independent generation.
        # Experiments may isolate phases under runs/<experiment>/<phase>/api.
        # Include those ledgers so a delivery-unknown smoke request cannot be
        # silently resent by a later phase under a different key.
        ledger_paths = set((ROOT / "runs").glob("*/api/ledger.sqlite"))
        ledger_paths.update((ROOT / "runs").glob("*/*/api/ledger.sqlite"))
        for ledger in sorted(ledger_paths):
            if ledger.resolve() == (self.root / "ledger.sqlite").resolve():
                continue
            with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as prior:
                for data, in prior.execute("SELECT data FROM requests"):
                    row = json.loads(data)
                    if row.get("status") == "ok" and row.get("returned_model") == self.model:
                        self.external_cache.setdefault(row["payload_sha"], (ledger, row))
                    elif row.get('status') != 'ok':
                        self.external_failures.setdefault(row['payload_sha'], []).append(
                            {'ledger':str(ledger), 'request_id':row['request_id'], 'status':row['status'],
                             'known_precontent_429':self._known_429(row, ledger.parent),
                             'started_utc':row.get('started_utc'),
                             'row_sha256':sha(row),
                             'service_recovery_epoch':row.get('service_recovery_epoch')})

    @staticmethod
    def _known_429(row, root):
        if row.get('upstream_status') == 429:
            return bool(row.get('rate_limit_recovery_eligible'))
        if row.get('http_status') == 429:
            return True
        if row.get('error') != 'stream_in_band_error' or row.get('returned_model') or row.get('usage'):
            return False
        path = Path(root) / row.get('stream_path', '_missing')
        if not path.is_file():
            return False
        found = False
        for line in path.read_text().splitlines():
            frame = json.loads(line)
            for choice in frame.get('choices') or []:
                if (choice.get('delta') or {}).get('content'):
                    return False
            if frame.get('error') and re.search(r'\b429\b', str(frame['error'])):
                found = True
        return found

    def event(self, **data):
        with self.lock:
            self.db.execute("INSERT INTO events(data) VALUES (?)", (canonical({"utc": time.time(), **data}),))
            self.db.commit()

    def _save(self, row: dict):
        with self.lock:
            self.db.execute("UPDATE requests SET data=? WHERE request_id=?", (canonical(row), row["request_id"]))
            self.db.commit()

    def _request_row(self, key):
        with self.lock:
            row = self.db.execute("SELECT data FROM requests WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def complete(self, key: str, system: str, payload, max_tokens: int = 4096) -> str:
        """Coalesce identical in-flight requests while preserving distinct keys."""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)}]
        public = {"model": self.model, "messages": messages, "temperature": 0,
                  "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True}}
        digest = sha(public)
        with self._payload_condition:
            while digest in self._inflight_payloads:
                self._payload_condition.wait()
            self._inflight_payloads.add(digest)
        try:
            return self._complete_serialized(key, system, payload, max_tokens)
        finally:
            with self._payload_condition:
                self._inflight_payloads.remove(digest)
                self._payload_condition.notify_all()

    def _complete_serialized(self, key: str, system: str, payload, max_tokens: int = 4096) -> str:
        """One normal attempt, at most one separately logged pre-content 429 recovery.

        Partial/unknown transport errors are never retried. An exhausted recovery
        opens a circuit instead of silently skipping many history segments.
        """
        try:
            return self._complete_attempt(key, system, payload, max_tokens)
        except CallError:
            first = self._request_row(key)
            if not first or first.get('upstream_status') != 429:
                raise
            recovery_key = key + '/rate_limit_recovery1'
            recovered = self._request_row(recovery_key)
            if recovered and recovered['status'] == 'ok':
                return self._complete_attempt(recovery_key, system, payload, max_tokens)
            delay = self.rate.rate_limited(first.get('retry_after_seconds'))
            if first.get('automatic_retries', 0):
                self._rate_stop(key, '429_cross_version_recovery_exhausted')
                raise
            if not first.get('rate_limit_recovery_eligible'):
                self._rate_stop(key, '429_after_content_or_usage')
                raise
            self.event(key=key, status='bounded_rate_limit_recovery', original_request_id=first['request_id'],
                       recovery_key=recovery_key, max_recoveries=1, cooldown_seconds=delay,
                       original_failure_retained=True, original_usage_may_remain_unknown=True)
            try:
                return self._complete_attempt(recovery_key, system, payload, max_tokens)
            except CallError:
                last = self._request_row(recovery_key)
                if last and last.get('upstream_status') == 429:
                    self.rate.rate_limited(last.get('retry_after_seconds'))
                    self._rate_stop(key, '429_recovery_exhausted')
                raise

    def _rate_stop(self, key, reason):
        (self.root / 'STOP').write_text(reason + ': ' + key)
        self.disabled = True
        self.event(key=key, status='rate_limit_circuit_open', reason=reason,
                   quota_or_auth_failure=False, new_dispatch_stopped=True)

    def _complete_attempt(self, key: str, system: str, payload, max_tokens: int = 4096) -> str:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)}]
        public = {"model": self.model, "messages": messages, "temperature": 0,
                  "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True}}
        digest = sha(public)
        size = len(canonical(messages).encode())
        if size > self.max_input_bytes:
            self.event(key=key, status="input_capacity_gate_no_dispatch", bytes=size,
                       limit=self.max_input_bytes, actual_model_capacity_certified=False)
            raise CallError("input_capacity_gate_no_dispatch")
        with self.slots:
            with self.lock:
                prev = self.db.execute("SELECT data,payload_sha FROM requests WHERE key=?", (key,)).fetchone()
                if prev:
                    old = json.loads(prev[0])
                    if prev[1] != digest:
                        raise CallError("resume_payload_changed")
                    if old["status"] != "ok":
                        raise CallError("previous_attempt_retained_" + old["status"])
                    self.event(key=key, status='local_cache_hit', source_request_id=old['request_id'])
                    return json.loads((self.root / old["response_path"]).read_text())["answer"]
                imported = self.db.execute("SELECT data,payload_sha FROM cache_imports WHERE key=?", (key,)).fetchone()
                if imported:
                    if imported[1] != digest:
                        raise CallError("resume_import_payload_changed")
                    old = json.loads(imported[0])
                    path = Path(old["source_response_path"])
                    if sha(path.read_bytes()) != old["source_response_sha256"]:
                        raise CallError("imported_response_changed")
                    self.event(key=key, status='imported_cache_hit', source_request_id=old['source_request_id'])
                    return json.loads(path.read_text())["answer"]
                # Successful same-ledger responses are reusable across keys too.
                # Exact public-request equality is checked before recording lineage.
                local_rows = self.db.execute('SELECT data FROM requests WHERE payload_sha=? ORDER BY request_id', (digest,)).fetchall()
                local_rows = [json.loads(row[0]) for row in local_rows]
                for old in local_rows:
                    if old['status'] != 'ok':
                        continue
                    old_request = self.root / old['request_path']
                    old_response = self.root / old['response_path']
                    if old_request.exists() and old_response.exists() and json.loads(old_request.read_text()) == public:
                        provenance = {'key':key, 'payload_sha':digest, 'status':'cached_success',
                                      'source_ledger':str((self.root / 'ledger.sqlite').resolve()),
                                      'source_request_id':old['request_id'],
                                      'source_request_path':str(old_request.resolve()),
                                      'source_response_path':str(old_response.resolve()),
                                      'source_response_sha256':sha(old_response.read_bytes()),
                                      'new_real_requests':0, 'independent_generation':False}
                        self.db.execute('INSERT INTO cache_imports VALUES (?,?,?)', (key, digest, canonical(provenance)))
                        self.db.commit()
                        return json.loads(old_response.read_text())['answer']
                # Another key's unresolved attempt is not an implicit retry permit.
                if any(old['status'] != 'ok' and old['key'] != key and
                       key != old['key'] + '/rate_limit_recovery1' for old in local_rows):
                    raise CallError('prior_local_failed_payload_no_automatic_dispatch')
                if digest in self.external_cache:
                    ledger, old = self.external_cache[digest]
                    old_request = ledger.parent / old["request_path"]
                    old_response = ledger.parent / old["response_path"]
                    if json.loads(old_request.read_text()) == public and old_response.exists():
                        provenance = {"key": key, "payload_sha": digest, "status": "cached_success",
                                      "source_ledger": str(ledger), "source_request_id": old["request_id"],
                                      "source_request_path": str(old_request), "source_response_path": str(old_response),
                                      "source_response_sha256": sha(old_response.read_bytes()),
                                      "new_real_requests": 0, "independent_generation": False}
                        self.db.execute("INSERT INTO cache_imports VALUES (?,?,?)", (key, digest, canonical(provenance)))
                        self.db.commit()
                        return json.loads(old_response.read_text())["answer"]
            past_failures = self.external_failures.get(digest, [])
            active_failures = past_failures
            explicit_recoveries = []
            if past_failures:
                for old in past_failures:
                    permit = self.allowed_incomplete.get((str(Path(old['ledger']).resolve()), old['request_id']))
                    if (permit and old['status'] in ('transport_error_delivery_unknown','protocol_error')
                            and permit['payload_sha']==digest and permit['row_sha256']==old['row_sha256']):
                        explicit_recoveries.append(old)
                if any(not old['known_precontent_429'] and old not in explicit_recoveries for old in past_failures):
                    self.event(key=key, status='prior_failed_payload_no_automatic_dispatch', failures=past_failures)
                    raise CallError('prior_failed_or_unknown_payload_no_automatic_dispatch')
                # Only fully observed pre-content 429s strictly before the trusted
                # recovery timestamp can leave the active retry window.
                active_failures = [old for old in past_failures if old not in explicit_recoveries]
                if self.recovery_cutoff is not None:
                    def before_recovery(old):
                        if (old.get('service_recovery_epoch') or {}).get('epoch_id') == self.service_recovery['epoch_id']:
                            return False
                        try:
                            return datetime.fromisoformat(old['started_utc'].replace('Z', '+00:00')).timestamp() < self.recovery_cutoff
                        except (KeyError, TypeError, ValueError):
                            return False
                    active_failures = [old for old in active_failures if not before_recovery(old)]
                if len(active_failures) > 1:
                    self._rate_stop(key, 'prior_429_recovery_already_exhausted')
                    raise CallError('prior_429_recovery_already_exhausted')
            self.rate.wait_turn(lambda: self.disabled or (self.root / "STOP").exists())
            with self.lock:
                # A second local caller cannot send the same key during cooldown.
                if self.db.execute("SELECT 1 FROM requests WHERE key=?", (key,)).fetchone():
                    raise CallError("request_claimed_during_cooldown_no_duplicate_dispatch")
                if self.disabled or (self.root / "STOP").exists():
                    raise CallError("operator_or_quota_stop_no_dispatch")
                row = {"key": key, "model": self.model, "prompt_hash": sha(system),
                       "payload_sha": digest, "status": "pending_delivery_unknown", "usage": None,
                       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "automatic_retries": int(bool(active_failures) or bool(explicit_recoveries) or key.endswith('/rate_limit_recovery1')), "input_utf8_bytes": size,
                       "previous_failure_sources": past_failures,
                       "active_window_previous_failures": active_failures,
                       "service_recovery_epoch": self.service_recovery,
                       "explicit_incomplete_recovery": {'plan_id':self.incomplete_recovery['plan_id'],
                           'sources':explicit_recoveries,'possible_duplicate_provider_work':True,
                           'prior_usage_remains_unknown':True,'human_reapproval_claimed':False} if explicit_recoveries else None,
                       "related_incomplete_operation_sources": [item for item in self.allowed_incomplete.values()
                           if (item.get('key')==key or (not key.startswith('store/') and item.get('key','').split('/',1)[-1]==key.split('/',1)[-1]))],
                       "transport_policy": "stop_new_dispatch_on_first_error; no_automatic_resend; explicit_frozen_manifest_once_only",
                       "transport_limits": {'socket_timeout_seconds':self.socket_timeout,'stream_observation_limit_seconds':self.stream_limit,'strict_absolute_deadline':False},
                       "dns_cache_policy": {**self.dns_policy, 'tls_hostname_verification_unchanged':True, 'http_retry':False},
                       "recovery_of_key": key.removesuffix('/rate_limit_recovery1') if key.endswith('/rate_limit_recovery1') else None,
                       "rate_limit_policy": "known_precontent_429_only; max_one_recovery; shared_120s_cooldown; circuit_after_exhaustion",
                       "estimated_input_tokens_cl100k": token_estimate(canonical(messages)),
                       "max_tokens": max_tokens, "reference_config_sha256": self.reference_sha}
                cur = self.db.execute("INSERT INTO requests(key,payload_sha,data) VALUES (?,?,?)",
                                      (key, digest, canonical(row)))
                row["request_id"] = cur.lastrowid
                prefix = f"raw/{row['request_id']:06d}"
                row.update(request_path=prefix + "_request.json", response_path=prefix + "_response.json",
                           stream_path=prefix + "_stream.jsonl")
                dump(self.root / row["request_path"], public)
                self._save(row)
            body = {**public, **{k: self.config[k] for k in ("app", "quota_id", "user_id", "access_key")}}
            req = urllib.request.Request(self.config["base_url"].rstrip("/") + "/chat/completions",
                                         data=canonical(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.config["api_key"]})
            start = time.monotonic()
            text, finish, model, usage, response_id = [], None, None, None, None
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), CachedDNSHTTPSHandler(self.dns))
                with opener.open(req, timeout=self.socket_timeout) as res, (self.root / row["stream_path"]).open("w") as stream:
                    row["http_status"] = res.status
                    for line in res:
                        if time.monotonic() - start > self.stream_limit:
                            self.disabled = True
                            (self.root/'STOP').write_text('stream_observation_limit: '+key)
                            self.event(key=key,status='stream_observation_limit_circuit_open',
                                       limit_seconds=self.stream_limit,strict_absolute_deadline=False,new_dispatch_stopped=True)
                            raise CallError(f"stream_observation_limit_{self.stream_limit:g}s")
                        if not line.startswith(b"data:"):
                            continue
                        data = line[5:].strip()
                        if data == b"[DONE]":
                            break
                        if not data:
                            continue
                        chunk = json.loads(data)
                        stream.write(canonical(sanitize(chunk, self.config)) + "\n")
                        stream.flush()
                        if chunk.get("error"):
                            err = canonical(chunk["error"]).lower()
                            if any(w in err for w in ("insufficient_quota", "quota exceeded", "insufficient balance", "authentication", "invalid_api_key")):
                                row["disable_model"] = True
                                self.disabled = True
                                raise CallError("quota_or_auth")
                            if re.search(r'\b429\b', err):
                                row.update(upstream_status=429, rate_limit_recovery_eligible=not text and usage is None,
                                           observed_visible_content_before_error=bool(text))
                                raise CallError("upstream_rate_limit_429")
                            if not text and usage is None and model is None:
                                # An upstream empty error has no model result. Stop
                                # new dispatch before a persistent gateway fault
                                # marks many independent Writer chunks as failed.
                                self.disabled = True
                                (self.root/'STOP').write_text('upstream_empty_error: '+key)
                                self.event(key=key,status='upstream_empty_error_circuit_open',
                                           new_dispatch_stopped=True,delivery_and_usage_unknown=True)
                            raise CallError("stream_in_band_error")
                        model = chunk.get("model") or model
                        usage = chunk.get("usage") or usage
                        response_id = chunk.get("id") or response_id
                        for choice in chunk.get("choices") or []:
                            if choice.get("index", 0) != 0:
                                raise CallError("unexpected_choice")
                            delta = choice.get("delta") or {}
                            if delta.get("tool_calls"):
                                raise CallError("unexpected_tool_call")
                            if delta.get("content"):
                                text.append(delta["content"])
                            finish = choice.get("finish_reason") or finish
                answer = "".join(text)
                row.update(returned_model=model, finish_reason=finish, usage=usage, response_id=response_id)
                dump(self.root / row["response_path"], {"answer": answer, "finish_reason": finish,
                                                       "model": model, "usage": usage, "id": response_id})
                if finish != "stop":
                    raise CallError("stream_missing_finish_reason" if finish is None else "finish_" + str(finish))
                if model != self.model:
                    raise CallError("model_alias_mismatch")
                if not answer.strip():
                    raise CallError("empty_answer")
                if not isinstance(usage, dict) or any(type(usage.get(k)) is not int for k in
                                                    ("prompt_tokens", "completion_tokens", "total_tokens")):
                    raise CallError("missing_or_invalid_usage")
                row["status"] = "ok"
                return answer
            except urllib.error.HTTPError as exc:
                err = exc.read(65536).decode(errors="replace")
                dump(self.root / row["response_path"], {"http_status": exc.code, "error": sanitize(err, self.config)})
                row.update(status="http_error", http_status=exc.code, error="http_" + str(exc.code))
                if exc.code == 429:
                    row.update(upstream_status=429, rate_limit_recovery_eligible=True,
                               retry_after_seconds=exc.headers.get('Retry-After') if exc.headers else None)
                if exc.code in (401, 403) or any(w in err.lower() for w in ("insufficient_quota", "quota exceeded", "insufficient balance")):
                    row["disable_model"] = True
                    self.disabled = True
                    row["error"] = "quota_or_auth"
                raise CallError(row["error"]) from None
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                row.update(status="transport_error_delivery_unknown", error=type(exc).__name__)
                reason = getattr(exc, 'reason', exc)
                frames = traceback.extract_tb(exc.__traceback__)
                last = frames[-1] if frames else None
                row.update(transport_reason_type=type(reason).__name__,
                           transport_errno=getattr(reason, 'errno', None),
                           transport_file_basename=Path(reason.filename).name if getattr(reason, 'filename', None) else None,
                           transport_origin={"module": Path(last.filename).name, "function": last.name,
                                             "line": last.lineno} if last else None,
                           failure_phase='dns_before_connection' if isinstance(reason,socket.gaierror) else 'transport_stage_not_certified',
                           observed_visible_content_before_error=bool(text))
                # Stop after the first observed transport outage. Already in-flight
                # calls may finish; no later chunks or answers should be dispatched.
                self.disabled = True
                (self.root/'STOP').write_text('transport_outage: '+key)
                self.event(key=key,status='transport_circuit_open',reason_type=type(reason).__name__,
                           prior_delivery_and_usage_may_remain_unknown=True,new_dispatch_stopped=True)
                raise CallError("transport_" + type(exc).__name__) from None
            except Exception as exc:
                row.update(status="protocol_error", error=str(exc) if isinstance(exc, CallError) else type(exc).__name__)
                raise CallError(row["error"]) from None
            finally:
                row.update(latency_seconds=round(time.monotonic() - start, 4), usage=usage,
                           returned_model=model, finish_reason=finish)
                self._save(row)

    def object(self, key: str, prompt: str, payload, validator=None, max_tokens: int = 4096) -> dict:
        raw = self.complete(key, prompt, payload, max_tokens)
        try:
            obj = parse_object(raw)
            if validator:
                validator(obj)
            return obj
        except (ValueError, KeyError, TypeError, AssertionError) as exc:
            self.event(key=key, status="json_contract_failed", error=str(exc))
            repaired = self.complete(key + "/contract_repair", prompt,
                                     {"original_input": payload, "invalid_output": raw,
                                      "contract_error": str(exc), "instruction": "Repair the JSON schema and cited identifiers. Return only one JSON object; do not add new evidence."}, max_tokens)
            obj = parse_object(repaired)
            if validator:
                validator(obj)
            return obj

    def export(self):
        with self.lock:
            rows = [json.loads(r[0]) for r in self.db.execute("SELECT data FROM requests ORDER BY request_id")]
            imports = [json.loads(r[0]) for r in self.db.execute("SELECT data FROM cache_imports ORDER BY key")]
            events = [json.loads(r[0]) for r in self.db.execute("SELECT data FROM events ORDER BY id")]
        dump(self.root / "request_ledger.json", rows)
        dump(self.root / "cache_imports.json", imports)
        dump(self.root / "events.json", events)
        return rows
