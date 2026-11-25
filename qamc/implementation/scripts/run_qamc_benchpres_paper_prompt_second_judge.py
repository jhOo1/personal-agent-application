"""Compare GPT-4.1 and archived Qwen labels on the same semantic preferences."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

import audit_qamc_benchpres_paper_prompt_bridge as attributes
from qamc.common import parse_object

bridge = attributes.trial
base, bench, ROOT = bridge.base, bridge.bench, bridge.ROOT
read, frozen, sha = bridge.read, bridge.frozen, bridge.sha
NAME = "qamc_benchpres_paper_prompt_second_judge"
OUT, RUN = ROOT / "reports" / NAME, ROOT / "runs" / NAME
METHODS, STAGES = attributes.METHODS, attributes.ATTRIBUTES
CAP = 36
DIAGNOSTIC_UID = "benchpres/new_pairs/e314f70877c20913d031"
LABELS = ("follow", "do_not_follow")


def check(plan):
    assert len(plan["specs"]) == len(plan["reference"]) == len(set(plan["allowed_unit_keys"])) == CAP
    assert Counter(r["scope"] for r in plan["reference"]) == {"primary": 33, "diagnostic": 3}
    assert all(base.file_sha(ROOT / f) == h for f, h in plan["files"].items())


def prepare():
    p, r = bridge.OUT / "PLAN.json", bridge.OUT / "PILOT.json"
    old = read(p)
    archive = bridge.previous.OUT / "PILOT.json"
    by = {(row["uid"], row["method"]): row for row in read(archive)["rows"] if row["method"] in METHODS}
    by.update({(row["uid"], bridge.METHOD): row for row in read(r)["rows"]})
    protocols = old["protocol"]
    qwen_protocol = {**protocols, "stages": {stage: protocols["stages"][stage] for stage in STAGES}}
    plan = {"protocol": {**qwen_protocol, "namespace": NAME, "model": "gpt-4.1"}, "specs": [], "reference": []}
    files = [Path(__file__), Path(attributes.__file__), OUT / "RULES.md", p, r, archive,
             ROOT / "src/qamc/pilot_scoring.py", ROOT / "proposals/qamc_memgate_external/evaluation.py"]
    for c in old["cases"]:
        uid = c["uid"]
        ref_path = ROOT / c["evaluation_path"]
        files.append(ref_path)
        ref = read(ref_path)
        assert bench.digest(ref) == c["evaluation_hash"]
        for i, (attribute, appropriate) in enumerate(zip(ref["preference_attribute"], ref["preference_label"], strict=True)):
            primary = appropriate and not re.search(r"\bbold text\b", attribute, re.I)
            diagnostic = uid == DIAGNOSTIC_UID and not appropriate and "emotionally expressive" in attribute
            if not (primary or diagnostic):
                continue
            for method in METHODS:
                row = by[uid, method]
                stage = STAGES[i]
                qwen = attributes.attribute_labels(row)[i]
                query = read(ROOT / c["public_path"])["query"]
                judges = {s: (system, payload) for s, system, payload in
                          bench.initial_requests(ROOT, "benchpres", ref, query, row["answer"])}
                system, payload = judges[stage]
                assert set(payload) == {"preference", "response"} and payload["preference"] == attribute
                spec = bench.job(plan, uid, method, stage, system, payload)
                qwen_body = {**spec["request"], "model": qwen_protocol["model"]}
                plan["specs"].append(spec)
                plan["reference"].append({"uid": uid, "stage": stage, "method": method,
                    "profile_group": c["profile_group"], "qwen_label": qwen, "attribute": attribute,
                    "scope": "primary" if primary else "diagnostic", "qwen_request_sha256": sha(qwen_body)})
    plan["allowed_unit_keys"] = sorted(base.sampling_key(s["unit"]) for s in plan["specs"])
    plan["files"] = {str(f.relative_to(ROOT)): base.file_sha(f) for f in files}
    check(plan)
    frozen(OUT / "PLAN.json", plan)


def results(plan, rt):
    rows = []
    for spec, ref in zip(plan["specs"], plan["reference"], strict=True):
        u = spec["unit"]
        saved = rt.output(u)
        row = {**ref, "status": saved["status"] if saved else "NOT_RUN", "gpt_label": None}
        if saved and saved["status"] == "OK":
            assert saved["request_sha256"] == sha(spec["request"])
            row["raw"] = saved["response"]["answer"]
            try:
                label = parse_object(row["raw"]).get("label")
            except ValueError:
                label = None
            if label in LABELS:
                row["gpt_label"] = label
            else:
                row["status"] = "INVALID_LABEL"
        rows.append(row)
    positions = defaultdict(dict)
    for row in rows:
        if row["scope"] == "primary":
            positions[row["uid"], row["stage"]][row["method"]] = row
    common = [p for p in positions.values() if all(p[m]["gpt_label"] is not None for m in METHODS)]
    summary = {m: {judge: sum(p[m][judge] == "follow" for p in common)
                   for judge in ("qwen_label", "gpt_label")} for m in METHODS}
    ledger = base.caches.old.snapshot(RUN, CAP)
    assert not ledger["in_flight_observations"]
    return {"rows": rows, "summary": summary, "common_positions": len(common), "ledger": ledger}


def main(action):
    if action == "prepare":
        prepare()
        return
    plan = read(OUT / "PLAN.json")
    check(plan)
    rt = base.rtlib.Runtime(ROOT.parent, OUT, RUN, check)
    if action == "run":
        RUN.mkdir(parents=True, exist_ok=True)
        with base.caches.old.runner_lock(RUN / "runner.lock"):
            stop = RUN / "STOP"
            if stop.exists():
                raise ValueError("Run already terminal")
            path = OUT / "CACHE.json"
            specs = plan["specs"]
            index = read(path) if path.exists() else base.caches.inventory(specs)
            assert index["wanted"] == sorted({sha(s["request"]) for s in specs})
            frozen(path, index)
            base.rtlib.exact = base.caches.old.prefilter_exact
            rt.stage(plan, "pilot", "Judge", specs, index)
            frozen(OUT / "PILOT.json", results(plan, rt))
            stop.write_text("Frozen semantic rescore terminal.\n")
    elif action == "report":
        saved = read(OUT / "PILOT.json")
        assert saved == results(plan, rt)
        print(json.dumps(saved["summary"], ensure_ascii=False))
    else:
        raise ValueError("Use prepare, run or report")


if __name__ == "__main__":
    main(sys.argv[1])
