"""Compare two extractive prompts on one frozen source per RPEval task."""
import argparse
import json
import re

from freeze_rpe_projection_panel import OUT as PANEL, build
from incremental_panel import HERE, prior, read, sha
from rpe_source_projection import project
from run_probe import engine, probe

OUT = HERE / "rpe_projection_comparison_v1"
RUN = engine.RUN.with_name(OUT.name)
MODES = ("ordinary", "conditions")
COMMON = (
    'Select task-relevant, verbatim passages from this single historical source. '
    'Return only JSON {"ids":[1]} with ascending distinct passage IDs, or {"ids":[]} '
    'if extraction is unsuitable. Respect the character budget including separators. '
    'Use the actual query; do not answer it.'
)
EXTRA = (
    " Include any preceding passage needed to resolve attribution, negation, time, "
    "participants, or a conditional statement. Do not retain dependent replies in isolation "
    "or generalize a historical episode into an enduring preference. If those dependencies "
    "do not fit, return no IDs."
)


def prepare():
    panel = read(PANEL)
    if panel != build():
        raise ValueError("Panel drift")
    v41 = prior.R["archived"].v41
    roots = {r["uid"]: r for r in read(v41.OUT / "FROZEN.json")["roots"]}
    originals = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
                 if r["method"] == "RPR_PAPER_FULL" and r["actor_status"] == "OK"}
    plans, inputs = {}, {}
    for card in panel:
        uid = card["uid"]
        wire = originals[uid]["actor_request"]
        if sha(wire) != card["actor_sha256"]:
            raise ValueError("Original request drift")
        packet = json.loads(wire["messages"][1]["content"])
        source, = (row["text"] for row in packet["source_evidence"]
                   if row["memory_id"] == card["source_id"])
        spans = [m.span() for m in re.finditer(r"[^\n]+", source)]
        budget = len(source) // 2
        payload = json.dumps({"query": packet["query"], "character_budget": budget,
                              "passages": {i: source[a:b] for i, (a, b) in enumerate(spans, 1)}},
                             ensure_ascii=False)
        for mode in MODES:
            plans[uid, mode] = {**wire, "messages": [
                {"role": "system", "content": COMMON + (EXTRA if mode == "conditions" else "")},
                {"role": "user", "content": payload},
            ]}
        inputs[uid] = (card, wire, spans, budget, originals[uid])
    return plans, inputs, {uid: roots[uid] for uid in inputs}


def run(check):
    plans, inputs, roots = prepare()
    caps = {"Extract": len(plans), "ProjectionAnswer": len(plans), engine.RPE: len(plans)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([read(PANEL), sorted((list(k), sha(v)) for k, v in plans.items()),
                                          sha((HERE / "run_rpe_projection_comparison.py").read_bytes()),
                                          sha((HERE / "rpe_source_projection.py").read_bytes())])}
    if check:
        print(len(inputs), caps)
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, batch, cache=None):
            return engine.stage(stage, batch, identity, True, ledger, cache) if batch else {}

        rows, jobs = [], {}
        for (uid, mode), reply in dispatch("Extract", plans).items():
            card, original, spans, budget, archived = inputs[uid]
            row = {"uid": uid, "method": mode, "group": card["group"],
                   "base_score": card["base_score"], "actor_status": reply["status"],
                   "answer": None, "score": None, "selected": None, "fallback": False}
            rows.append(row)
            if reply["status"] != "OK":
                continue
            try:
                ids = json.loads(reply["answer"])["ids"]
                if (not isinstance(ids, list) or any(type(i) is not int or i < 1 or i > len(spans) for i in ids)
                        or ids != sorted(set(ids))):
                    raise ValueError("Invalid IDs")
                selected = [spans[i - 1] for i in ids]
                length = sum(b - a for a, b in selected) + max(0, len(selected) - 1) * len("\n[…]\n")
                if length > budget:
                    raise ValueError("Over character budget")
                wire = project(original, card["actor_sha256"], card["source_id"], selected)
            except (ValueError, KeyError, TypeError):
                row["actor_status"] = "INVALID_EXTRACTION"
                continue
            row["selected"] = ids
            if wire == original:
                row.update(actor_status="OK", answer=archived["answer"], score=archived["native_fields"],
                           fallback=True)
            else:
                jobs[uid, mode] = wire
        replies = dispatch("ProjectionAnswer", jobs)
        for row in rows:
            reply = replies.get((row["uid"], row["method"]))
            if reply:
                row.update(actor_status=reply["status"], answer=reply.get("answer"))
        engine.grade_rpe(roots, [row for row in rows if not row["fallback"]], dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    run(parser.parse_args().action == "check")
