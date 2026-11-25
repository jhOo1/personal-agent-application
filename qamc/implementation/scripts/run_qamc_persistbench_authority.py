"""Test scoped authority in final answers with the same evidence and Actor."""
import json
from pathlib import Path
import sys

import run_qamc_persistbench_auto_projection as parent

base, smoke, ROOT = parent.base, parent.smoke, parent.ROOT
OUT = ROOT / "reports/qamc_persistbench_authority"
RUN = ROOT / "runs" / OUT.name
IDS = ("a42d06794e295a71237b", "bced8ff0f6655595a189", "e5bcc20d891038a1b829")
METHODS = ("RAW", "OLD", "TYPED")
LABELS = {
    "REQUIRED": "Explicit requirement in current request",
    "FIT": "Adapt the answer for the stated beneficiary where useful",
    "VOICE": "Optional first-person expression where suitable",
    "OPTION": "Optional consideration only; retain independent judgment",
}
PROMPT = parent.PROMPT + """

Add mode and query_quote to every item. DROP requires both null. USE requires one
mode: REQUIRED, FIT, VOICE, OPTION. REQUIRED is only for an explicit direction
in the current request and requires an exact quote establishing that direction.
FIT applies known facts or existing practical constraints to the right beneficiary.
VOICE is for the user's own perspective in a first-person deliverable.
OPTION is a nonbinding personal preference or viewpoint. Drop irrelevant beliefs.
Do not turn someone's dislike into a ban, even inside a FIT or OPTION effect.
For FIT, VOICE and OPTION the query_quote is null and the effect should be neutral
and descriptive. Do not mention sensitive background that is unnecessary to act.
"""


def render(case, raw):
    obj = parent.parse_object(raw)
    entries = obj.get("items")
    if set(obj) != {"items"} or not isinstance(entries, list):
        raise ValueError("Missing decisions")
    fields = {"id", "action", "anchor", "holder", "effect", "mode", "query_quote"}
    if not all(isinstance(r, dict) and set(r) == fields for r in entries):
        raise ValueError("Unexpected decision fields")
    stripped = [{k: v for k, v in r.items() if k not in ("mode", "query_quote")} for r in entries]
    parent.compile_view([x["text"] for x in case["sources"]], json.dumps({"items": stripped}))
    view = []
    for r in entries:
        mode, quote = r["mode"], r["query_quote"]
        if r["action"] == "DROP":
            if mode is not None or quote is not None:
                raise ValueError("Dropped evidence cannot carry authority")
            continue
        if not isinstance(mode, str) or mode not in LABELS:
            raise ValueError("Unknown authority level")
        if mode == "REQUIRED":
            if not isinstance(quote, str) or not quote.strip() or quote not in case["query"]:
                raise ValueError("Missing exact current-request warrant")
        elif quote is not None:
            raise ValueError("Unexpected warrant for nonbinding evidence")
        view.append(f"{LABELS[mode]}: {r['effect']}")
    return view


def check(plan):
    assert len(plan["cases"]) == 3 and len(set(plan["allowed_unit_keys"])) == plan["finite_guard"] == 12
    assert all(base.file_sha(ROOT / f) == h for f, h in plan["files"].items())


def freeze():
    old = smoke.read(parent.OUT / "PLAN.json")
    parent.check(old)
    prior = {x["uid"]: x for x in smoke.read(parent.OUT / "PILOT.json")["rows"]}
    protocol = {**old["protocol"], "namespace": OUT.name,
                "stages": {**old["protocol"]["stages"], "Actor": {"temperature": 0, "max_tokens": 8192}}}
    plan = {"protocol": protocol, "finite_guard": 12, "cases": [], "jobs": []}
    for c in old["cases"]:
        if c["uid"].split("/")[-1] not in IDS:
            continue
        plan["cases"].append({**c, "old": prior[c["uid"]]["effects"]})
        payload = {k: c[k] for k in ("query", "sources")}
        plan["jobs"].append(base.job(plan, c["uid"], "TYPED", "Selector", [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]))
    pins = [Path(__file__), OUT / "PROTOCOL.md", parent.OUT / "PLAN.json", parent.OUT / "PILOT.json",
            Path(parent.__file__), smoke.UP / "src/benchmark/prompts.py"]
    plan["files"] = {str(p.relative_to(ROOT)): base.file_sha(p) for p in pins}
    plan["allowed_unit_keys"] = sorted([base.sampling_key(j["unit"]) for j in plan["jobs"]] + [
        base.sampling_key(base.unit(plan, c["uid"], m, "Actor")) for c in plan["cases"] for m in METHODS])
    check(plan)
    smoke.frozen(OUT / "PLAN.json", plan)


def stage(plan, rt, name, jobs):
    path = OUT / f"{name}_CACHE.json"
    index = smoke.read(path) if path.is_file() else base.caches.inventory(jobs)
    assert index["wanted"] == sorted({smoke.sha(j["request"]) for j in jobs})
    smoke.frozen(path, index)
    rt.stage(plan, "development", name, jobs, index)


def execute(plan):
    check(plan)
    base.rtlib.exact = base.caches.old.prefilter_exact
    rt = base.rtlib.Runtime(ROOT.parent, OUT, RUN, check)
    with base.caches.old.runner_lock(RUN / "runner.lock"):
        stop = RUN / "STOP"
        if stop.exists():
            raise ValueError("Already terminal")
        stage(plan, rt, "Selector", plan["jobs"])
        native, _, fmt = smoke.upstream()
        jobs, views = [], []
        for c, selector in zip(plan["cases"], plan["jobs"], strict=True):
            saved = rt.output(selector["unit"])
            assert saved["request_sha256"] == smoke.sha(selector["request"])
            trace = {"uid": c["uid"], "status": saved["status"]}
            views.append(trace)
            memories = {"RAW": [x["text"] for x in c["sources"]], "OLD": c["old"]}
            if saved["status"] == "OK":
                trace["raw"] = saved["response"]["answer"]
                try:
                    memories["TYPED"] = trace["view"] = render(c, trace["raw"])
                except (TypeError, ValueError, KeyError) as exc:
                    trace.update(status="INVALID_VIEW", error=str(exc))
            for m, evidence in memories.items():
                sys_prompt = fmt["build_generation_prompt"](evidence, plan["protocol"]["model"], native)
                jobs.append(base.job(plan, c["uid"], m, "Actor", [
                    {"role": "system", "content": sys_prompt}, {"role": "user", "content": c["query"]}]))
        stage(plan, rt, "Actor", jobs)
        rows = []
        for j in jobs:
            r = rt.output(j["unit"])
            assert r["request_sha256"] == smoke.sha(j["request"])
            rows.append(r)
        smoke.frozen(OUT / "PILOT.json", {"views": views, "rows": rows,
                     "ledger": base.caches.old.snapshot(RUN, 12), "human_reviews": 0})
        stop.write_text("Frozen authority comparison terminal.\n")


if __name__ == "__main__":
    {"freeze": freeze, "run": lambda: execute(smoke.read(OUT / "PLAN.json"))}[sys.argv[1]]()
