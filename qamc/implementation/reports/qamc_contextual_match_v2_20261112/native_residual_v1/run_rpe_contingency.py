"""Compare draft review strategies on fixed, exposed IPE-C history routes."""
import argparse
import json
from pathlib import Path

from audit_rpe_protected_repairs import scan
from incremental_panel import HERE, prior, read, sha
from run_probe import engine, probe

OUT = HERE / "rpe_contingency_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "ContingencyActor"
PANEL = HERE / "RPE_CONTINGENCY_PANEL.json"
PREFIX = "rpeval/formal_multi_v1/"
SCREEN = {
    "unresolved_step": ("explicit/008", "explicit/090", "explicit/129", "implicit/116"),
    "existing_replacement": ("explicit/024", "implicit/098"),
    "already_feasible": ("explicit/014", "explicit/070"),
    "soft_only": ("explicit/036", "explicit/042"),
    "history_all_A": ("implicit/102", "implicit/103"),
}
COMMON = (
    "Review the archived draft against the original request, evidence and policy. "
    "Keep established facts, appropriate preferences, participant scope and the requested deliverable. "
    "Correct a step that is clearly incompatible with an applicable constraint. Do not invent facts, "
    "availability or participant characteristics. Make only useful changes and return a complete "
    "user-facing answer in the requested language. Do not include analysis or mention this audit. "
)
PROMPTS = {
    "ORDINARY": COMMON + (
        "Improve practicality, completeness and correct use of preferences. Assess relevant "
        "uncertainties and consider concrete alternatives or contingencies where useful. You can revise "
        "any part of the draft, or keep it as is if adequate."
    ),
    "TWO_STATE": COMMON + (
        "For an actual draft step whose feasibility under an applicable constraint depends on an "
        "unresolved, observable condition, consider normal execution and triggered execution separately. "
        "Keep the normal step when feasible, and say exactly which feasible step replaces it if the "
        "condition is triggered. Preserve the original purpose and unaffected steps. If the original "
        "is adequate, including when it already has a sufficient replacement, add no contingency. "
        "Do not turn a soft preference into a prerequisite."
    ),
}


def prepare():
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development cases")
    roots = {r["uid"]: r for r in frozen["roots"]}
    archive = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
               if r["method"] == "RPR_PAPER_FULL"}
    base = {r["uid"]: r for r in read(HERE.parent / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    excluded = {r["group"] for r in scan()["candidates"]}
    panel, jobs, groups = [], {}, set()
    for kind, tasks in SCREEN.items():
        for task in tasks:
            uid = PREFIX + task
            row, reference = archive[uid], base[uid]
            group, labels = reference["source_group"], set(reference["labels"])
            if group in groups or group in excluded or uid not in roots:
                raise ValueError(f"Development group mismatch: {uid}")
            groups.add(group)
            if (reference["old_route"] != "REUSE_RP"
                    or kind == "soft_only" and ("B" not in labels or "C" in labels)
                    or kind == "history_all_A" and labels != {"A"}
                    or kind not in {"soft_only", "history_all_A"} and "C" not in labels):
                raise ValueError(f"Stratum or route mismatch: {uid}")
            wire, draft = row["actor_request"], row["answer"]
            if (sha(wire) != row["actor_request_sha256"] or wire["model"] != "qwen3.8-flash"
                    or sha(draft.strip()) != reference["ipe_c"]["answer_sha256"]):
                raise ValueError(f"Baseline evidence or answer drift: {uid}")
            system, user = wire["messages"]
            payload = json.loads(user["content"])
            if "archived_draft" in payload or user["role"] != "user" or system["role"] != "system":
                raise ValueError(f"Unexpected archive contract: {uid}")
            data = {**user, "content": json.dumps({**payload, "archived_draft": draft}, ensure_ascii=False)}
            order = sorted(PROMPTS, key=lambda arm: sha([uid, arm]))
            requests = {}
            for arm in order:
                new_system = {**system, "content": system["content"] + "\n\n" + PROMPTS[arm]}
                request = {**wire, "messages": [new_system, data]}
                jobs[uid, arm] = request
                requests[arm] = sha(request)
            panel.append({"uid": uid, "group": group, "stratum": kind,
                          "base_wire_sha256": sha(wire), "base_answer_sha256": sha(draft.strip()),
                          "request_sha256": requests})
    return panel, jobs, {card["uid"]: roots[card["uid"]] for card in panel}, base


def main(action):
    panel, jobs, roots, base = prepare()
    if action == "freeze":
        probe.freeze(PANEL, panel)
    if panel != read(PANEL):
        raise ValueError("Frozen roster/request drift")
    if action != "run":
        print(f"{len(panel)} exposed source groups, {len(jobs)} Actor and at most {len(jobs)} Judge calls")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, {STAGE: len(jobs), engine.RPE: len(jobs)}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([panel, sha(Path(__file__).read_bytes())]),
    }
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, identity, True, ledger, cache) if wires else {}

        replies = dispatch(STAGE, jobs)
        rows = []
        for (uid, arm), response in replies.items():
            rows.append({"uid": uid, "method": arm, "actor_status": response["status"],
                         "answer": response.get("answer"), "score": None,
                         "base_score": base[uid]["ipe_c"]["grade"]})
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    main(parser.parse_args().action)
