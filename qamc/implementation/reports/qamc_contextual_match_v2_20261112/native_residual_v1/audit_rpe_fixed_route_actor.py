"""Verify model-only input changes and summarize paired RPEval outcomes."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "rpe_fixed_route_actor_v1"
REFERENCES = ("GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL", "DES2GEN_FULL", "MEMADAPTER_FULL")


def read(path):
    return json.loads(path.read_text())


def digest(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode()).hexdigest()


def check_inputs(cards):
    manifest = read(OUT / "FixedRouteActor_MANIFEST.json")
    seen = set()
    for entry in manifest["units"]:
        uid = entry["unit"]["root_id"]
        wire = entry["request"]
        if uid in seen or wire["model"] != "gpt-4.1":
            raise ValueError(f"Duplicate case or unexpected Actor alias: {uid}")
        seen.add(uid)
        if digest({**wire, "model": "qwen3.8-flash"}) != cards[uid]["qwen_request_sha256"]:
            raise ValueError(f"Model replacement changed other inputs: {uid}")
    if seen != set(cards):
        raise ValueError("Live request list differs from the panel")


def add_pair(counter, candidate, reference):
    counter["assigned"] += 1
    if not candidate or not reference or not candidate.get("match") or not reference.get("match"):
        counter["missing"] += 1
        return
    a, b = candidate["match"], reference["match"]
    if a["positions"] != b["positions"]:
        raise ValueError("Position counts differ")
    counter.update({"paired": 1, "positions": a["positions"], "candidate": a["matched"],
                    "reference": b["matched"], "wins": a["matched"] > b["matched"],
                    "losses": a["matched"] < b["matched"], "ties": a["matched"] == b["matched"]})
    for field in ("OPB", "UPB", "FM"):
        if candidate.get(field) is not None and reference.get(field) is not None:
            counter.update({f"{field}_pairs": 1, f"candidate_{field}": candidate[field],
                            f"reference_{field}": reference[field]})


def summarize(cards):
    out = read(OUT / "RESULTS.json")
    reference = {(r["uid"], r["method"]): r["native_fields"] for r in read(
        HERE.parent / "rpeval_formal_multi_coverage_v1" / "RESULT_ROWS.json")
        if r["uid"] in cards and r["method"] in REFERENCES}
    pairs = defaultdict(Counter)
    for row in out["rows"]:
        uid = row["uid"]
        card = cards[uid]
        candidate, base = row["score"], card["base_grade"]
        group = "prior_group" if card["prior_backbone_group"] else "new_to_backbone"
        for key in ("all", card["stratum"], group):
            add_pair(pairs[key], candidate, base)
        for method in REFERENCES:
            add_pair(pairs[method], candidate, reference.get((uid, method)))
    ledger = out["ledger"]
    return {"comparisons": pairs, "statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum((r["usage"] or {}).get("total_tokens") is None for r in ledger)}


if __name__ == "__main__":
    roster = read(HERE / "RPE_FIXED_ROUTE_ACTOR_PANEL.json")["cases"]
    cards = {row["uid"]: row for row in roster}
    check_inputs(cards)
    if (OUT / "RESULTS.json").is_file():
        print(json.dumps(summarize(cards), indent=2, sort_keys=True))
    else:
        print(f"Verified {len(cards)} Actor requests changing only the model alias.")
