"""Test Style's fixed preference subset inside the BenchPreS paper prompt."""
from collections import Counter
from pathlib import Path
import re
import sys

import run_qamc_benchpres_paper_prompt_bridge as paper

base, ROOT, read, frozen, sha = paper.base, paper.ROOT, paper.read, paper.frozen, paper.sha
OUT, RUN = ROOT / "reports/qamc_benchpres_paper_style", ROOT / "runs/qamc_benchpres_paper_style"
PARENT, PAPER = paper.OUT, paper.METHOD
METHOD = "PAPER_STYLE"
CAP = 70


def check(plan):
    assert len(plan["cases"]) == len({c["profile_group"] for c in plan["cases"]}) == 10
    assert len(plan["initial"]) == 10 and len(set(plan["allowed_unit_keys"])) == CAP
    assert all(base.file_sha(ROOT / p) == h for p, h in plan["files"].items())


def filter_preferences(content, preferences, selected):
    profile, query = content.split(paper.PROFILE_END)
    lines = profile.splitlines(keepends=True)
    assert all(sum(line.rstrip("\r\n") == pref for line in lines) == 1 for pref in preferences)
    assert selected <= preferences
    return "".join(line for line in lines if line.rstrip("\r\n") not in preferences - selected) + paper.PROFILE_END + query


def freeze():
    old_path = PARENT / "PLAN.json"
    style_path = paper.previous.OUT / "PILOT.json"
    old = read(old_path)
    paper.check(old)
    style = {row["uid"]: row for row in read(style_path)["rows"] if row["method"] == "STYLE"}
    plan = {"protocol": {**old["protocol"], "namespace": OUT.name}, "cases": old["cases"], "initial": [],
            "filter_audit": {}}
    pins = [old_path, PARENT / "PILOT.json", style_path, Path(__file__), Path(paper.__file__), OUT / "RULES.md"]
    for case, original in zip(old["cases"], old["initial"], strict=True):
        uid = case["uid"]
        assert original["unit"]["root_id"] == uid
        public_path = ROOT / case["public_path"]
        public = read(public_path)
        memories = {m["memory_id"]: m["text"] for m in public["memories"]}
        assert len(memories) == len(public["memories"]) and len(memories) >= 5
        kept = {m["memory_id"] for m in style[uid]["evidence"]}
        assert kept <= memories.keys()
        assert all(m["text"] == memories[m["memory_id"]] for m in style[uid]["evidence"])
        msg, = original["request"]["messages"]
        result = filter_preferences(msg["content"], set(memories.values()), {memories[k] for k in kept})
        job = base.job(plan, uid, METHOD, "Actor", [{**msg, "content": result}])
        assert {**job["request"], "messages": original["request"]["messages"]} == original["request"]
        plan["initial"].append(job)
        plan["filter_audit"][uid] = {"kept": sorted(kept), "removed": sorted(memories.keys() - kept),
                                     "old_sha256": sha(original["request"])}
        pins.extend((public_path, ROOT / case["evaluation_path"]))
    plan["allowed_unit_keys"] = sorted(base.sampling_key(base.unit(plan, c["uid"], METHOD, stage))
                                      for c in plan["cases"] for stage in ("Actor", *paper.JUDGES))
    plan["files"] = {str(p.relative_to(ROOT)): base.file_sha(p) for p in pins}
    check(plan)
    frozen(OUT / "PLAN.json", plan)


def summary(plan, rows):
    methods = (PAPER, METHOD, "STYLE", "GP0")
    by = {(r["uid"], METHOD): r["score"] for r in rows}
    by.update({(r["uid"], PAPER): r["score"] for r in read(PARENT / "PILOT.json")["rows"]})
    by.update({(r["uid"], r["method"]): r["score"] for r in read(paper.previous.OUT / "PILOT.json")["rows"]
               if r["method"] in methods})
    comparisons = {}
    for arms in (methods[:2], (methods[2], METHOD), methods):
        common = [c["uid"] for c in plan["cases"] if all(by.get((c["uid"], m)) for m in arms)]
        metrics, components = {}, {}
        for method in arms:
            scores = [by[uid, method] for uid in common]
            metrics[method] = paper.bench.aggregate_bench(scores)
            counts = Counter()
            for score in scores:
                for row in score["decisions"]:
                    text = row["preference"]
                    kind = ("bold" if re.search(r"\bbold text\b", text, re.I)
                            else "nickname" if re.search(r"\b(?:called|nickname)\b", text, re.I) else "other")
                    key = f"{'appropriate' if row['appropriate'] else 'inappropriate'}_{kind}"
                    counts[key + "_total"] += 1
                    counts[key + "_follow"] += row["label"] == "follow"
            components[method] = counts
        effects = {uid: {m: {k: by[uid, m][k] for k in ("aar_numerator", "mr_numerator", "task_completeness")}
                         for m in arms} for uid in common}
        comparisons["__".join(arms)] = {"common": common, "metrics": metrics, "components": components,
                                       "effects": effects}
    return comparisons


def collect(plan, rt):
    rows, _ = paper.collect(plan, rt)
    ledger = base.caches.old.snapshot(RUN, CAP)
    assert not ledger["in_flight_observations"]
    return {"rows": rows, "ledger": ledger, "summary": summary(plan, rows)}


def main(action):
    if action == "freeze":
        freeze()
        return
    plan = read(OUT / "PLAN.json")
    check(plan)
    paper.METHOD, paper.OUT = METHOD, OUT
    rt = base.rtlib.Runtime(ROOT.parent, OUT, RUN, check)
    if action == "report":
        assert read(OUT / "PILOT.json") == collect(plan, rt)
        return
    if action != "run":
        raise ValueError(action)
    RUN.mkdir(parents=True, exist_ok=True)
    with base.caches.old.runner_lock(RUN / "runner.lock"):
        stop = RUN / "STOP"
        if stop.exists():
            raise ValueError("Frozen pilot already terminal")
        base.rtlib.exact = base.caches.old.prefilter_exact
        paper.stage(plan, rt, "Actor", plan["initial"])
        _, judges = paper.collect(plan, rt)
        paper.stage(plan, rt, "Judge", judges)
        frozen(OUT / "PILOT.json", collect(plan, rt))
        stop.write_text("Frozen BenchPreS paper Style comparison terminal.\n")


if __name__ == "__main__":
    main(sys.argv[1])
