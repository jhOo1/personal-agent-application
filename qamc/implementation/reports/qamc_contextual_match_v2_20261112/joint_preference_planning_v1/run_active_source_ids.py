"""Compare two archived admissions with exactly the same visible history."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

from planning import request
import run_outcome_contract as outcome
from settle_joint_planning import score_matrix, usage
from task_conditioned_value import ACTOR_BASE, BUDGET
from thinking_budget_transport import controlled_wire
from transaction_text_wire import ordinary_answer


OUT = outcome.OUT.with_name("active_source_ids_rpeval_v1")
RUN = outcome.RUN.with_name(OUT.name)
V42 = outcome.OUT.with_name("decision_visibility_rpeval_v42")
OLD, NEW = "OLD_ADMISSION", "NEW_ADMISSION"
ARMS = OLD, NEW
ACTOR, JUDGE = "ActiveIdsActor", outcome.JUDGE
probe, read, replay = outcome.probe, outcome.read, outcome.replay
scorer, runner = outcome.parent.SCORER, outcome.parent.previous

PROMPT = ACTOR_BASE + """
The packet includes a task-only draft. Use it as a starting point and edit it as needed
to produce a complete answer. The active_memory_ids list is the full set of historical
sources eligible to influence the answer. Use historical evidence only from those
sources, under their original conditions. Treat the other history as inactive.
Prioritize the current task. Verify task-specific external assertions such as a named
venue's opening or reservation policy against the supplied original facts. When no
supplied fact establishes an assertion, present it as uncertain or a specific check,
with a practical alternative when useful. A draft or history is not evidence of a
current external fact. An empty active_memory_ids list leaves the task and facts
available to answer the question."""

METRICS = ("OPB", "UPB", "FM", "VG", "full_match")


def old_v42_masks(uids):
    masks = {}
    for path in sorted(V42.glob("wave_*/COMPLETED.json")):
        for row in read(path)["rows"]:
            uid = row["uid"]
            if uid not in uids:
                continue
            if uid in masks:
                raise ValueError("Duplicate V42 source history")
            masks[uid] = {}
            for arm in ("DIRECT", "SCOPED"):
                prediction = row["selected"][arm]
                if prediction["status"] == "OK" and prediction["scope"] is not None:
                    ids = sorted({use["memory_id"] for use in prediction["scope"]})
                    masks[uid][arm] = {"ids": ids, "sha256": sha(ids)}
    return masks


def audit_admissions(masks, v42):
    audit = {}
    for uid, assignments in masks.items():
        archived = v42.get(uid, {})
        audit[uid] = {
            "current": {arm: sha(ids) for arm, ids in assignments.items()},
            "v42": archived,
            "matches": {arm: [key for key, mask in archived.items() if mask["ids"] == ids]
                        for arm, ids in assignments.items()},
        }
    changed = [uid for uid, pair in masks.items() if pair[OLD] != pair[NEW]]
    for left, right in (("DIRECT", "SCOPED"), ("SCOPED", "DIRECT")):
        if all(left in audit[uid]["matches"][OLD] and right in audit[uid]["matches"][NEW] for uid in changed):
            raise ValueError("The treatment masks repeat V42")
    return audit


def actor_request(root, state, ids):
    available = [source["memory_id"] for source in root["original_sources"]]
    if len(available) != len(set(available)) or ids != sorted(set(ids)) or not set(ids) <= set(available):
        raise ValueError("Invalid source ID list")
    packet = {"task": root["public_task"], "task_choices": state["contract"],
              "task_only_draft": state["draft"], "source_evidence": root["original_sources"],
              "active_memory_ids": ids}
    return controlled_wire(request(packet, PROMPT, 8192), BUDGET)


def prepare():
    initial, _, roots, history, data, inherited = outcome.prepare()
    rows, _, _ = data
    alignment = read(outcome.OUT / "BINDING_COMPARISON.json")
    masks = {row["uid"]: {OLD: row["old"], NEW: row["new"]} for row in alignment["rows"]}
    if (len(rows) != 55 or len(masks) != 51 or not masks.keys() <= rows.keys()
            or sum(pair[OLD] == pair[NEW] for pair in masks.values()) != 13):
        raise ValueError("Unexpected development cohort")
    audit = audit_admissions(masks, old_v42_masks(masks))
    for uid, pair in masks.items():
        known = {source["memory_id"] for source in roots[uid]["original_sources"]}
        if any(not set(saved["ids"]) <= known for saved in audit[uid]["v42"].values()):
            raise ValueError("V42 and current source IDs differ")
    jobs = [(uid, arm, actor_request(roots[uid], history[uid], ids))
            for uid, pair in masks.items() for arm, ids in pair.items()]
    cache = {ACTOR: {}, JUDGE: dict(inherited[JUDGE])}
    for base in (outcome.OUT, outcome.OUT / "item_header_recovery", *sorted(V42.glob("wave_*"))):
        if base.parent != V42 and read(base / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Prior score receipts are unsettled")
        # Reuse only exact request hashes through the existing dispatcher.
        cache[JUDGE].update(read(base / f"{JUDGE}_EXACT.json"))
        actor_path = base / "Actor_EXACT.json"
        if actor_path.exists():
            cache[ACTOR].update(read(actor_path))
    paths = (Path(__file__), Path(__file__).with_name("ACTIVE_SOURCE_IDS_PROTOCOL.md"))
    spec = {"panel": "pilot", "caps": {ACTOR: 89, JUDGE: 89}, "assigned": sorted(rows),
            "alignment": audit, "admission_sha256": sha(alignment),
            "request_sha256": {uid: {} for uid in masks},
            "service_reference_sha256": initial["service_reference_sha256"], "parent_sha256": sha(initial),
            "cache_sha256": {stage: sha(receipts) for stage, receipts in cache.items()},
            "code_sha256": {path.name: sha(path.read_bytes()) for path in paths},
            "coverage": .90, "minimum_positive_source_groups": 2,
            "automatic_retries": 0, "independent_confirmation": False}
    for uid, arm, wire in jobs:
        spec["request_sha256"][uid][arm] = sha(wire)
    return spec, jobs, roots, masks, data, cache


def check(inputs):
    spec, jobs, roots, masks, _, _ = inputs
    wires = {(uid, arm): wire for uid, arm, wire in jobs}
    for uid, pair in masks.items():
        stripped = []
        for arm in ARMS:
            wire = deepcopy(wires[uid, arm])
            payload = json.loads(wire["messages"][1]["content"])
            if (payload.pop("active_memory_ids") != pair[arm]
                    or payload["source_evidence"] != roots[uid]["original_sources"]
                    or payload["task"] != roots[uid]["public_task"]):
                raise ValueError("The common actor packet has changed")
            wire["messages"][1]["content"] = payload
            stripped.append(wire)
        if stripped[0] != stripped[1]:
            raise ValueError("The actor wires differ outside active source IDs")
    if len({sha(wire) for _, _, wire in jobs}) != 89:
        raise ValueError("Expected 89 unique actor inputs across both arms")
    print(json.dumps({"assigned": len(spec["assigned"]), "eligible": len(masks),
                      "changed_masks": sum(p[OLD] != p[NEW] for p in masks.values()), "caps": spec["caps"],
                      "v42_overlaps": Counter(f"{arm}/{old}" for entry in spec["alignment"].values()
                                              for arm, matches in entry["matches"].items() for old in matches),
                      "physical_requests": 0}))


def evaluate(inputs, stage):
    _, jobs, _, masks, (rows, official, cases), _ = inputs
    responses, scoring = stage(ACTOR, jobs), []
    for uid, row in rows.items():
        row.update(actor={}, outputs={}, active_memory_ids=masks.get(uid))
        for arm in ARMS:
            row["native"][arm] = {"status": "NO_PAIRED_ADMISSION", "fields": {}}
    for uid, arm, wire in jobs:
        receipt, raw = responses[uid, arm]
        row = rows[uid]
        trace = {"status": receipt["status"], "request_sha256": sha(wire)}
        row["actor"][arm] = trace
        if receipt["status"] == "OK":
            try:
                answer = ordinary_answer(raw)
            except ValueError:
                trace["status"] = "INVALID_ACTOR_TEXT"
            else:
                row["outputs"][arm] = answer
                scoring.append((uid, arm, scorer.grade_request(official, cases[uid], answer)))
        row["native"][arm]["status"] = trace["status"]
    for (uid, arm), (receipt, raw) in stage(JUDGE, scoring).items():
        rows[uid]["native"][arm] = scorer.parse_grade(receipt, raw, rows[uid]["positions"])
    return {}, list(rows.values())


def summarize(spec, _, rows, ledger):
    eligible = [row for row in rows if row["active_memory_ids"] is not None]
    changed = [row for row in eligible if row["active_memory_ids"][OLD] != row["active_memory_ids"][NEW]]
    panels = {"all_assigned": rows, "eligible": eligible, "changed": changed,
              "same_mask": [row for row in eligible if row not in changed]}
    for name, predicate in {
        "all_A": lambda labels: set(labels) == {"A"},
        "B_only": lambda labels: "B" in labels and "C" not in labels,
        "contains_C": lambda labels: "C" in labels,
    }.items():
        panels[name] = [row for row in eligible if predicate(row["labels"])]
        panels[f"changed_{name}"] = [row for row in changed if predicate(row["labels"])]

    def compare(panel, left):
        paired = [row for row in panel if all(row["native"][arm]["fields"].get("match") for arm in (left, NEW))]
        return {"match": replay.paired(panel, left, NEW),
                **{metric: scorer.comparisons.grade_pair(paired, left, NEW, metric) for metric in METRICS}}

    paired = {name: {arm: compare(panel, arm) for arm in (OLD, outcome.GATE, outcome.RP)}
              for name, panel in panels.items()}
    group_delta = defaultdict(int)
    for row in changed:
        old, new = (row["native"][arm]["fields"].get("match") for arm in ARMS)
        if old and new:
            group_delta[row["group"]] += new["matched"] - old["matched"]

    def satisfies(panel, field, *, direction, strictly=False):
        score = paired[panel][OLD][field]
        n = score.get("n", score.get("valid_cases", 0))
        delta = score.get("delta", score.get("match_delta"))
        sufficient = n >= spec["coverage"] * len(panels[panel])
        return sufficient and delta is not None and (direction * delta > 0 if strictly else direction * delta >= 0)

    screen = {"match_gain": satisfies("eligible", "match", direction=1, strictly=True),
              "lower_all_A_OPB": satisfies("all_A", "OPB", direction=-1, strictly=True),
              "B_only_match_preserved": satisfies("B_only", "match", direction=1),
              "B_only_UPB_preserved": satisfies("B_only", "UPB", direction=-1),
              "C_match_preserved": satisfies("contains_C", "match", direction=1),
              "C_UPB_preserved": satisfies("contains_C", "UPB", direction=-1),
              "C_FM_preserved": satisfies("contains_C", "FM", direction=-1),
              "overall_full_match_preserved": satisfies("eligible", "full_match", direction=1),
              "overall_vagueness_preserved": satisfies("eligible", "VG", direction=-1),
              "multiple_positive_source_groups": sum(delta > 0 for delta in group_delta.values())
              >= spec["minimum_positive_source_groups"]}
    return {"screen": screen, "pass": all(screen.values()), "group_match_count_delta": dict(group_delta),
            "paired": paired,
            "common": {name: score_matrix(panel, (*ARMS, outcome.GATE, outcome.RP))
                       for name, panel in panels.items()},
            "actor_status_counts": {arm: Counter(row["actor"].get(arm, {}).get("status", "NO_PAIRED_ADMISSION")
                                                for row in rows) for arm in ARMS},
            "native_status_counts": {arm: Counter(row["native"][arm]["status"] for row in rows) for arm in ARMS},
            "ledger": {stage: usage([record for record in ledger if record["unit"]["stage"] == stage])
                       for stage in spec["caps"]}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    action = parser.parse_args().action
    inputs = prepare()
    if action in ("check", "freeze"):
        check(inputs)
        if action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
        return
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT
    with (probe.runner_lock(RUN / "runner.lock"), patch.object(runner, "OUT", OUT),
          patch.object(runner, "evaluate", evaluate), patch.object(runner, "summarize", summarize)):
        state = OUT / "RUN_STATE.json"
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            runner.execute(inputs, live=True)
        elif action == "verify":
            if not done:
                raise ValueError("Comparison has not settled")

            def same(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Replay changed {path.name}")

            with patch.object(probe, "freeze", same):
                runner.execute(inputs, live=False)
            print(json.dumps({"verified": True, "physical_requests": 0}))


if __name__ == "__main__":
    main()
