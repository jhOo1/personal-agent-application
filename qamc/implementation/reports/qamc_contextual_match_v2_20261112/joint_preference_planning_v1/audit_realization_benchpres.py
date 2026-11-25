"""Localize BenchPreS outputs relative to the exact realized Actor evidence."""
from collections import Counter
import json

from qamc.common import sha

import run_realization_transfer as run


def audit():
    folder = run.OUT / "BenchPreS"
    state = run.read(folder / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("BenchPreS has not settled")
    saved = run.read(folder / "SETTLED.json")
    roots = {r["uid"]: r for r in run.development_roots("BenchPreS")}
    wires = {sha(unit["request"]): unit["request"] for unit in run.read(folder / "Actor_MANIFEST.json")["units"]}
    records, totals = [], Counter()
    for row in saved["rows"]:
        if row["method"] != run.MAIN_ONLY or row["score"] is None:
            continue
        uid = row["uid"]
        root = roots[uid]
        view = json.loads(wires[row["actor_sha256"]]["messages"][1]["content"])
        original = {m["memory_id"]: m["text"] for m in root["original_sources"]}
        shown = {m["memory_id"]: m["text"] for m in view["source_evidence"]}
        selector = saved["selector"][uid]
        licensed = {edge["memory_id"] for edge in selector["uses"]}
        if shown != {mid: value for mid, value in original.items() if mid in licensed}:
            raise ValueError("Actor-visible originals differ from the accepted licenses")
        counts = Counter()
        decisions = []
        for score in row["score"]["decisions"]:
            text = score["preference"]
            exact = [mid for mid, card in original.items() if card == text]
            visibility = "visible" if any(mid in shown for mid in exact) else "excluded" if exact else "no_exact_candidate"
            counts[score["appropriate"], score["label"], visibility] += 1
            decisions.append({**score, "visibility": visibility, "exact_memory_ids": exact})
        yes = sum(n for (appropriate, label, _), n in counts.items() if appropriate and label == "follow")
        no = sum(n for (appropriate, label, _), n in counts.items() if not appropriate and label == "follow")
        if (yes, no) != (row["score"]["aar_numerator"], row["score"]["mr_numerator"]):
            raise ValueError("Visibility attribution changed the native denominator or numerator")
        totals.update(counts)
        records.append({"uid": uid, "actor_sha256": row["actor_sha256"], "visible_ids": list(shown),
                        "decisions": decisions})
    return {"assigned": saved["assigned"], "valid": len(records),
            "visibility_counts": {"/".join(map(str, key)): value for key, value in sorted(totals.items())},
            "cases": records, "new_model_calls": 0, "scores_modified": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
