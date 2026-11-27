"""Freeze, dispatch and replay a paired BenchPreS local simplification study."""
import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import file_digest
import importlib.metadata
import json
from pathlib import Path
import time

import baselines
from census import normalized
from expression import apply, eligible, locate, plain_text, restore_format, valid_replacement
from local_models import CONTROL, ENTAILMENT, SIMPLIFIER, THRESHOLD, FrozenModels, snapshot
from qamc.common import sha
from run_car import engine, grading, probe, wire

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
BENCH = "BenchPreS"
METHODS = ("GENERIC", "SPECIALIST")
CAPS = {"GenericEdit": 8, "BenchAttrs": 96}
PROMPT = """Simplify each supplied English sentence if it can be made genuinely shorter and easier to read while saying the same thing. Keep names, numbers, facts, conditions, negation, intended recipient, and strength of any request or commitment. Keep the original terminal punctuation. Use null for a sentence with no safe simplification. Return only JSON {"replacements":[...]} with one string or null per sentence in sentence order."""


def panel():
    ref = baselines.transfer(BENCH)
    archive = baselines.archive
    cases, _, _ = archive.transfer.context(BENCH)
    gate = {r["uid"]: r for r in archive.transfer.archived_answers(BENCH, cases)
            if r["uid"] in ref and r["method"] == archive.engine.GATE and r["actor_status"] == "OK"}
    attr = probe.read(HERE.parent / "strong_actor_boundary_audit_v1/CENSUS.json")["BenchPreS"]["attributes"]
    brevity = [r for r in attr if r["uid"] in ref
               and eligible("", [r["preference"]]) and r["expression"] == "SELECTED_EXACT"]
    misses = [r for r in brevity if r["base_follow"] != "follow"]
    controls = {}
    for record in sorted(brevity, key=lambda r: sha(["brevity-protection-v1", r["uid"]])):
        if record["base_follow"] == "follow":
            controls.setdefault(record["profile_group"], record)
    if len(misses) != 4 or len(controls) != 2:
        raise ValueError("Frozen brevity source coverage changed")
    chosen = {r["uid"]: ("miss", r) for r in misses}
    chosen.update({r["uid"]: ("fulfilled", r) for r in controls.values()})
    used = {r["profile_group"] for r in brevity}
    for uid in sorted(ref, key=lambda u: sha(["other-expression-protection-v1", u])):
        g = ref[uid]["group"]
        if g in used:
            continue
        r = gate[uid]
        task = json.loads(r["actor_request"]["messages"][1]["content"])
        if eligible(task["query"], [x["text"] for x in r["view"]["source_evidence"]]):
            continue
        used.add(g)
        chosen[uid] = ("abstention_control", None)
        if len(chosen) == 8:
            break
    if len(chosen) != 8:
        raise ValueError("Expected eight development tasks")

    result = []
    for uid, (role, feature) in chosen.items():
        card, archived = ref[uid], gate[uid]
        if cases[uid].get("independent_confirmation") or cases[uid].get("role", "DEV") != "DEV":
            raise ValueError("Expected exposed cases")
        request = archived["actor_request"]
        if sha(request) != archived["actor_request_sha256"] or archived["answer"] != card["base_answer"]:
            raise ValueError("Archived gate input or answer changed")
        task = json.loads(request["messages"][1]["content"])
        original = {r["memory_id"]: r for r in card["root"]["original_sources"]}
        selected = archived["view"]["source_evidence"]
        if any(r != original[r["memory_id"]] for r in selected):
            raise ValueError("Unknown original Gate source")
        texts = [r["text"] for r in selected]
        if feature is not None and not any(normalized(feature["preference"]) in normalized(t) for t in texts):
            raise ValueError("Brevity preference not visible in the archived Gate evidence")
        spans = locate(card["base_answer"]) if eligible(task["query"], texts) else ()
        result.append({"uid": uid, "group": card["group"], "role": role, "feature": feature,
                       "answer": card["base_answer"], "score": card["base_score"], "spans": spans})
    return result


def prepare():
    cards = panel()
    assets = {}
    for spec in (SIMPLIFIER, ENTAILMENT):
        checksums = {}
        for path in sorted(snapshot(spec).iterdir()):
            if path.is_file():
                with path.open("rb") as source:
                    checksums[path.name] = file_digest(source, "sha256").hexdigest()
        if not {"model.safetensors", "config.json", "tokenizer.json"} <= checksums.keys():
            raise ValueError("Incomplete frozen model weights or tokenizer")
        assets[spec[0]] = checksums
    pins = {"panel_sha256": sha([{**card, "spans": [asdict(s) for s in card["spans"]]} for card in cards]),
            "counts": dict(Counter(r["role"] for r in cards)),
            "eligible_spans": dict(Counter({role: sum(len(c["spans"]) for c in cards if c["role"] == role)
                                           for role in {c["role"] for c in cards}})),
            "models": [list(SIMPLIFIER), list(ENTAILMENT)], "threshold": THRESHOLD, "control_tokens": CONTROL,
            "model_assets": assets,
            "packages": {p: importlib.metadata.version(p) for p in ("torch", "transformers")},
            "caps": CAPS, "hashes": {p: sha((HERE / p).read_bytes())
                                    for p in ("PROTOCOL.md", "expression.py", "local_models.py", "run_expression.py")}}
    return cards, pins


def decode(text, length):
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != {"replacements"}:
        raise ValueError("Unexpected replacement fields")
    rows = value["replacements"]
    if not isinstance(rows, list) or len(rows) != length or any(x is not None and not isinstance(x, str) for x in rows):
        raise ValueError("Incorrect replacement inventory")
    return rows


def local_simplify(cards, models):
    return {c["uid"]: models.simplify([plain_text(s.text) for s in c["spans"]]) for c in cards}


def compile_draft(card, proposals, models):
    accepted = [None] * len(proposals)
    candidates = []
    for i, (span, candidate) in enumerate(zip(card["spans"], proposals, strict=True)):
        new = restore_format(span.text, candidate)
        if new is not None and valid_replacement(span.text, new):
            candidates.append((i, span.text, new))
    judgements = models.mutual([(plain_text(a), plain_text(b)) for _, a, b in candidates])
    for (index, _, text), confidence in zip(candidates, judgements, strict=True):
        if confidence >= THRESHOLD:
            accepted[index] = text
    checks = {"literal_pass": len(candidates), "accepted_count": sum(a is not None for a in accepted)}
    return apply(card["answer"], card["spans"], accepted), checks


def execute(cards, frozen, live):
    engine.OUT = probe.RUN = probe.OUT = RUN
    engine.CAP = CAPS
    identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(RUN / "EXECUTION.json", identity)
        elif probe.read(RUN / "EXECUTION.json") != identity:
            raise ValueError("Frozen evaluation identity changed")

        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, identity, live, ledger, cache) if jobs else {}

        start = time.monotonic()
        models = FrozenModels()
        specialist = local_simplify(cards, models)
        local_file = RUN / "LOCAL_PROPOSALS.json"
        if live:
            probe.freeze(local_file, specialist)
        elif probe.read(local_file) != specialist:
            raise ValueError("The local simplifier did not reproduce its proposals")
        qwen = stage("GenericEdit", {(c["uid"], "GENERIC"): wire(PROMPT, {"sentences": [
            plain_text(s.text) for s in c["spans"]]})
                                     for c in cards if c["spans"]})
        outputs = []
        local_elapsed = time.monotonic() - start
        for card in cards:
            uid, length = card["uid"], len(card["spans"])
            for method in METHODS:
                output = {"uid": uid, "method": method, "benchmark": BENCH, "stratum": card["role"],
                          "group": card["group"], "score": None, "answer": None}
                try:
                    if method == "GENERIC" and length:
                        receipt = qwen[uid, method]
                        if receipt["status"] != "OK":
                            outputs.append({**output, "actor_status": receipt["status"]})
                            continue
                        proposals = decode(receipt["answer"], length)
                    else:
                        proposals = specialist[uid]
                    answer, checks = compile_draft(card, proposals, models)
                except (ValueError, AttributeError, KeyError, TypeError):
                    outputs.append({**output, "actor_status": "INVALID_EDIT_CONTRACT"})
                    continue
                output.update(actor_status="OK", answer=answer, **checks)
                if answer == card["answer"]:
                    output["score"] = card["score"]
                    output["score_origin"] = "EXACT_STRONG_GATE"
                outputs.append(output)
        grading(outputs, stage)
        result = {"outputs": outputs, "ledger": ledger, "local_counts": {"simplified": models.simplified,
                  "entailment_directions": models.entailment_pairs},
                  "statuses": dict(Counter(r["status"] for r in ledger)),
                  "usage": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger)}
        if live:
            probe.freeze(RUN / "RESULTS.json", result)
        elif probe.read(RUN / "RESULTS.json") != result:
            raise ValueError("Saved result does not replay")
        print({k: result[k] for k in ("statuses", "local_counts", "usage", "unknown_usage")})
        print("Seconds until local proposals and generic edits were collected:", round(local_elapsed, 2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run", "replay"))
    args = parser.parse_args()
    tasks, pins = prepare()
    if args.action == "freeze":
        RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
        probe.freeze(RUN / "FROZEN.json", pins)
    elif probe.read(RUN / "FROZEN.json") != pins:
        raise ValueError("Frozen source and method changed")
    if args.action in ("run", "replay"):
        execute(tasks, pins, args.action == "run")
    else:
        print(json.dumps(pins, indent=2, sort_keys=True))
