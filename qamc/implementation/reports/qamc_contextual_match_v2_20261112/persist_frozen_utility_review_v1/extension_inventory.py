"""Find reusable selected answers and as-yet-unallocated exact full-history wires."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path
import subprocess

from qamc.common import sha

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
BU = "beneficial_memory_usage"


def matching_manifests(uids):
    """Find known development manifests containing these already-exposed task IDs."""
    query = ["rg", "-l", "-F", "-g", "*MANIFEST.json",
             "-g", "!**/*seal*/**", "-g", "!**/*holdout*/**", "-g", "!**/*confirm*/**"]
    for uid in sorted(uids):
        query.extend(["-e", uid])
    output = subprocess.run([*query, "runs", "reports"], cwd=ROOT, text=True, capture_output=True)
    if output.returncode not in (0, 1):
        raise RuntimeError(output.stderr)
    return [ROOT / p for p in sorted(output.stdout.splitlines())]


def prepare():
    archive = run_path(str(BASE / "persist_author_score_bridge_v1/check.py"))
    latest = run_path(str(BASE / "persist_equal_cap_development_v1/run_bu.py"))
    pin, api, _, _, _, factorial, judge, bounds = latest["prepare"]()
    if pin != latest["read"](latest["RUN"] / "FROZEN.json"):
        raise ValueError("Existing utility panel drift")
    selected, controls, answers, cases = archive["checked_answers"]()
    historical = {uid for uid, (category, _) in selected.items()
                  if category == BU and "PB_GEPA" in controls[uid]}
    factorial_plan = archive["read"](ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    possible = historical - pin["cohort"].keys() - factorial_plan["jobs"].keys()
    old_groups = {cases[u]["group_id"] for u in pin["cohort"]}
    if len(possible) != 5 or len({cases[u]["group_id"] for u in possible} - old_groups) != 5:
        raise ValueError("Expected five distinct exposed groups absent from the newer utility roster")
    transfer_plan = archive["read"](api["transfer"].OUT / "PLAN.json")
    full, public, route, memberships = {}, {}, {}, {}
    for uid in sorted(possible):
        case = cases[uid]
        task = api["persist"].author.parent.smoke.task_for(case)
        public[uid] = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public[uid]) != case["public_sha256"]:
            raise ValueError("Exposed query or original candidate memory differs")
        full[uid] = api["actor_request"](case, task.query, public[uid]["memories"], factorial,
                                        factorial["prompts"]["gepa"])
        old = answers[uid, "PB_GEPA"]["actor_request"]
        if full[uid] != dict(old, max_tokens=8192):
            raise ValueError("Archived FULL differs beyond output cap")
        route[uid] = api["input_requests"](case, public[uid], transfer_plan)
        memberships[uid] = cases[uid]["group_id"]
    seen = Counter()
    for path in matching_manifests(possible):
        for entry in archive["read"](path).get("units", []):
            unit = entry["unit"]
            uid = unit.get("root_id")
            if uid in possible and entry["request"] == full[uid]:
                seen[uid] += 1
    baseline = {}
    history_roots = (*[BASE / "native_residual_v1" / name for name in
                      ("selected_gepa_expansion_v1", "persist_performance_v1")], archive["RUN"])
    for root in history_roots:
        for cell in archive["read"](root / "FinalActor_MANIFEST.json")["units"]:
            unit = cell["unit"]
            uid = unit["root_id"]
            if uid not in possible or unit["method"] != "SELECTED_GEPA":
                continue
            if uid in baseline or cell["request"]["max_tokens"] != 8192:
                raise ValueError("Missing unique selected Actor contract")
            if cell["request"]["messages"][1:] != full[uid]["messages"][1:]:
                raise ValueError("Selected task or history-only rendering contract drift")
            comparables = {key: val for key, val in cell["request"].items() if key != "messages"}
            if comparables != {key: val for key, val in full[uid].items() if key != "messages"}:
                raise ValueError("Selected sampling settings differ")
            picked = [x for x in archive["read"](root / "EvidenceSelect_MANIFEST.json")["units"]
                      if x["unit"]["root_id"] == uid and x["unit"]["method"] == "SELECTED_GEPA"]
            routed = [x for x in archive["read"](root / "QueryRoute_MANIFEST.json")["units"]
                      if x["unit"]["root_id"] == uid and x["unit"]["method"] == "SELECTED_GEPA"]
            if (len(picked) != 1 or picked[0]["request"] not in (route[uid]["style"], route[uid]["grounding"])
                    or len(routed) != 1 or routed[0]["request"] != route[uid]["query"]):
                raise ValueError("Archived selected method has different preparation requests")
            row = answers[uid, "SELECTED_GEPA"]
            if row["actor_status"] != "OK" or not row["answer"] or row["score"] != selected[uid][1]:
                raise ValueError("Archived selected answer or score missing")
            baseline[uid] = {"answer": row["answer"], "score": row["score"],
                             "branch": row["branch"], "actor_sha256": sha(cell["request"])}
    if baseline.keys() != possible:
        raise ValueError("Missing selected side of a potential extension pair")
    summary = {
        "eligible_exposed_groups": len(possible), "groups_with_selected_cache": len(baseline),
        "groups_with_existing_exact_full_manifest": len(seen),
        "no_current_panel_overlap": True, "independent_confirmation": False,
        "full_wire_comparison": "caps only relative to the old FULL archive",
        "selected_actor_caps": Counter(archived_8192=len(baseline)),
        "archived_full_caps": Counter(archived_4096=len(possible)),
        "candidate_join_sha256": sha(sorted((u, memberships[u], baseline[u]["actor_sha256"], sha(full[u]))
                                              for u in possible)),
        "research_calls": 0,
    }
    return summary, api, public, full, baseline, cases, judge, bounds, seen


if __name__ == "__main__":
    print(json.dumps(prepare()[0], indent=2, sort_keys=True))
