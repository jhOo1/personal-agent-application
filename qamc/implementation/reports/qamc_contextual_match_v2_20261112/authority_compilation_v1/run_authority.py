"""Run the frozen comparison using the existing physical request journal and judges."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import parse_object, sha

from authority import compile_answer, compile_public, personal_wires, public_wire
from freeze_panel import freeze, read
from preflight import public_roots
import run_v41 as transport
import transfer_edit as transfer

OUT = Path(__file__).resolve().parent
RUN = transport.RUN.with_name(OUT.name)
probe = transport.probe
ARMS = ("GENERIC", "AUTHORITY")
PUBLIC, FINAL, RPE, BENCH, PERSIST = "Public", "Final", transport.NATIVE, "BenchJudge", "PersistJudge"
CAP = {PUBLIC: 16, FINAL: 32, RPE: 8, BENCH: 48, PERSIST: 16}
GATE, RP = transport.GATE, transport.RP


def stage(name, jobs, plan, live, ledger, cache=None):
    if len(jobs) > CAP[name]:
        raise ValueError(f"{name} exceeds its frozen budget")
    cached = {} if cache is None else cache
    unique, aliases = {}, {}
    for key, wire in jobs.items():
        digest = sha(wire)
        aliases[key] = digest
        if digest not in cached:
            unique.setdefault(digest, (key, wire))
    settings = {(wire["model"], wire["max_tokens"], wire["temperature"])
                for _, wire in unique.values()}
    if len(settings) > 1:
        raise ValueError(f"{name} has incompatible sampling settings")
    values = {digest: {"status": "OK", "answer": cached[digest], "request_sha256": digest,
                       "origin": "EXACT_ARCHIVE"} for digest in set(aliases.values()) & cached.keys()}
    if unique:
        model, cap, temperature = settings.pop()
        protocol = {"experiment": OUT.name, "model": model, "concurrency": 8, "spacing_seconds": 3.2,
                    "stages": {name: {"max_tokens": cap, "temperature": temperature}}, "automatic_retries": 0}
        manifest = {"protocol": protocol, "units": [
            {"unit": {"stage": name, "root_id": uid, "method": arm,
                      "replicate": 0, "protocol_sha256": sha(protocol)}, "request": wire}
            for (uid, arm), wire in unique.values()
        ]}
        if live:
            probe.freeze(OUT / f"{name}_MANIFEST.json", manifest)
            transport.dispatch(plan, name, manifest)
        elif probe.read(OUT / f"{name}_MANIFEST.json") != manifest:
            raise ValueError(f"{name} request manifest changed")
        receipts = probe.stage_receipts(name)
        for digest, (key, _) in unique.items():
            record, answer = receipts[key]
            if not record or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise RuntimeError(f"{name} has undelivered or unsettled units")
            if record["request_sha256"] != digest or (record["status"] == "OK" and not answer):
                raise ValueError(f"{name} receipt is inconsistent")
            ledger.append(record)
            values[digest] = {"status": record["status"], "answer": answer,
                              "request_sha256": digest, "origin": "LOCAL_RECEIPT"}
    return {key: values[digest] for key, digest in aliases.items()}


def generate(roots, execute):
    shared = execute(PUBLIC, {(uid, "PUBLIC"): public_wire(root) for uid, root in roots.items()})
    public, issues, jobs = {}, {}, {}
    for uid, root in roots.items():
        response = shared[uid, "PUBLIC"]
        if response["status"] != "OK":
            issues[uid] = response["status"]
            continue
        try:
            public[uid] = compile_public(response["answer"])
        except (TypeError, ValueError) as error:
            issues[uid] = "INVALID_PUBLIC_CONTRACT: " + str(error)
            continue
        order = personal_wires(root, public[uid])
        arms = ARMS if int(sha(uid)[0], 16) % 2 else ARMS[::-1]
        jobs.update({(uid, arm): order[arm] for arm in arms})
    replies = execute(FINAL, jobs)
    rows = []
    for uid, root in roots.items():
        for arm in ARMS:
            answer, error = None, issues.get(uid)
            reply = replies.get((uid, arm))
            status = reply["status"] if reply else "NO_USABLE_PUBLIC"
            if status == "OK":
                answer = reply["answer"]
                if arm == "AUTHORITY":
                    try:
                        answer = compile_answer(root["public_task"], public[uid], answer, root["original_sources"])
                    except (KeyError, TypeError, ValueError) as issue:
                        answer, status, error = None, "INVALID_PERSONAL_CONTRACT", str(issue)
            rows.append({"uid": uid, "method": arm, "actor_status": status, "answer": answer,
                         "error": error, "actor_request_sha256": reply["request_sha256"] if reply else None,
                         "public_request_sha256": shared[uid, "PUBLIC"]["request_sha256"],
                         "raw_personal_response": reply["answer"] if reply and arm == "AUTHORITY" else None,
                         "score": None})
    return public, issues, rows


def rpe_wire(parent, case, row):
    request, = transport.formal.grading_jobs(parent, [case], [{**row, "method": GATE}])
    return request["request"]


def grade_rpe(roots, rows, execute):
    parent = probe.read(transport.formal.OUT / "PLAN.json")
    cases = transport.author_cases(parent)
    jobs = {(row["uid"], row["method"]): rpe_wire(parent, cases[row["uid"]], row)
            for row in rows if row["actor_status"] == "OK"}
    cached = {}
    for uid in {uid for uid, _ in jobs}:
        for name, archived in roots[uid]["archived"].items():
            if archived["raw_judge"]:
                wire = rpe_wire(parent, cases[uid], {"uid": uid, "actor_status": "OK",
                                                     "answer": archived["answer"]})
                digest = sha(wire)
                previous = cached.setdefault(digest, archived["raw_judge"])
                if previous != archived["raw_judge"]:
                    raise ValueError(f"Ambiguous exact RPEval legacy grade: {uid}/{name}")
    received = execute(RPE, jobs, cached)
    for row in rows:
        result = received.get((row["uid"], row["method"]))
        row["judge"] = result
        if result and result["status"] == "OK":
            try:
                row["score"], row["invalid"] = probe.fields(
                    parse_object(result["answer"]), len(roots[row["uid"]]["original_sources"]), True)
            except (KeyError, TypeError, ValueError) as error:
                row["score_error"] = str(error)


def grade_other(benchmark, rows, execute):
    cases, protocol, controls = transfer.context(benchmark)
    panel = {row["uid"] for row in rows}
    cases = {uid: case for uid, case in cases.items() if uid in panel}
    archive = transfer.archived_answers(benchmark, cases)
    exact, _ = transfer.matching_grading_receipts(benchmark, cases, protocol, archive)

    def dispatch(jobs):
        keyed = {(uid, arm + "/" + metric): wire for (uid, arm, metric), wire in jobs.items()}
        returned = execute(BENCH if benchmark == "BenchPreS" else PERSIST, keyed, exact)
        return {key: returned[key[0], key[1] + "/" + key[2]] for key in jobs}

    transfer.grade(benchmark, rows, cases, protocol, dispatch)
    scores = {(row["uid"], row["method"]): row["score"]
              for row in (*controls, *rows) if row["score"] is not None}
    pair = transfer.bench_pair if benchmark == "BenchPreS" else transfer.persist_pair
    comparators = (GATE, RP) if benchmark == "BenchPreS" else (GATE, RP, "PB_RUBRIC", "PB_GEPA")
    return {name: pair(name, "AUTHORITY", cases, scores) for name in ("GENERIC", *comparators)}


def main(action):
    frozen = probe.read(OUT / "FROZEN.json")
    if frozen != freeze() or sum(CAP.values()) != frozen["max_generation_requests"] + frozen["max_grading_requests"]:
        raise ValueError("Panel, implementation or physical cap changed")
    roots_by_name = {uid: root for _, root in public_roots() if (uid := root["uid"]) in
                     {cell["uid"] for cell in frozen["panel"]}}
    roots = {cell["uid"]: roots_by_name[cell["uid"]] for cell in frozen["panel"]}
    probe.OUT, probe.RUN = OUT, RUN
    if action == "check":
        print(json.dumps({"roots": len(roots), "distinct_public": len({sha(public_wire(r)) for r in roots.values()}),
                          "caps": CAP, "new_calls": 0}, indent=2))
        return
    live = action == "run"
    plan_path, state_path = OUT / "EXECUTION.json", OUT / "RUN_STATE.json"
    if live:
        pin = {"service_reference_sha256": probe.read_reference()[1], "panel_sha256": sha(frozen),
               "runner_sha256": sha(Path(__file__).read_text()), "caps": CAP}
        probe.freeze(plan_path, pin)
        probe.atomic_json(state_path, {"state": "RUNNING"})
    plan = probe.read(plan_path)
    ledger = []

    def execute(name, jobs, cache=None):
        return stage(name, jobs, plan, live, ledger, cache)

    try:
        public, issues, rows = generate(roots, execute)
        sets = {name: {cell["uid"] for cell in frozen["panel"] if cell["benchmark"] == name}
                for name in ("RPEval", "BenchPreS", "PersistBench")}
        rpe = [row for row in rows if row["uid"] in sets["RPEval"]]
        grade_rpe(roots, rpe, execute)
        comparisons = {name: grade_other(name, [row for row in rows if row["uid"] in sets[name]], execute)
                       for name in ("BenchPreS", "PersistBench")}
        groups = Counter(record["unit"]["stage"] for record in ledger)
        if any(total > CAP[name] for name, total in groups.items()):
            raise ValueError("Physical ledger exceeds the frozen allocation")
        result = {"public": public, "public_failures": issues, "rows": rows, "comparisons": comparisons,
                  "ledger": ledger, "request_counts": groups,
                  "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        if live:
            probe.freeze(OUT / "RESULTS.json", result)
            probe.atomic_json(state_path, {"state": "COMPLETE", "physical_requests": len(ledger)})
        elif probe.read(OUT / "RESULTS.json") != result:
            raise ValueError("Saved results differ from the verified replay")
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state_path, {"state": "STOPPED", "error": str(error)})
        raise


if __name__ == "__main__":
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("check", "run", "report"))
    args = cli.parse_args()
    if args.action == "run":
        with probe.runner_lock(RUN / "runner.lock"):
            main(args.action)
    else:
        main(args.action)
