"""Replay two shared routes using exact, already-scored method outputs."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
INPUTS = {
    "frontier": "native_decision_frontier_v1/FRONTIER.json",
    "rpe": "selective_path_frontier_v1/RESULTS.json",
    "transfer": "rp_estimator_routing_transfer_v1/RESULTS.json",
    "persist": "selective_path_frontier_v1/PERSIST_OPPONENTS.json",
}
METHOD_ARCHIVES = (
    "paper_baseline_validation_156_v1/RESULT_ROWS.json",
    "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json",
)
BOLD = re.compile(r"\bbold\s+(?:text|formatting|typeface)\b", flags=re.IGNORECASE)
PERSIST_C5 = HERE / "PERSIST_C5_EXACT.json"
C5, GATE, RP, IPE = "GOAL_EFFECT_GEPA", "GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL", "IPE_C"
BOARDS = ("rpeval", "benchpres", "persistbench")
METRICS = {
    "rpeval": ("match", "negative_opb", "negative_upb", "negative_fm"),
    "benchpres": ("aar", "negative_mr", "completeness", "nonbold_aar"),
    "persistbench": ("primary_pass", "companion_pass"),
}


def read(file):
    return json.loads(file.read_text(encoding="utf-8"))


def index(rows):
    rows = list(rows)
    result = {r["uid"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate root index")
    return result


def source_choice(benchmark, uid, sources):
    if benchmark == "rpeval":
        row = sources["rpe"][uid]
        if row["base"] not in {RP, "TASK_ONLY"}:
            raise ValueError("Unknown RPEval route")
        return row["base"] == RP
    board = {"benchpres": "BenchPreS", "persistbench": "PersistBench"}[benchmark]
    keep = sources["transfer"]["results"][board]["choices"][uid]["methods"][IPE]
    if benchmark == "persistbench":
        persisted = sources["persist"][uid]
        if persisted["ipe_arm"] != (RP if keep else "PB_NO_MEMORY"):
            raise ValueError("PersistBench selected branch differs from frozen IPE rule")
    return keep


def formatting_selected(candidate, archive):
    row = archive.get((candidate["uid"], candidate["scores"][candidate["backbone"]]["answer_sha256"]))
    if row is None:
        raise ValueError("Backbone answer lacks a matching archived input")
    selected = row.get("view", {}).get("source_evidence", [])
    matched = [m for m in selected if BOLD.search(m["text"])]
    actor = "\n".join(m["content"] for m in row["actor_request"]["messages"])
    if any(m["text"] not in actor for m in matched):
        raise ValueError("Archived format source was not exposed to the Actor")
    evidence = [m["memory_id"] for m in matched]
    return evidence


def compute(benchmark, rows, sources, backbone, format_variant=False):
    missing, comparisons = Counter(), []
    for row in rows:
        uid = row["uid"]
        scores = row["scores"]
        keep = source_choice(benchmark, uid, sources)
        bucket = row["variant"], row["stratum"]
        missing[bucket + ("frontier",)] += 1
        if backbone not in scores or IPE not in scores or RP not in scores:
            missing[bucket + ("missing_any_base_or_route",)] += 1
            continue
        if benchmark == "rpeval":
            core = sources["rpe"][uid]["cells"][RP if keep else "TASK_ONLY"]
            if core["answer_sha256"] != scores[IPE]["answer_sha256"]:
                raise ValueError("RPEval exact selected answer differs")
        if keep and scores[IPE] != scores[RP]:
            raise ValueError(f"Exact kept RP differs from IPE-C for {uid}")
        if not keep and benchmark == "persistbench" and scores[IPE] != scores["PB_NO_MEMORY"]:
            raise ValueError(f"Selected task-only result differs for {uid}")
        if not keep and scores[IPE]["answer_sha256"] == scores[backbone]["answer_sha256"]:
            if scores[IPE]["primary"] != scores[backbone]["primary"] or scores[IPE]["protections"] != scores[backbone]["protections"]:
                missing[bucket + ("same_answer_grade_conflict",)] += 1
                continue
        evidence = (formatting_selected({"uid": uid, "scores": scores, "backbone": backbone},
                                        sources["archive"][backbone]) if format_variant and not keep else [])
        effective_keep = keep or bool(evidence)
        outcome = scores[backbone if effective_keep else IPE]
        comparisons.append({"uid": uid, "group": row["group"], "stratum": row["stratum"],
                            "variant": row["variant"], "n": row["denominator"],
                            "task_only": not effective_keep, "bold_protected_ids": evidence,
                            "changed": outcome["answer_sha256"] != scores[backbone]["answer_sha256"],
                            "scores": {m: c for m, c in scores.items() if m in {backbone, GATE, RP, IPE, "PB_RUBRIC"}},
                            "routed": outcome})
    return comparisons, [{"variant": v, "stratum": s, "status": k, "n": n}
                         for (v, s, k), n in sorted(missing.items())]


def summarize(benchmark, rows):
    pools = defaultdict(list)
    for row in rows:
        pools[row["variant"] + "/" + row["stratum"]].append(row)
        if benchmark == "rpeval":
            pools[row["variant"] + "/all"].append(row)
    result = {}
    for k, group in pools.items():
        arms = set.intersection(*(set(r["scores"]) for r in group)) | {"ROUTED"}
        scores = {}
        for arm in sorted(arms):
            variants = [r["routed"] if arm == "ROUTED" else r["scores"][arm] for r in group]
            vector = [sum(values) for values in zip(*([s["primary"], *s["protections"]]
                                                     for s in variants), strict=True)]
            scores[arm] = dict(zip(METRICS[benchmark], vector, strict=True))
        result[k] = {"roots": len(group), "groups": len({r["group"] for r in group}),
                     "denominator": sum(r["n"] for r in group), "task_only": sum(r["task_only"] for r in group),
                     "changed_from_backbone": sum(r["changed"] for r in group), "scores": scores}
    return result


def main():
    sources = {k: read(BASE / path) for k, path in INPUTS.items()}
    sources["rpe"] = index(sources["rpe"]["rows"])
    sources["persist"] = index(sources["persist"]["rows"])
    c5 = index(read(PERSIST_C5)["rows"])
    for row in sources["frontier"]["benchmarks"]["persistbench"]["rows"]:
        cell = c5.get(row["uid"])
        if not cell:
            continue
        if row["stratum"] != cell["category"] or C5 in row["scores"]:
            raise ValueError("PersistBench C5 score join differs")
        primary, companion = (int(not cell["failure_release"]), int(not cell["failure_strict_utility"]))
        if cell["category"] == "beneficial_memory_usage":
            primary, companion = companion, primary
        row["scores"][C5] = {"primary": primary, "protections": [companion],
                             "answer_sha256": cell["answer_sha256"]}
    sources["archive"] = {C5: {}, GATE: {}}
    for file in METHOD_ARCHIVES:
        for r in read(BASE / file):
            if r["method"] in sources["archive"] and r.get("answer"):
                digest = hashlib.sha256(r["answer"].encode()).hexdigest()
                key = r["uid"], digest
                records = sources["archive"][r["method"]]
                old = records.setdefault(key, r)
                if old.get("view") != r.get("view"):
                    raise ValueError("Same archived answer has two different views")
    out = {}
    for benchmark in BOARDS:
        out[benchmark] = {}
        for backbone in (C5, GATE):
            for format_variant in (False, True):
                cohort = sources["frontier"]["benchmarks"][benchmark]["rows"]
                pairs, exclusions = compute(benchmark, cohort, sources, backbone, format_variant)
                method = backbone + ("_PRESERVE_BOLD" if format_variant else "")
                out[benchmark][method] = {"summary": summarize(benchmark, pairs),
                                          "rows": pairs, "coverage": exclusions}
    result = {"comparisons": out, "new_model_requests": 0,
              "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
                  **{name: BASE / f for name, f in INPUTS.items()},
                  **{f: BASE / f for f in METHOD_ARCHIVES}, PERSIST_C5.name: PERSIST_C5}.items()}}
    (HERE / "RESULTS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
