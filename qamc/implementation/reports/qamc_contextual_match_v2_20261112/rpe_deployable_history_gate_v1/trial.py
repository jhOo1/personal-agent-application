from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from run_probe import engine, probe
from qamc.common import canonical, sha

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / "ipe_c_rate_matched_controls_v1"))
from audit_rate import FULL, ZERO, load, score

rows, pins = load()
source = json.loads((here.parent / "counterfactual_rpeval_v41/FROZEN.json").read_text())
roots = {row["uid"]: row for row in source["roots"]}
groups = defaultdict(list)
for row in rows:
    groups[row["wire"]].append(row)
panel = []
for group in sorted(groups, key=lambda g: sha(["gate-panel-v1", g])):
    histories = {}
    for r in sorted(groups[group], key=lambda r: sha(["gate-case-v1", r["uid"]])):
        histories.setdefault(sha(roots[r["uid"]]["original_sources"]), r)
    if len(histories) >= 2:
        pair = list(histories.values())[:2]
        assert len({sha(roots[r["uid"]]["public_task"]) for r in pair}) == 1
        panel.extend(pair)
    if len(panel) == 24:
        break
assert len(panel) == 24
prompt = """Choose whether the answer writer should receive the user's entire history for the current request. ON when access is likely to improve the delivered answer, including respecting applicable constraints and helpful preferences. OFF when its value is outweighed by irrelevant influence, wrong attribution, or shifting the task. If the history is unavailable to you, estimate its likely value from the task alone. Return exactly ON or OFF."""
jobs, keys = {}, {}
for row in panel:
    uid = row["uid"]
    for arm in ("query", "memory"):
        packet = dict(roots[uid]["public_task"])
        if arm == "memory":
            packet["history"] = roots[uid]["original_sources"]
        wire = {"model":"qwen3.8-flash","stream":True,"stream_options":{"include_usage":True},"temperature":0,"max_tokens":2048,
                "messages":[{"role":"system","content":prompt},{"role":"user","content":canonical(packet)}]}
        key = sha(wire), arm
        keys[uid,arm] = key
        jobs[key] = wire
assert len(jobs) == 36
run = here.parents[2] / "runs" / here.parent.name / (here.name + "_usage")
out = run / "private"
out.mkdir(parents=True,exist_ok=True)
probe.RUN, probe.OUT, engine.OUT = run, out, out
stage = "HistorySwitch"
with probe.runner_lock(run / "runner.lock"):
    pin = {"sources":pins,"code":sha(Path(__file__).read_bytes()),"protocol":sha((here/"PROTOCOL.md").read_bytes()),
           "panel":[r["uid"] for r in panel],"jobs":sorted(sha(w) for w in jobs.values())}
    probe.freeze(out/"FROZEN.json",pin)
    ledger = []
    engine.CAP[stage] = len(jobs)
    replies = engine.stage(stage, dict(sorted(jobs.items())), {"experiment_sha256":sha(pin),"service_reference_sha256":probe.read_reference()[1]},True,ledger)
    def decision(r, arm):
        rec = replies[keys[r["uid"],arm]]
        return {"ON":FULL,"OFF":ZERO}.get((rec.get("answer") or "").strip()) if rec["status"]=="OK" else None
    valid = [r for r in panel if all(decision(r,a) for a in ("query","memory"))]
    summary = {}
    labels = {r["uid"]:r["labels"] for r in json.loads((here.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]}
    for label, subset in {"all":valid,"unflagged":[r for r in valid if r["clean"]],
                          "contains_C":[r for r in valid if "C" in labels[r["uid"]]],
                          "only_B":[r for r in valid if set(labels[r["uid"]])=={"B"}]}.items():
        card = {"tasks":len(subset),"positions":sum(r["positions"] for r in subset)}
        for a in ("query","memory","IPE-C","empty","full"):
            def arm(r):
                return decision(r,a) if a in ("query","memory") else {"IPE-C":r["base"],"empty":ZERO,"full":FULL}[a]
            card[a] = {m:sum(score(r,arm(r),m) for r in subset if all(score(r,k,m) is not None for k in (ZERO,FULL))) for m in ("Match","OPB","UPB","FM")}
            card[a]["open"] = sum(arm(r)==FULL for r in subset)
        summary[label]=card
    result = dict(summary=summary,disagreements=sum(decision(r,"query")!=decision(r,"memory") for r in valid),
                  physical=len(ledger),status=dict(Counter(r["status"] for r in ledger)),
                  tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),
                  invalid_outputs=sum(r["status"]=="OK" and (r.get("answer") or "").strip() not in ("ON","OFF") for r in replies.values()))
    probe.freeze(out/"SETTLED.json",result)
    print(json.dumps(result,indent=2))
