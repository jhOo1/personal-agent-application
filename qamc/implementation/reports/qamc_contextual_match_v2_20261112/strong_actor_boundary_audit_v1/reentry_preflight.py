"""Freeze equivalent-history test inputs without reading hidden confirmation data."""
from collections import Counter
import json

from qamc.common import sha

from census import BASE, HERE, prior, read


def verified_pairs():
    archive = prior.R["archived"]
    frozen = read(archive.v41.OUT/"FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Not an exposed development archive")
    index = {row["uid"]: row for row in frozen["roots"]}
    inventory = read(BASE/"soft_only_nested_contrasts_v1/PAIRS.json")
    # Verify author classes only offline, before constructing any condition.
    author = {row["uid"]:row["labels"] for row in read(
        BASE/"counterfactual_rpeval_v41_task_only/RESULTS.json")["roots"]}
    ready = []
    for spec in inventory["pairs"]:
        a,b = (index[spec[name]] for name in ("all_A","only_B_added"))
        if a["public_task"] != b["public_task"] or a["group"] != b["group"] or a["group"] != spec["root"]:
            raise ValueError("Different task or source group")
        a_wire,b_wire = archive.v41.task_only_request(a),archive.v41.task_only_request(b)
        if a_wire != b_wire or sha(a_wire) != spec["task_hash"]:
            raise ValueError("Task-only anchor wire drift")
        histories_a, histories_b = (root["original_sources"] for root in (a,b))
        common = {s["text"] for s in histories_a}
        if len(common) != len(histories_a) or set(author[a["uid"]]) != {"A"}:
            raise ValueError("Unexpected shared classes or duplicate text")
        added = [s for s, label in zip(histories_b,author[b["uid"]],strict=True) if s["text"] not in common]
        if [s["memory_id"] for s in added] != spec["added_B_ids"]:
            raise ValueError("Soft-only additions do not align")
        for s,label in zip(histories_b,author[b["uid"]],strict=True):
            if label != ("A" if s["text"] in common else "B"):
                raise ValueError("The richer variant changed an existing class")
        full = {s["text"]:s for s in histories_b}
        if len(full)!=len(histories_b) or not common.issubset(full):
            raise ValueError("History variants do not nest")
        # Preserve shared texts, their original order and IDs. Use a new identifier
        # only for genuinely added rows, so checking source membership is possible.
        shared = [dict(r) for r in histories_a]
        ids = {r["memory_id"] for r in shared}
        additions = []
        for i,r in enumerate(added):
            ident = f"NEW{i+1}"
            if ident in ids:
                raise ValueError("New history identifier overlaps an existing one")
            additions.append({**r,"memory_id":ident})
        condition_a = {"task":a["public_task"],"sources":shared}
        condition_b = {"task":a["public_task"],"sources":[*shared,*additions]}
        ready.append({"group":spec["root"],"original_uids":[a["uid"],b["uid"]],
                      "task_wire_sha256":sha(a_wire),"shared_positions":len(shared),"added_positions":len(added),
                      "actual_native_orders_same":spec["shared_order_fixed"],
                      "shared_condition_sha256":sha(condition_a),"extended_condition_sha256":sha(condition_b),
                      "protected_legacy_match_gain_counts":{
                          method:bool(row["core_protected_match_gain"])
                          for method,row in spec["reuse_delta_on_B"].items()}})
    return {"conditions_topology":"fixed task and old-source order, append only original new texts",
            "kind":"controlled diagnosis; published/native variant scores remain separate",
            "n":len(ready),"groups":len({r["group"] for r in ready}),
            "shared_positions":sum(r["shared_positions"] for r in ready),
            "added_positions":sum(r["added_positions"] for r in ready),
            "supported_archived_substitutions":dict(Counter(m for r in ready
                 for m,p in r["protected_legacy_match_gain_counts"].items() if p)),
            "rows":ready}


if __name__ == "__main__":
    print(json.dumps(verified_pairs(),ensure_ascii=False,indent=2))
