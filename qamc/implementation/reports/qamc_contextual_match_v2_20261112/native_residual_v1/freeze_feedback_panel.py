"""Freeze exposed search and group-out panels with baseline headroom."""
import argparse
from collections import Counter
import json

from build_jobs import HERE, archive_inputs
from freeze_roster import RPE_ROUTES, archive
from qamc.common import sha
from summarize_reassembly import measure

PATH = HERE / "FEEDBACK_PANEL.json"
QUOTAS = {"RPEval": (3, 2), "BenchPreS": (1, 2), "PersistBench": (2, 2)}


def panel(wires, cards, routes):
    rows = []
    for benchmark, quota in QUOTAS.items():
        used_groups = set()
        for has_gap, count in zip((True, False), quota):
            candidates = []
            for (name, uid), card in cards.items():
                if name != benchmark or (name, uid) not in wires:
                    continue
                if name == "RPEval" and routes.get(uid) != "REUSE_RP":
                    continue
                score = measure(name, card["stratum"], card["base_score"])
                if score is None or not score["positions"]:
                    continue
                gap = score["primary"] < score["positions"]
                if has_gap and not gap:
                    continue
                order = sha(["feedback-panel-v1", name, card["group"], uid])
                priority = 0 if has_gap else -score["primary"] / score["positions"]
                candidates.append((priority, order, uid, card, gap))
            accepted = 0
            for _, _, uid, card, gap in sorted(candidates):
                group = card["group"]
                if group in used_groups:
                    continue
                used_groups.add(group)
                rows.append({"benchmark": benchmark, "uid": uid, "group": group,
                             "stratum": card["stratum"], "has_gap": gap, "role": "headroom" if has_gap else "protection",
                             "split": ("search", "group_out")[accepted % 2],
                             "answer_sha256": sha(card["base_answer"]),
                             "grade_sha256": sha(card["base_score"]),
                             "actor_sha256": wires[benchmark, uid]["actor_request_sha256"]})
                accepted += 1
                if accepted == 2 * count:
                    break
            if accepted != 2 * count:
                raise ValueError(f"Insufficient groups: {benchmark}/{has_gap}")
    return {"rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check"))
    args = parser.parse_args()
    wires, cards = archive_inputs()
    routes = {row["uid"]: row["old_route"] for row in archive.read(RPE_ROUTES)["rows"]}
    result = panel(wires, cards, routes)
    if args.action == "freeze":
        with PATH.open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    elif result != archive.read(PATH):
        raise ValueError("Feedback panel drift")
    print(Counter((row["benchmark"], row["split"], row["has_gap"]) for row in result["rows"]))
