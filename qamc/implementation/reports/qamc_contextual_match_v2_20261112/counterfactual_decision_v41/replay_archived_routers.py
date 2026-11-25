"""Measure exact no-history rerouting using only pre-existing selector evidence."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

from score_task_only import OUT, READ, v41

C5 = "GOAL_EFFECT_GEPA"


def evidence_count(archived, sources):
    wire, view = archived["actor_request"], archived["view"]
    if archived["actor_status"] != "OK" or sha(wire) != archived["actor_request_sha256"]:
        raise ValueError("Cannot infer an empty view without a verified Actor request")
    system, user = wire["messages"]
    raw = view["source_evidence"]
    expected_block = "<memories>\n" + "\n".join(f"- {item['text']}" for item in raw) + "\n</memories>"
    payload = json.loads(user["content"])
    if not system["content"].endswith(expected_block + "\n") or any(
        payload[name] != view[archived_name] for name, archived_name in (
            ("query", "query"), ("current_context", "current_context"), ("fixed_facts", "facts")
        )
    ):
        raise ValueError("The saved view differs from the actual GEPA request")
    n = len(raw)
    if n == 0:
        if payload.get("selected_memory_use_guidance") or view["memory_use_instructions"]:
            return None
        messages = [entry["content"] for entry in wire["messages"]]
        if any(source["text"] in text or json.dumps(source["text"], ensure_ascii=False)[1:-1] in text
               for source in sources for text in messages):
            return None
    return n


def audit():
    prior = READ(v41.OUT / "FROZEN.json")
    score = READ(OUT / "RESULTS.json")
    if score["state"]["state"] != "COMPLETE":
        raise ValueError("The common no-history control must be terminal")
    roots = {row["uid"]: row for row in prior["roots"]}
    by_uid = {row["uid"]: row for row in score["roots"]}
    archived = {(row["uid"], row["method"]): row for row in READ(v41.formal.OUT / "RESULT_ROWS.json")
                if row["uid"] in roots and row["method"] in (v41.GATE, C5)}
    scores, details = defaultdict(Counter), []
    switched_groups = defaultdict(set)
    for uid, root in roots.items():
        row = by_uid[uid]
        labels = row["labels"]
        group = root["group"]
        scopes = ("all", "all_A" if set(labels) == {"A"} else "contains_BC",
                  "less_exposed" if root["in_sensitivity"] else "additional_groups")
        counts = {m: evidence_count(archived[uid, m], root["original_sources"]) for m in (v41.GATE, C5)}
        routes = {
            "RP_all_A": all(policy["policy"] == "A" for policy in root["archived_policy"]),
            "Gate_empty": counts[v41.GATE] == 0,
            "C5_empty": counts[C5] == 0,
        }
        old = root["archived"][v41.RP]["fields"].get("match")
        task = row["task_only"]["fields"].get("match")
        drift = task["matched"] - old["matched"] if old and task else None
        unverifiable = {"Gate_empty": counts[v41.GATE] is None, "C5_empty": counts[C5] is None}
        for method, switch in routes.items():
            for scope in scopes:
                line = scores[method, scope]
                line.update(planned=1, switched=switch)
                if unverifiable.get(method, False):
                    line["unverified_empty"] += 1
                if drift is not None:
                    line.update(pairs=1, positions=len(labels), RP_match=old["matched"],
                                switched_paired=switch, match_gain=drift if switch else 0,
                                switch_wins=int(switch and drift > 0),
                                switch_losses=int(switch and drift < 0))
                    if switch:
                        switched_groups[method, scope].add(group)
        details.append({"uid": uid, "group": group, "labels": labels, "counts": counts,
                        "switches": routes, "task_only_minus_RP_match": drift})
    return {
        "rows": details, "new_generation": 0, "new_scoring": 0,
        "tables": {method: {scope: {**counts, "switched_pair_source_groups": len(switched_groups[method, scope])}
                            for (name, scope), counts in scores.items() if name == method}
                   for method in ("RP_all_A", "Gate_empty", "C5_empty")},
        "interpretation": ("Select between saved RP and task-only answers, using only the existing method's "
                           "empty evidence output. This describes a routing component, not a new E2E score. "
                           "A live composition would also pay for all necessary preparation stages. "
                           "Literal absence is not a semantic proof of no indirect history."),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
