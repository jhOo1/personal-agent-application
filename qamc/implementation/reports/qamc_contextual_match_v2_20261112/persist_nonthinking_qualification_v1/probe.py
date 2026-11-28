"""A synthetic paired configuration check; never persist model reasoning or credentials."""
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from qamc.bace.runtime import runner_lock
from qamc.common import canonical, sha
from qamc.transport_helpers import NoRedirect, atomic_json, read_reference

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name
MODEL = "deepseek-v4.1-flash"
MODES = ("disabled", "enabled")


def wire(mode):
    assert mode in MODES
    return dict(model=MODEL, stream=False, temperature=0, max_tokens=1024,
                thinking={"type": mode}, messages=[dict(role="user",
                    content="Compute 16 times 27 minus 13. Output only the decimal integer.")])

def inspect(payload):
    choice = payload["choices"][0]
    message = choice["message"]
    usage = payload.get("usage") or {}
    n = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return dict(alias_matches=payload.get("model") == MODEL,
                correct=str(message.get("content")).strip() == "419",
                stopped=choice.get("finish_reason") == "stop",
                reasoning_text_present=bool(message.get("reasoning_content") or message.get("reasoning")),
                reported_reasoning_tokens=n if type(n) is int and n >= 0 else None,
                usage={k:usage[k] for k in ("prompt_tokens","completion_tokens","total_tokens")
                       if type(usage.get(k)) is int and usage[k] >= 0})

def qualifies(pair):
    if not all(r.get("status") == "OK" and r["alias_matches"] and r["stopped"] and r["correct"]
               for r in pair.values()):
        return False
    off, on = (pair[k] for k in MODES)
    return (off["reported_reasoning_tokens"] == 0 and not off["reasoning_text_present"] and
            (on["reasoning_text_present"] or (on["reported_reasoning_tokens"] or 0) > 0))

def run():
    config, fingerprint = read_reference()
    pair = {}
    with runner_lock(OUT / "runner.lock"):
        for mode in MODES:
            path = OUT / (mode + ".json")
            if path.exists():
                pair[mode] = json.loads(path.read_text())
                continue
            w = wire(mode)
            receipt = dict(mode=mode, status="PENDING_DELIVERY_UNKNOWN", automatic_retries=0,
                           request_sha256=sha(w), reference_sha256=fingerprint, started_unix=time.time())
            atomic_json(path, receipt)
            body = {**w, **{k:config[k] for k in ("app","quota_id","user_id","access_key")}}
            request = Request(config["base_url"].rstrip("/") + "/chat/completions",
                              data=canonical(body).encode(), headers={"Content-Type":"application/json",
                              "Authorization":"Bearer " + config["api_key"]})
            try:
                with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=180) as response:
                    raw = response.read(4_000_000)
                    receipt.update(http_status=response.status, response_sha256=hashlib.sha256(raw).hexdigest())
                receipt.update(inspect(json.loads(raw)), status="OK")
            except HTTPError as exc:
                receipt.update(status="HTTP_ERROR", http_status=exc.code)
            except (ValueError, OSError, KeyError, IndexError, TypeError, AttributeError) as exc:
                receipt.update(status="UNVERIFIED_RESPONSE", error_class=type(exc).__name__)
            receipt["seconds"] = round(time.time() - receipt["started_unix"], 2)
            atomic_json(path, receipt)
            pair[mode] = receipt
            if mode == "disabled":
                time.sleep(3.2)
        result = dict(observed=pair, qualified=qualifies(pair))
        atomic_json(OUT / "RESULTS.json", result)
        print(json.dumps(result))

def test():
    assert {k:v for k,v in wire("enabled").items() if k != "thinking"} == {
        k:v for k,v in wire("disabled").items() if k != "thinking"}
    payload = dict(model=MODEL, choices=[dict(finish_reason="stop", message={"content":"419"})],
                   usage={"completion_tokens_details":{"reasoning_tokens":0}})
    off = dict(inspect(payload), status="OK")
    on = dict(off, reported_reasoning_tokens=8)
    assert qualifies(dict(enabled=on, disabled=off))
    for unknown in (None, 1):
        assert not qualifies(dict(enabled=on, disabled=dict(off, reported_reasoning_tokens=unknown)))
    assert not qualifies(dict(enabled=off, disabled=off))
    assert not qualifies(dict(enabled=on, disabled=dict(off, correct=False)))
    assert not qualifies(dict(enabled=on, disabled=dict(off, reasoning_text_present=True)))
    print("Paired qualification fixtures passed")

if __name__ == "__main__":
    {"run": run, "test": test}[sys.argv[1]]()
