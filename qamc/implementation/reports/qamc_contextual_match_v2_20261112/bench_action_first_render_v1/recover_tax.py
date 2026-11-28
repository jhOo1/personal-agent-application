"""Render the saved tax response without the extra closing-line cap, as a separate diagnostic."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
parent = run_path(str(HERE / "trial.py"))
archive, engine, probe, sha = (parent[k] for k in ("archive", "engine", "probe", "sha"))
RUN = parent["RUN"].with_name("bench_action_first_tax_recovery_v1")
OUT = RUN / "private"
LABEL = "tax_discrepancy"
STAGE = "BenchTaxRenderGrade"


def prepare():
    cards, grader, jobs, original_pin = parent["prepare"]()
    if original_pin != archive.read(parent["PRIVATE"] / "FROZEN.json"):
        raise ValueError("Original roster drift")
    original = archive.read(parent["PRIVATE"] / "RESULTS.json")
    if original["failures"].get(LABEL + "/STRUCTURED") != "INVALID_MESSAGE":
        raise ValueError("Require the original recorded rejection")
    digest = sha(jobs[LABEL, "STRUCTURED"])
    matches = []
    for path in (parent["RUN"] / parent["ACTOR"]).glob("visible/*/record.json"):
        record = archive.read(path)
        if record["request_sha256"] == digest and record["status"] == "OK":
            if sha(archive.read(path.with_name("request.json"))) != digest:
                raise ValueError("Saved Actor response does not match its input")
            matches.append(path)
    if len(matches) != 1:
        raise ValueError("Expected exactly one original tax response")
    raw = archive.read(matches[0].with_name("response.json"))["answer"]
    parts = parent["parse_object"](raw)
    try:
        parent["render"](raw)
    except ValueError as e:
        if str(e) != "Unexpected header or closing":
            raise
    else:
        raise ValueError("Original renderer already accepts it")
    pattern = {"ACTION_FIRST": ("header", "actions", "context", "closing"),
               "CONTEXT_FIRST": ("header", "context", "actions", "closing")}
    final = {a: "\n\n".join(parts[k].strip() for k in fields if parts[k].strip())
             for a, fields in pattern.items()}
    if final["ACTION_FIRST"] == final["CONTEXT_FIRST"] or Counter(final["ACTION_FIRST"].split()) != Counter(
        final["CONTEXT_FIRST"].split()
    ):
        raise ValueError("Expected differing order with identical words")
    card, run = cards[LABEL], parent["run"]
    ref = run.read(run.ROOT / card["case"]["evaluation_path"])
    if parent["digest"](ref) != card["case"]["evaluation_hash"]:
        raise ValueError("Unbound scorer parameters")
    wires = {}
    for arm, answer in final.items():
        for tag, system, content in run.prior.score.initial_requests(run.ROOT, "benchpres", ref, card["packet"]["query"], answer):
            wires[arm, tag] = run.prior.text_request(system, content, grader["model"], grader["stages"][tag]["max_tokens"])
    if len(wires) != 12:
        raise ValueError("Unexpected diagnostic budget")
    pin = {"original_actor_sha256": digest, "baseline_answer_sha256": sha(raw),
           "score_requests_sha256": sha(list(wires.values())), "launcher": sha(Path(__file__).read_bytes()),
           "reference": probe.read_reference()[1]}
    return pin, ref, wires


def main(live):
    pin, ref, wires = prepare()
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if live:
        probe.freeze(OUT / "FROZEN.json", pin)
    elif archive.read(OUT / "FROZEN.json") != pin:
        raise ValueError("Frozen diagnostic changed")
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {STAGE: 12}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        checkpoint = OUT / "ARCHIVE.json"
        if live and not checkpoint.exists():
            found, _ = parent["previous"]["support"]["prior"]["find_archived"](wires, HERE.parents[2])
            checked = []
            for (arm, field), item in found.items():
                meta = (HERE.parents[2] / item["archive"]).parent / "visible" / item["archive_unit"] / "record.json"
                ref_hash = archive.read(meta).get("reference_config_sha256") if meta.is_file() else None
                if item["status"] == "OK" and ref_hash != pin["reference"]:
                    item = dict(item, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                checked.append([arm, field, item])
            probe.freeze(checkpoint, checked)
        known = {(arm, field): r for arm, field, r in archive.read(checkpoint)}
        if any(sha(wires[k]) != r["request_sha256"] for k, r in known.items()):
            raise ValueError("Diagnostic archive mismatch")
        pending = {k: w for k, w in wires.items() if k not in known}
        ident = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
        receipts = known | (engine.stage(STAGE, pending, ident, live, ledger) if pending else {})
        scores = {}
        for arm in ("CONTEXT_FIRST", "ACTION_FIRST"):
            raw = {field: r["answer"] for (method, field), r in receipts.items() if method == arm and r["status"] == "OK"}
            attrs, complete = parent["archived_fields"]({"raw_scores": raw, "actor_status": "OK"}, ref)
            scores[arm] = parent["summarize"](attrs, complete)
        output = {"scores": scores, "requests": len(ledger), "stage_status": Counter(r["status"] for r in receipts.values()),
                  "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                  "retries": sum(r["automatic_retries"] for r in ledger), "archived_reused": len(known)}
        location = OUT / "RESULTS.json"
        if live:
            probe.freeze(location, output)
        elif archive.read(location) != output:
            raise ValueError("Diagnostic replay mismatch")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("run", "replay"))
    main(cli.parse_args().action == "run")
