"""Score-envelope verified answer-pool ceiling on the exposed PersistBench roster."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
RESIDUAL = BASE / "native_residual_v1"
sys.path.insert(0, str(RESIDUAL))

from transfer_replay import persist, saved_scores, RUNS
from audit_persist_switch_receipts import normalized
from qamc.common import sha

AUTHOR = BASE / "persist_author_controls_v2" / "waves"
EXTERNAL = ("persist_memadapter_alignment_v1",)
EXPOSURE = ("selected_gepa_expansion_v1", "persist_performance_v1",
            "persist_switch_execution_v1", "selected_rubric_exposure_v1")
GENERATION = ("persist_criteria_v1", "persist_query_premise_v1")
FACTORIAL = ROOT / "reports/qamc_persistbench_actor_factorial"
STANCE = ROOT / "runs" / BASE.name / "persist_counterfactual_stance_v1"


def read(path):
    return json.loads(path.read_text())


def passes(score, track):
    return not score["failure_strict_utility" if track == "beneficial_memory_usage" else "failure_release"]


def get_author():
    files = sorted(AUTHOR.glob("[0-9][0-9].json"))
    rows = [r for p in files for r in read(p)["rows"]]
    if len(files) != 13 or len({r["uid"] for r in rows}) != 60:
        raise ValueError("Expected 60 previously exposed author controls")
    if len(rows) != len({(r["uid"], r["method"]) for r in rows}):
        raise ValueError("Duplicate archived control")
    plan_path = AUTHOR.parent / "PLAN.json"
    plan = read(plan_path)
    cases = {c["uid"]: c for c in plan["cases"] if c["role"] == "DEV"}
    ids = {r["uid"] for r in rows}
    if ids != cases.keys():
        raise ValueError("Author manifest and exposed wave roster differ")
    tasks = {uid: persist.author.parent.smoke.task_for(cases[uid]) for uid in ids}
    protocol = plan["protocols"]["gpt41"]
    judge = persist.author.ext.parent.persist
    _, rubrics, formatter = judge.upstream()
    receipts = saved_scores(RUNS / persist.AUTHOR_OUT.name / "gpt41")
    bounds = {}
    for row in rows:
        if not row["score"]:
            continue
        uid, method = row["uid"], row["method"]
        receipt = receipts[uid, method]
        raw = row["raw_scores"][persist.STAGE]
        if raw != receipt["response"]["answer"]:
            raise ValueError("Saved score response mismatch")
        topic = cases[uid]["category"]
        task = tasks[uid]
        wire = persist.author.ext.text_request(
            rubrics[topic], formatter["build_judge_prompt"](
                [m.text for m in task.memories], task.query, row["answer"]),
            protocol["model"], protocol["stages"][persist.STAGE]["max_tokens"])
        if sha(wire) != receipt["request_sha256"] or any(
                row["score"][key] != value for key, value in judge.score(topic, raw).items()):
            raise ValueError(f"Author grader receipt changed: {uid}/{method}")
        envelope = normalized(wire, row["answer"])
        if uid in bounds and envelope != bounds[uid]:
            raise ValueError("Author control scored under different conditions")
        bounds[uid] = envelope
    files.append(plan_path)
    return rows, bounds, files


def supplementary(path, bounds, tally):
    rows_path = path / "RESULTS.json"
    manifest_path = path / "PersistNative_MANIFEST.json"
    wires = {}
    for item in read(manifest_path)["units"]:
        unit = item["unit"]
        key = unit["root_id"], unit["method"].removesuffix("/PersistJudge")
        if key in wires or unit["replicate"] != 0:
            raise ValueError("Expected one saved score request per method and task")
        wires[key] = item["request"]
    out = []
    for row in read(rows_path)["rows"]:
        uid, method = row["uid"], row["method"]
        if uid not in bounds:
            tally["no_author_envelope"] += 1
        elif not row.get("score"):
            tally["missing_score"] += 1
        elif (uid, method) not in wires:
            tally["unbound_or_reused_score"] += 1
        elif normalized(wires[uid, method], row["answer"]) != bounds[uid]:
            tally["different_envelope"] += 1
        else:
            score = row["score"]
            topic = row.get("category") or score.get("category") or row["base_score"]["category"]
            checked = persist.author.ext.parent.persist.score(topic, row["raw_scores"][persist.STAGE])
            if any(score[k] != v for k, v in checked.items()):
                raise ValueError("Stored supplementary rating differs from raw result")
            tally["matched"] += 1
            out.append(row)
    return out, (rows_path, manifest_path)


def factorial(bounds, tally):
    results = FACTORIAL / "PILOT.json"
    manifest = FACTORIAL / "stage_manifests/pilot_Judges.json"
    plan_path = FACTORIAL / "PLAN.json"
    actors = read(plan_path)["jobs"]
    wires = {x["unit"]["root_id"]: x["request"] for x in read(manifest)["units"]
             if x["unit"]["method"] == "SELECTED_GEPA"}
    rows = []
    for row in read(results)["rows"]:
        uid = row["uid"]
        if row["method"] != "SELECTED_GEPA":
            continue
        if uid not in bounds or uid not in wires or not row["score"]:
            tally["unbound_or_reused_score"] += 1
            continue
        if (row["actor_request_sha256"] != sha(actors[uid]["SELECTED_GEPA"]["request"])
                or normalized(wires[uid], row["answer"]) != bounds[uid]):
            raise ValueError("Factorial endpoint does not match the frozen protocol")
        checked = persist.author.ext.parent.persist.score(row["category"], row["judge_raw"])
        if any(row["score"][k] != v for k, v in checked.items()):
            raise ValueError("Factorial grade does not reparse")
        rows.append(row)
        tally["matched"] += 1
    return rows, (results, manifest, plan_path)


def audit():
    author, envelopes, files = get_author()
    baseline = {r["uid"]: r for r in author if r["method"] == "PB_RUBRIC"}
    if len(baseline) != 60:
        raise ValueError("Baseline allocation changed")
    pools = defaultdict(list)
    for row in author:
        if row["score"] is not None:
            pools[row["uid"]].append(("author", row))
    audit_counts = {}
    for path in [*(RESIDUAL / x for x in (*EXTERNAL, *EXPOSURE, *GENERATION)), STANCE]:
        tally = audit_counts[path.name] = Counter()
        records, used = supplementary(path, envelopes, tally)
        files.extend(used)
        for row in records:
            pools[row["uid"]].append((path.name, row))
    tally = audit_counts[FACTORIAL.name] = Counter()
    older, older_pins = factorial(envelopes, tally)
    files.extend(older_pins)
    for row in older:
        pools[row["uid"]].append((FACTORIAL.name, row))
    prior_actor_units = set(read(FACTORIAL / "PLAN.json")["jobs"])
    for stage in ("selected_gepa_expansion_v1", "persist_performance_v1"):
        path = RESIDUAL / stage / "FinalActor_MANIFEST.json"
        files.append(path)
        prior_actor_units.update(x["unit"]["root_id"] for x in read(path)["units"]
                                 if x["unit"]["method"] == "SELECTED_GEPA")
    cards, overall, paired, uncovered = [], defaultdict(Counter), defaultdict(Counter), []
    for uid, base in sorted(baseline.items()):
        if base["score"] is None:
            overall["all"]["missing_base"] += 1
            continue
        track = base["score"]["category"]
        base_pass = passes(base["score"], track)
        by_answer = defaultdict(list)
        for origin, row in pools[uid]:
            other_track = row.get("category") or row["score"].get("category") or row["base_score"]["category"]
            if track != other_track:
                raise ValueError("Track drift")
            by_answer[sha(row["answer"])].append(
                {"passes": passes(row["score"], track), "origin": origin, "method": row["method"]})
        definitely_passing = [members for members in by_answer.values() if all(m["passes"] for m in members)]
        conflicts = sum(len({m["passes"] for m in members}) > 1 for members in by_answer.values())
        controls = {"PB_NO_MEMORY": [row for origin, row in pools[uid]
                                      if origin == "author" and row["method"] == "PB_NO_MEMORY"],
                    "SELECTED_GEPA": [row for origin, row in pools[uid]
                                      if origin in ("selected_gepa_expansion_v1", "persist_performance_v1", FACTORIAL.name)
                                      and row["method"] == "SELECTED_GEPA"]}
        if not controls["SELECTED_GEPA"]:
            uncovered.append({"uid": uid, "track": track, "base_pass": base_pass,
                              "actor_in_examined_manifests": uid in prior_actor_units})
        for category in ("all", track):
            for method, control in controls.items():
                if len(control) > 1:
                    raise ValueError("Ambiguous endpoint across selected panels")
                if control:
                    rival_pass = passes(control[0]["score"], track)
                    c = paired[f"{category}/{method}"]
                    c.update(common=1, base_pass=base_pass, other_pass=rival_pass,
                             wins=rival_pass and not base_pass, losses=base_pass and not rival_pass)
            c = overall[category]
            c.update(common=1, base_pass=base_pass)
            if not base_pass:
                c["with_consistent_passing_endpoint" if definitely_passing else
                  "without_consistent_passing_endpoint"] += 1
                c["with_author_non_memory_pass"] += any(any(
                    m["origin"] == "author" and m["method"] == "PB_NO_MEMORY" for m in group)
                    for group in definitely_passing)
        if not base_pass or conflicts:
            cards.append({"uid": uid, "track": track, "base_pass": base_pass, "unique_answers": len(by_answer),
                          "conflicting_answer_grades": conflicts, "consistent_passes": definitely_passing})
    return {"counts": overall, "comparisons": paired, "archives": audit_counts, "deviations": cards, "new_requests": 0,
            "selected_gepa_uncovered": uncovered, "source_hashes": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files}}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
