"""Compare exact-span decision edits with and without original history."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from runpy import run_path
import sys

from qamc.common import sha
from patch_contract import patch

HERE = Path(__file__).resolve().parent
REP, TR = (HERE.parent / n for n in ("composition_replication_v1", "composition_transfer_v1"))
sys.path.extend((str(REP), str(TR)))
R = run_path(str(REP / "run.py"))
engine, probe, wire = R["engine"], R["probe"], R["wire"]
ARMS = ("CURRENT", "HISTORY")
INSTRUCTIONS = """Review the supplied existing user-facing answer. Keep it verbatim unless you
can identify a specific requested decision it materially gets wrong, an unmet applicable
constraint, or a useful requested decision it fails to resolve. Do not simply add generic advice.
Change one decision only. Cite a literal short span from the current query or context as the
task_anchor and one literal quote from the supplied evidence dictionary as the justification.
Q/T are current evidence. M keys are original history, if supplied. Copy the source_id key,
never its text. Current stated constraints win. Use history only to the actual person, goal
and decision it governs. A request made on behalf of a group can allow personal choices, but
does not make one person's unrelated preference a group rule. Keep legitimate advice already
implemented. For a hard condition check all implementations of this same decision; if the
necessary change cannot be made in two existing excerpts without making the answer inconsistent,
keep it. For soft preferences use realistic impact instead of creating a new goal. No invented
availability or facts. Return only JSON, either {"edits":[]} or this exact schema:
{"decision":"specific existing decision","task_anchor":"literal current span","source_id":"Q",
"quote":"literal excerpt from evidence Q","edits":[{"old":"unique exact text from the answer",
"new":"replacement in the same language"}]}. At most two nonoverlapping edits."""


def public_evidence(task):
    return {key: val for key, val in (("Q", task["query"]), ("T", task.get("current_context"))) if val}


def prepare(benchmark):
    if benchmark == "RPEval":
        previous, roots, drafts, packets = R["prepare"]()
        aux = {"rpe_panel": previous["panel"]}
        lineage = sha(previous)
    else:
        T = run_path(str(TR / "run_transfer_composition.py"))
        previous, roots, packets, drafts, cases, protocol, controls, cache, conflicts = T["inputs"](benchmark)
        aux = {"cases": cases, "protocol": protocol, "controls": controls, "cache": cache,
               "conflicts": conflicts, "references": T["REFERENCES"][benchmark]}
        lineage = sha(previous)
    pin = {"benchmark": benchmark, "lineage_sha256": lineage, "cohort": list(roots),
           "code_sha256": {name: sha((HERE / name).read_bytes())
                           for name in ("run_patches.py", "PROTOCOL.md", "patch_contract.py")},
           "drafts_sha256": sha(drafts), "packets_sha256": sha(packets)}
    return pin, roots, drafts, packets, aux


def generation(roots, drafts, packets, stage):
    jobs, evidence = {}, {}
    for uid, root in roots.items():
        task = root["public_task"]
        for arm in ARMS if int(sha(uid)[0], 16) % 2 else ARMS[::-1]:
            sources = public_evidence(task)
            if arm == "HISTORY":
                original = packets[uid]["memory"]
                if sources.keys() & original.keys():
                    raise ValueError("Source ID collision")
                sources = {**sources, **original}
            evidence[uid, arm] = sources
            jobs[uid, arm] = wire(INSTRUCTIONS, {"task": task, "answer": drafts[uid], "evidence": sources}, 4096)
    rows = []
    for (uid, arm), receipt in stage("Patch", jobs).items():
        row = {"uid": uid, "method": arm, "actor_status": "MISSING", "score": None, "answer": None,
               "proposal": receipt, "edit": None}
        rows.append(row)
        if receipt["status"] != "OK":
            continue
        try:
            row["answer"], row["edit"] = patch(receipt["answer"], drafts[uid],
                                               roots[uid]["public_task"], evidence[uid, arm])
            row["operation"] = "APPLY" if row["edit"] else "KEEP"
        except (ValueError, TypeError, KeyError) as exc:
            row.update(answer=drafts[uid], operation="INVALID_KEEP", contract_error=str(exc))
        row["actor_status"] = "OK"
    return rows


def execute(action, benchmark):
    pin, roots, drafts, packets, aux = prepare(benchmark)
    probe.OUT = engine.OUT = HERE / benchmark
    engine.OUT.mkdir(exist_ok=True)
    frozen = engine.OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(frozen, pin)
        print({"benchmark": benchmark, "tasks": len(roots)})
        return
    if probe.read(frozen) != pin:
        raise ValueError("Frozen patch experiment drift")
    probe.RUN = engine.RUN.with_name(f"{HERE.name}_{benchmark}")
    engine.CAP = {"Patch": 2 * len(roots), engine.RPE: 2 * len(roots), "BenchNative": 12 * len(roots)}
    live, ledger = action == "run", []
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    with probe.runner_lock(probe.RUN / "runner.lock"):
        probe.freeze(engine.OUT / "EXECUTION.json", identity)

        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, identity, live, ledger, cache) if jobs else {}

        rows = generation(roots, drafts, packets, stage)
        if benchmark == "RPEval":
            touched = []
            for row in rows:
                if row["actor_status"] != "OK":
                    continue
                if row["answer"] == drafts[row["uid"]]:
                    case = aux["rpe_panel"][row["uid"]]
                    card = case["cells"][case["base"]]
                    row["score"] = {"match": {"matched": card["matched"], "positions": case["positions"]},
                                    **card["fields"]}
                    row["score_origin"] = "EXACT_IPE_C"
                else:
                    touched.append(row)
            engine.grade_rpe(roots, touched, stage)
            paired = {}
        else:
            transfer = engine.transfer
            cases = aux["cases"]

            def dispatch(jobs):
                requests = {(uid, f"{arm}/{metric}"): req for (uid, arm, metric), req in jobs.items()
                            if sha(req) not in aux["conflicts"]}
                received = stage("BenchNative", requests, aux["cache"])
                return {key: ({"status": "AMBIGUOUS_ARCHIVED_SCORE", "request_sha256": sha(req), "answer": None}
                              if sha(req) in aux["conflicts"] else received[key[0], f"{key[1]}/{key[2]}"])
                        for key, req in jobs.items()}

            transfer.grade(benchmark, rows, cases, aux["protocol"], dispatch)
            scores = {(r["uid"], r["method"]): r["score"] for r in (*aux["controls"], *rows)
                      if r["uid"] in cases and r["score"] is not None}
            paired = {m: transfer.bench_pair(m, "HISTORY", cases, scores)
                      for m in ("CURRENT", *aux["references"])}
            paired["CURRENT_vs_GATE"] = transfer.bench_pair("GEPA_SELECTED_BOUNDS", "CURRENT", cases, scores)
        result = {"rows": rows, "pairs": paired, "ledger": ledger,
                  "calls": Counter(r["unit"]["stage"] for r in ledger),
                  "statuses": Counter(r["status"] for r in ledger),
                  "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        if live:
            probe.freeze(engine.OUT / "RESULTS.json", result)
        elif probe.read(engine.OUT / "RESULTS.json") != result:
            raise ValueError("Patch replay drift")
        print(json.dumps({k: result[k] for k in ("calls", "statuses", "tokens")}, ensure_ascii=False))


if __name__ == "__main__":
    cli = ArgumentParser()
    cli.add_argument("action", choices=("freeze", "run", "replay"))
    cli.add_argument("benchmark", choices=("RPEval", "BenchPreS"))
    args = cli.parse_args()
    execute(args.action, args.benchmark)
