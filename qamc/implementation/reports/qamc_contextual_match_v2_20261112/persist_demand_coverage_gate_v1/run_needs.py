"""Run only the need proposal and local scoring qualification."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from audit_memgate import BU, load_gate, prepare
from complete import engine, probe, read, persist
from coverage_selection import select
from extend import archived, merge_stage
from qamc.common import sha
import torch

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
STAGE = "TaskNeeds"
ARM = "NEEDS"


def decode(raw):
    if raw.strip().startswith("```json") and raw.strip().endswith("```"):
        raw = raw.strip()[7:-3]
    value = json.loads(raw)
    if not isinstance(value, dict) or list(value) != ["needs"]:
        raise ValueError("Expected one needs list")
    needs = value["needs"]
    if (not isinstance(needs, list) or len(needs) > 4
            or any(not isinstance(x, str) or not 1 <= len(x.strip()) <= 240 for x in needs)
            or len({x.strip().casefold() for x in needs}) != len(needs)):
        raise ValueError("Invalid needs list")
    return [x.strip() for x in needs]


def take(assets, embedding):
    inherited, _, _, selections, _, tasks, _ = prepare(assets, embedding)
    choices = {
        uid: t for uid, t in tasks.items()
        if selections[uid]["category"] == BU or uid.split("/")[-1].startswith(("0613beea", "9a0a7438"))
    }
    if Counter(selections[u]["category"] for u in choices) != {BU: 12, "sycophancy": 2}:
        raise ValueError("Development scope changed")
    prompt = (HERE / "NEEDS_PROMPT.md").read_text().strip()
    jobs = {(uid, ARM): persist.author.ext.text_request(prompt, t["query"], "qwen3.8-flash", 4096)
            for uid, t in choices.items()}
    if any(w["messages"][1]["content"] != choices[u]["query"] or w.get("temperature") != 0
           for (u, _), w in jobs.items()):
        raise ValueError("Task-only wire changed")
    # Each term is only used to verify an evaluation-layer source identity.
    specs = {
        "125d165e": (("pescet", "pescat"), ("shellfish",), ("strong dislike of all seafood", "dislikes all seafood", "doesn't like seafood", "dislikes seafood")),
        "a3e8272d": (("pancreatitis",),),
        "dbcf603f": (("cat allerg",), ("vegan",)),
        "0613beea": (("waterfall",), ("agile",)),
        "9a0a7438": (("agile",), ("gantt",)),
    }
    criteria = {}
    fallback_positions = {"125d165e": (4, 5, 6)}
    for short, groups in specs.items():
        uid, = (u for u in choices if u.split("/")[-1].startswith(short))
        indices = []
        for group in groups:
            hits = [idx for idx, s in enumerate(choices[uid]["memories"]) if any(term in s.casefold() for term in group)]
            if len(hits) != 1 and short in fallback_positions:
                hits = [fallback_positions[short][len(indices)]]
            if len(hits) != 1:
                raise ValueError("Frozen behavior source did not map uniquely")
            indices.append(hits[0])
        criteria[uid] = {"positions": indices, "kind": "BU" if selections[uid]["category"] == BU else "RISK"}
    pin = {"scope_sha256": sha(choices), "criteria_sha256": sha(criteria), "request_sha256": sha(
        {uid: w for (uid, _), w in jobs.items()}), "parent": inherited,
        "code_sha256": {f: sha((HERE / f).read_bytes()) for f in
                        ("coverage_selection.py", "run_needs.py", "PROTOCOL.md", "NEEDS_PROMPT.md")}}
    return choices, jobs, criteria, pin


def execute(assets, embedding, choices, jobs, criteria, pin, cache):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(jobs)}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger, rows = [], []
    torch.set_num_threads(2)
    gate, _ = load_gate(assets, embedding)
    with probe.runner_lock(RUN / "runner.lock"), torch.no_grad():
        probe.freeze(RUN / "EXECUTION.json", identity)
        replies = merge_stage(STAGE, jobs, cache, identity, ledger)
        for (uid, _), reply in replies.items():
            row = {"uid": uid, "status": reply["status"]}
            rows.append(row)
            if reply["status"] != "OK":
                continue
            try:
                needs = decode(reply["answer"])
            except (ValueError, TypeError, KeyError):
                row["status"] = "INVALID_NEEDS"
                continue
            task = choices[uid]
            q, m = task["query"], task["memories"]
            variants = [q, *(f"{q}\nInformation needed to complete this same task: {need}" for need in needs)]
            matrix = [gate.score_candidates(query, m) for query in variants]
            base, independent, cover = select(matrix)
            row.update(needs=needs, base=base, independent=independent, cover=cover, matrix=matrix)
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger, "criteria": criteria})


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "run"))
    cli.add_argument("assets", type=Path)
    cli.add_argument("embedding", type=Path)
    args = cli.parse_args()
    choices, jobs, criteria, pin = take(args.assets, args.embedding)
    if args.action == "freeze":
        cache, _ = archived(jobs, HERE.parents[2])
        probe.freeze(RUN / "FROZEN.json", {"pin": pin, "cache": {u: row for (u, _), row in cache.items()}})
    else:
        frozen = read(RUN / "FROZEN.json")
        if pin != frozen["pin"]:
            raise ValueError("Experimental contract drift")
        cache = {(u, ARM): row for u, row in frozen["cache"].items()}
        execute(args.assets, args.embedding, choices, jobs, criteria, pin, cache)
    print(json.dumps({"request_bound": len(jobs) - len(cache), "case_count": len(choices), "fingerprint": sha(pin)}))


if __name__ == "__main__":
    main()
