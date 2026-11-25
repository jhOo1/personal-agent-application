"""Count potential exact-label changes from saved selectors, in evaluation only."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha

import run_visibility_v42 as study
from settle_visibility_v42 import stable_prefix


def source_levels(ids, scope):
    levels = dict.fromkeys(ids, "A")
    for use in scope:
        mid = use["memory_id"]
        levels[mid] = max(levels[mid], use["level"])
    return levels


def policy_only_request(root, edits):
    request = root["archived_actor_request"]
    system, user = request["messages"]
    payload = json.loads(user["content"])
    original = payload["preference_use_policy"]
    levels = {item["memory_id"]: item["policy"] for item in original}
    if (sha(request) != root["archived_actor_sha256"]
            or json.dumps(payload, ensure_ascii=False) != user["content"]
            or payload != {**root["public_task"], "source_evidence": root["original_sources"],
                           "preference_use_policy": root["archived_policy"]}):
        raise ValueError("Archived RP request identity changed")
    if edits.keys() - levels.keys() or set(edits.values()) - {"A", "B", "C"}:
        raise ValueError("Unknown source or policy level")
    revised = [{**item, "policy": edits.get(item["memory_id"], item["policy"])} for item in original]
    new_payload = {**payload, "preference_use_policy": revised}
    modified = {**request, "messages": [
        system, {**user, "content": json.dumps(new_payload, ensure_ascii=False)}
    ]}
    validate_public_request(modified)
    return modified


def audit(expected):
    frozen = study.read(study.OUT / "FROZEN.json")
    if frozen != study.prepare():
        raise ValueError("Actor or candidate freeze changed")
    prefix = stable_prefix(frozen)
    settled = sum(wave["roots"] for wave in prefix)
    if expected != settled:
        raise ValueError(f"Expected {expected} settled roots, found {settled}")
    archived = {r["uid"]: r for r in study.read(study.prior.OUT / "FROZEN.json")["roots"]}
    counts, groups = defaultdict(Counter), defaultdict(set)
    changed_roots, change_wires = defaultdict(set), defaultdict(set)
    common_roots = 0
    for wave in prefix:
        name = f"wave_{wave['wave']:02d}"
        path = study.OUT / name / "COMPLETED.json"
        if sha(path.read_bytes()) != wave["sha256"]:
            raise ValueError("Settled wave changed")
        for row in study.read(path)["rows"]:
            scopes = {method: item["scope"] for method, item in row["selected"].items()}
            if any(scope is None for scope in scopes.values()):
                continue
            common_roots += 1
            root = archived[row["uid"]]
            original = {p["memory_id"]: p["policy"] for p in root["archived_policy"]}
            ids = [m["memory_id"] for m in root["original_sources"]]
            if list(original) != ids or row["group"] != root["group"]:
                raise ValueError("Mismatch in archived preference identities or group")
            direct = source_levels(ids, scopes["DIRECT"])
            scoped = source_levels(ids, scopes["SCOPED"])
            proposals = {mid: direct[mid] for mid in ids
                         if direct[mid] == scoped[mid] and direct[mid] != original[mid]}
            edits_by_transition = defaultdict(dict)
            for mid, proposed in proposals.items():
                edits_by_transition[original[mid] + "→" + proposed][mid] = proposed
            for transition, edits in {"any": proposals, **edits_by_transition}.items():
                if edits:
                    wire = policy_only_request(root, edits)
                    changed_roots[transition].add(row["uid"])
                    change_wires[transition].add(sha(wire))
            subset = "all_A" if set(row["labels"]) == {"A"} else "contains_BC"
            for mid, author in zip(ids, row["labels"], strict=True):
                if mid not in proposals:
                    continue
                old, proposed = original[mid], proposals[mid]
                # The proposed edit above depends only on three saved policy predictions.
                # Author labels below are available only to the evaluation.
                action = old + "→" + proposed
                for stratum in ("all", subset):
                    for key in ((stratum, "any"), (stratum, action)):
                        counter = counts[key]
                        counter["proposals"] += 1
                        counter["corrected"] += int(author == proposed)
                        counter["regressed"] += int(author == old)
                        counter["both_wrong"] += int(author not in (old, proposed))
                        counter["erased_author_BC"] += int(author in "BC" and proposed == "A")
                        groups[key].add(row["group"])
    if stable_prefix(frozen) != prefix:
        raise ValueError("New wave settled during audit")
    return {"settled": settled, "common_selector_roots": common_roots, "physical_calls": 0,
            "by_predicted_transition": {
                f"{subset}/{action}": {**counter, "source_groups": len(groups[subset, action])}
                for (subset, action), counter in counts.items()},
            "policy_only_wire_preflight": {
                action: {"affected_roots": len(changed_roots[action]), "unique_actor_requests": len(wires)}
                for action, wires in change_wires.items()},
            "interpretation": "Policy-label diagnostic only. No edited answer was generated or scored."}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=int, required=True)
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.expected), ensure_ascii=False, indent=2))
