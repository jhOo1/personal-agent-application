"""Run the two frozen, same-Actor-cap PersistBench risk waves."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

from complete import engine, normalized, probe, read
from qamc.common import sha

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
ARMS = ("ROUTED", "EMPTY", "FULL")
TRACKS = {"sycophancy": 11, "cross_domain": 8}
WAVES = (1, 2)
STAGE_LIMITS = {"Route": 1, "Select": 1, "Actor": len(ARMS), "Judge": len(ARMS)}


def prepare():
    prior = run_path(str(HERE.parent / "persist_repeated_deployment_v1/run.py"))
    prior_pin, cases, data, factorial, judge, bounds = prior["prepare"]()
    if prior_pin != read(prior["RUN"] / "FROZEN.json"):
        raise ValueError("Original risk allocation drift")
    cases = {uid: case for uid, case in cases.items() if case["category"] in TRACKS}
    if (Counter(c["category"] for c in cases.values()) != TRACKS
            or len({c["group_id"] for c in cases.values()}) != len(cases)):
        raise ValueError("Expected the 19 reserved exposed source roots")
    if len({data[uid][0]["query"] for uid in cases}) != len(cases):
        raise ValueError("Duplicate queries require task-scoped dispatch deduplication")
    orders = {str(w): sorted(cases, key=lambda u: sha(["equal-cap-risk", w, u])) for w in WAVES}
    wires = {}
    for uid, case in cases.items():
        public, route_inputs, archive = data[uid]
        query, memories = public["query"], public["memories"]
        full = actor_wire(prior, factorial, case, query, memories)
        empty = actor_wire(prior, factorial, case, query, [])
        archived = archive["PB_GEPA"]
        if full != dict(archived, max_tokens=8192):
            raise ValueError("Full-history request drift beyond Actor output cap")
        if empty["messages"] == full["messages"] or any(
                empty[k] != full[k] for k in full if k != "messages"):
            raise ValueError("Endpoints must differ only in rendered evidence")
        wires[uid] = {"route_inputs": route_inputs, "EMPTY": empty, "FULL": full}
    files = ("PROTOCOL.md", "run_safety.py")
    pin = {
        "tracks": {uid: c["category"] for uid, c in cases.items()},
        "orders": orders,
        "arms": list(ARMS),
        "cap": sum(STAGE_LIMITS.values()) * len(cases) * len(WAVES),
        "wire_sha256": sha(wires),
        "public_sha256": sha({uid: data[uid][0] for uid in cases}),
        "source_groups_sha256": sha({uid: c["group_id"] for uid, c in cases.items()}),
        "judge_sha256": sha([judge, {uid: bounds[uid] for uid in cases}]),
        "sources": {name: sha((HERE / name).read_bytes()) for name in files},
        "actor_sha256": prior_pin["actor_protocol"],
    }
    return pin, prior, cases, data, wires, factorial, judge, bounds


def actor_wire(prior, factorial, case, query, memories):
    wire = prior["actor_request"](case, query, memories, factorial, factorial["prompts"]["gepa"])
    if wire["max_tokens"] != 8192:
        raise ValueError("Actor output cap is unequal")
    return wire


def wave(number, order, prior, cases, data, wires, factorial, judge, bounds, identity, ledger):
    persist = prior["persist"]
    scorer = persist.author.ext.parent.persist
    _, rubrics, formatter = scorer.upstream()
    routed = "ROUTED"

    def dispatch(label, payload):
        stage = f"Wave{number}_{label}"
        engine.CAP[stage] = STAGE_LIMITS[label] * len(order)
        return engine.stage(stage, payload, identity, True, ledger) if payload else {}

    routes = dispatch("Route", {(u, routed): wires[u]["route_inputs"]["query"] for u in order})
    branches, failures, select_jobs = {}, {}, {}
    for (uid, arm), record in routes.items():
        if record["status"] != "OK":
            failures[uid] = record["status"]
            continue
        try:
            router = prior["transfer"].confirmation.route
            route = router.decode(record["answer"], data[uid][0]["query"])
            branches[uid] = "style" if route["check_history"] else "grounding"
            select_jobs[uid, arm] = wires[uid]["route_inputs"][branches[uid]]
        except (ValueError, TypeError, KeyError):
            failures[uid] = "INVALID_ROUTE"

    selected, selected_wires = {}, {}
    for (uid, arm), record in dispatch("Select", select_jobs).items():
        if record["status"] != "OK":
            failures[uid] = record["status"]
            continue
        try:
            task = data[uid][0]
            evidence = prior["select"](cases[uid], task, routes[uid, arm]["answer"], record["answer"])
            selected[uid] = evidence
            selected_wires[uid] = actor_wire(prior, factorial, cases[uid], task["query"], evidence)
        except (ValueError, TypeError, KeyError):
            failures[uid] = "INVALID_SELECTION"
    actor_jobs = {}
    for uid in order:
        for arm in ARMS:
            if arm != routed:
                actor_jobs[uid, arm] = wires[uid][arm]
            elif uid in selected_wires:
                actor_jobs[uid, arm] = selected_wires[uid]

    answers = dispatch("Actor", actor_jobs)
    grade_jobs = {}
    for (uid, arm), answer in answers.items():
        if answer["status"] == "OK":
            public = data[uid][0]
            category = cases[uid]["category"]
            grading = persist.author.ext.text_request(
                rubrics[category], formatter["build_judge_prompt"](
                    public["memories"], public["query"], answer["answer"]),
                judge["model"], judge["stages"][persist.STAGE]["max_tokens"])
            if normalized(grading, answer["answer"]) != bounds[uid]:
                raise ValueError("Scoring envelope drift")
            grade_jobs[uid, arm] = grading
    scores = dispatch("Judge", grade_jobs)
    rows = []
    for uid in order:
        for arm in ARMS:
            answer = answers.get((uid, arm), {})
            score_reply = scores.get((uid, arm), {})
            category = cases[uid]["category"]
            status = score_reply.get("status", answer.get(
                "status", failures.get(uid, "UNISSUED") if arm == routed else "UNISSUED"))
            score = None
            if score_reply.get("status") == "OK":
                try:
                    score = scorer.score(category, score_reply["answer"])
                except (ValueError, TypeError, KeyError):
                    status = "INVALID_SCORE"
            rows.append({
                "uid": uid, "wave": number, "arm": arm, "category": category, "status": status,
                "answer": answer.get("answer"), "actor_sha256": answer.get("request_sha256"),
                "judge": score_reply, "score": score,
                "branch": branches.get(uid) if arm == routed else None,
                "selected_count": len(selected[uid]) if arm == routed and uid in selected else None,
                "selected_sha256": sha(selected[uid]) if arm == routed and uid in selected else None,
            })
    return rows


def run(pin, *inputs):
    if pin != read(RUN / "FROZEN.json"):
        raise ValueError("Frozen allocation drift")
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    rows, ledger = [], []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        for number in WAVES:
            checkpoint = RUN / f"WAVE{number}.json"
            if checkpoint.exists():
                saved = read(checkpoint)
                if saved["identity"] != identity:
                    raise ValueError("Checkpoint identity drift")
            else:
                calls = []
                outcomes = wave(number, pin["orders"][str(number)], *inputs, identity, calls)
                saved = {"identity": identity, "rows": outcomes, "ledger": calls}
                probe.freeze(checkpoint, saved)
            rows.extend(saved["rows"])
            ledger.extend(saved["ledger"])
        if len(ledger) > pin["cap"]:
            raise ValueError("Dispatch exceeded frozen cap")
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("check", "freeze", "run"))
    args = cli.parse_args()
    frozen, *prepared = prepare()
    if args.action == "freeze":
        probe.freeze(RUN / "FROZEN.json", frozen)
    elif args.action == "run":
        run(frozen, *prepared)
    print(json.dumps({"track_counts": Counter(frozen["tracks"].values()),
                      "waves": list(WAVES), "max_requests": frozen["cap"], "sha256": sha(frozen)}))
