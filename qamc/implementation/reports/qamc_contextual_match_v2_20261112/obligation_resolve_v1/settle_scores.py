"""Read-only four-way paired analysis of frozen answers and their task-specific grades."""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / "runs/qamc_contextual_match_v2_20261112/obligation_resolve_v1"
ARMS = ("BASE", "FREE", "LOCAL_EDIT", "ISOLATED")


def read(name):
    return json.loads((PRIVATE / name).read_text())


def metrics(domain, s):
    if domain.startswith("RPEval"):
        match = s.get("match", {})
        return {"matched": match.get("matched", s.get("matched")), "positions": match.get("positions", s.get("total")),
                **{k: s.get("severity", s)[k] for k in ("OPB", "UPB", "FM")}}
    if domain == "BenchPreS":
        m = {"completeness": s["completeness"]}
        for k in ("aar", "nonbold", "mr"):
            m[k], m[k + "_positions"] = s[k]
        return m
    key = "failure_strict_utility" if domain.endswith("beneficial_memory_usage") else "failure_release"
    return {"passed": int(not s[key])}


def main():
    result = read("WRITER_RESULT_PRIVATE.json")
    answers = read("WRITER_ANSWERS_PRIVATE.json")
    first = read("INTERFACES_PRIVATE.json")
    old = ROOT / "runs/qamc_contextual_match_v2_20261112/persist_exposure_fr3_v1/RESULTS.json"
    tracks = {r["uid"]: r["track"] for r in json.loads(old.read_text())["rows"]}
    out = defaultdict(dict)
    for uid, row in result["uid_scores"].items():
        domain = row["domain"]
        if domain == "RPEval":
            domain += "/multi" if "match" in row["base"] else "/single"
        if domain == "PersistBench":
            domain += "/" + tracks[uid]
        status = answers["states"][uid]
        grades = {"BASE": row["base"], **row["scores"]}
        for subset in ("all", status):
            item = out[domain].setdefault(subset, {"assigned": 0, "common": 0,
                "totals": {a: Counter() for a in ARMS}, "disposition": {a: Counter() for a in ARMS[1:]}})
            item["assigned"] += 1
            for a in ARMS[1:]:
                item["disposition"][a][answers["outputs"][uid][a]["status"]] += 1
            if any(not grades[a] for a in ARMS):
                continue
            item["common"] += 1
            for a in ARMS:
                item["totals"][a].update(metrics(domain, grades[a]))
    ledger = first["ledger"] + read("WRITER_LEDGER.json")
    assert sum(d["all"]["assigned"] for d in out.values()) == 29
    return {"domains": out, "cost": {"requests": len(ledger), "statuses": Counter(r["status"] for r in ledger),
             "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
             "unknown_usage": sum((r["usage"] or {}).get("total_tokens") is None for r in ledger)}}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
