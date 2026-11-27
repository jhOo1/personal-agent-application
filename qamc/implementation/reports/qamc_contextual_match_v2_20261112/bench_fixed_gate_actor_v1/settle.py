"""Verify actual Actor manifests, summarize paired completed draws without dispatch."""
from collections import Counter, defaultdict
import json
from panel import HERE, BASE, RUN, digest, read

PRIVATE = HERE / "private"
MODELS = ("qwen3.8-flash", "deepseek-v4.1-flash")


def verify_wires(cards):
    count = 0
    receipts = Counter()
    for p in sorted(PRIVATE.glob("Actor*_MANIFEST.json")):
        stage = p.name.removesuffix("_MANIFEST.json")
        model = stage.split("_",1)[1]
        manifest = read(p)
        seen = set()
        for entry in manifest["units"]:
            unit, request = entry["unit"], entry["request"]
            uid = unit["root_id"]
            if uid in seen or uid not in cards or model not in MODELS or request["model"] != model or unit["method"] != model:
                raise ValueError("Unexpected Actor manifest")
            seen.add(uid)
            if digest({**request,"model":MODELS[0]}) != cards[uid]["request_sha256"]:
                raise ValueError("Actor wire mismatch")
        if seen != set(cards):
            raise ValueError("Incomplete Actor manifest")
        requests = {row["unit"]["root_id"]: row for row in manifest["units"]}
        received = set()
        stage_dir = RUN.with_name(HERE.name) / stage
        for record_path in stage_dir.glob("visible/*/record.json"):
            record = read(record_path)
            uid = record["unit"]["root_id"]
            original = requests[uid]
            saved_wire = read(record_path.with_name("request.json"))
            if (uid in received or original["unit"] != record["unit"]
                    or original["request"] != saved_wire
                    or digest(saved_wire) != record["request_sha256"]):
                raise ValueError("Receipt does not match frozen Actor request")
            received.add(uid)
            receipts[record["status"]] += 1
        count += len(seen)
    return count, dict(receipts)


def settle():
    roster = read(HERE/"PANEL.json")
    cards = {r["uid"]:r for group in roster.values() for r in group}
    cohorts = {r["uid"]:g for g,rows in roster.items() for r in rows}
    targets = {(r["uid"],r["position"]):r["preference"] for r in
               read(BASE/"strong_actor_boundary_audit_v1/CENSUS.json")["BenchPreS"]["attributes"]}
    manifested, receipts = verify_wires(cards)
    summary = {"verified_actor_wires":manifested,"verified_actor_receipts":receipts,"completed_draws":0}
    checkpoints = sorted(PRIVATE.glob("DRAW*.json"))
    if not checkpoints:
        return summary
    result = read(checkpoints[-1])
    n = len(checkpoints)
    expected = {(uid,rep,m) for uid in cards for rep in range(n) for m in MODELS}
    rows = {(r["uid"],r["rep"],r["model"]):r for r in result["rows"]}
    if set(rows)!=expected or len(rows)!=len(result["rows"]):
        raise ValueError("Draw inventory mismatch")
    totals = defaultdict(lambda:defaultdict(Counter))
    missing = Counter()
    pair_direction = defaultdict(Counter)
    lower = Counter()
    upper = Counter()
    for uid,card in cards.items():
        cohort = cohorts[uid]
        for rep in range(n):
            scores = [rows[uid,rep,m]["score"] for m in MODELS]
            for m,s in zip(MODELS,scores):
                if s is None:
                    missing[f"{cohort}/{m}"]+=1
            hits = []
            for score in scores:
                if score is None:
                    hits.append(None)
                    continue
                decision = score["decisions"][card["position"]]
                if decision["preference"] != targets[uid,card["position"]] or not decision["appropriate"]:
                    raise ValueError("Unmatched target attribute")
                hits.append(int(decision["label"] == "follow"))
            qwen, deepseek = hits
            lower[cohort] += (deepseek if deepseek is not None else 0) - (qwen if qwen is not None else 1)
            upper[cohort] += (deepseek if deepseek is not None else 1) - (qwen if qwen is not None else 0)
            if None not in hits:
                outcome = {(0, 0): "both_miss", (0, 1): "deepseek_only",
                           (1, 0): "qwen_only", (1, 1): "both_follow"}[qwen, deepseek]
                pair_direction[cohort][outcome] += 1
            if any(s is None for s in scores):
                continue
            for m,s in zip(MODELS,scores):
                attr = s["decisions"][card["position"]]
                for key in (cohort,cohort+"/"+card["profile"],cohort+"/"+uid):
                    totals[key][m].update(pairs=1,follow=int(attr["label"]=="follow"),
                        aar=s["aar_numerator"],aar_denom=s["aar_denominator"],
                        mr=s["mr_numerator"],mr_denom=s["mr_denominator"],completeness=s["task_completeness"])
    ledger=result["ledger"]
    summary.update(indexed_pairs=pair_direction,
                   indexed_net_bounds={g:[lower[g],upper[g]] for g in sorted(lower)},
                   completed_draws=n,totals=totals,missing_scores=dict(missing),
                   receipt_status=Counter(r["status"] for r in ledger),
                   reported_tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),
                   unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger))
    return summary


if __name__=="__main__":
    print(json.dumps(settle(),indent=2,sort_keys=True))
