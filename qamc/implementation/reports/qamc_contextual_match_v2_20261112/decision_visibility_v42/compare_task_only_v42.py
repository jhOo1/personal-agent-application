"""Join actual V42 answers and the exact inherited task-only reference."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_visibility_v42 as runner
from score_task_only import OUT as TASK_ONLY, saved_drafts

FULL, MASK, DIRECT, ZERO = "SCOPED_FULL", "SCOPED_MASKED", "DIRECT_MASKED", "TASK_ONLY"
ARMS = (ZERO, FULL, MASK, DIRECT, runner.prior.RP, runner.prior.GATE)


def analyze():
    plan = runner.read(runner.OUT / "FROZEN.json")
    if plan != runner.prepare():
        raise ValueError("Live experiment differs from its freeze")
    archive = runner.read(runner.prior.OUT / "FROZEN.json")
    roots = {row["uid"]: row for row in archive["roots"]}
    drafts = saved_drafts(archive)
    controls = runner.read(TASK_ONLY / "RESULTS.json")
    task_only = {row["uid"]: row for row in controls["roots"]}
    if controls["state"]["state"] != "COMPLETE" or task_only.keys() != roots.keys():
        raise ValueError("Task-only endpoint is incomplete or on another cohort")
    subsets, audit = defaultdict(list), Counter()
    empty_scoped = Counter()
    rows = []
    for index, uids in enumerate(plan["waves"]):
        path = runner.OUT / f"wave_{index:02d}" / "COMPLETED.json"
        if not path.exists():
            break
        batch = runner.read(path)["rows"]
        if [row["uid"] for row in batch] != uids:
            raise ValueError("Frozen wave membership changed")
        for row in batch:
            uid, labels, root = row["uid"], row["labels"], roots[row["uid"]]
            control = task_only[uid]
            if control["labels"] != labels or control["group"] != row["group"]:
                raise ValueError("Task-only and V42 label or group mismatch")
            if sha(runner.prior.task_only_request(root)) != root["task_wire_sha256"]:
                raise ValueError("Task-only Actor input changed")
            row["native"][ZERO] = control["task_only"]
            rows.append(row)
            all_a = set(labels) == {"A"}
            subsets["all"].append(row)
            subsets["all_A" if all_a else "mixed_BC"].append(row)
            if row["in_sensitivity"]:
                subsets["less_exposed"].append(row)
            permissions = row["selected"]["SCOPED"]["scope"]
            if permissions is None:
                audit["unavailable_scoped_selection"] += 1
                continue
            key = ("all_A" if all_a else "mixed_BC") + ("_nonempty" if permissions else "_empty")
            subsets[key].append(row)
            if permissions:
                continue
            family = "all_A" if all_a else "mixed_BC"
            empty_scoped[family + "/roots"] += 1
            wire = root["task_wire_sha256"]
            masked = row["answers"][MASK]
            if masked.get("request_sha256") != wire or masked["answer"] != drafts[wire]["answer"]:
                raise ValueError("Same empty-scope Actor request returned different archived text")
            if (control["task_only"]["raw"] != row["native"][MASK]["raw"]
                    or control["task_only"]["fields"] != row["native"][MASK]["fields"]):
                raise ValueError("Same archived empty-scope answer did not reuse the score")
            audit["empty_mask_actor_and_grade_identity"] += 1
            if "match" in control["task_only"]["fields"]:
                empty_scoped[family + "/valid_native_match"] += 1
    summary = {}
    for name, items in subsets.items():
        # Preserve the same denominator for every reported arm in the joint table.
        entire = [row for row in items if all("match" in row["native"][m]["fields"]
                                             for m in (ZERO, FULL, MASK))]
        summary[name] = {
            "expected_roots": len(items),
            "common_zero_full_mask": {"roots": len(entire), "positions": sum(row["positions"] for row in entire),
                                      "score": {m: sum(row["native"][m]["fields"]["match"]["matched"] for row in entire)
                                                for m in (ZERO, FULL, MASK)}},
            "paired": {m: runner.paired(items, ZERO, m) for m in ARMS[1:]},
        }
    return {
        "completed_roots": len(rows), "same_frozen_roots": sum(map(len, plan["waves"])),
        "empty_scoped_identity": audit, "empty_scoped_by_author_group": empty_scoped, "results": summary,
        "model_calls": 0,
        "semantics": ("Use already observed task-only generation. The task-only versus nonempty scoped "
                      "contrast changes the policy and evidence together. Author-label subsets are "
                      "diagnostic and must not be used as a deployed router."),
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
