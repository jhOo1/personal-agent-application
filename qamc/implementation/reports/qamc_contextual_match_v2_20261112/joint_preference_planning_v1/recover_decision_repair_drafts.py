"""Recover only representation-equivalent drafts, keeping original V2 results immutable."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import sha

import run_decision_repair as parent


OUT = parent.OUT / "draft_schema_recovery"
RUN = parent.RUN / "draft_schema_recovery"


def wrap_and_merge(root, raw):
    """Keep text, order, anchors and recipients intact."""
    try:
        obj = parent.draft.read_object(raw)
        reason = "CONTENT_PARAGRAPH_LIST"
    except ValueError as error:
        plain = raw.strip()
        if not (plain.startswith("[") and plain.endswith("]")):
            raise error
        obj = parent.draft.read_object('{"blocks":' + plain + '}')
        reason = "BARE_BLOCK_ARRAY"

    blocks = obj["blocks"]
    fixed = []
    for block in blocks:
        lines = block["lines"]
        if (block["kind"] == "CONTENT" and isinstance(lines, list) and len(lines) > 1
                and all(isinstance(line, str) and line.strip() for line in lines)):
            block = {**block, "lines": ["\n\n".join(lines)]}
        fixed.append(block)
    normalized = json.dumps({"blocks": fixed}, ensure_ascii=False)
    verified = parent.draft.read_draft(root, normalized)
    before = parent.draft.render(dict(enumerate(blocks)))
    if before != parent.draft.render(verified):
        raise ValueError("Schema recovery changed rendered text")
    return normalized, reason


def prepare():
    spec, rows, roots, archive = parent.prepare()
    if spec != parent.read(parent.OUT / "FROZEN.json"):
        raise ValueError("Parent freeze changed")
    drafts_path = parent.OUT / f"{parent.DRAFT}_EXACT.json"
    exact = parent.read(drafts_path)
    picked, normalized = {}, {}
    for row in rows:
        uid = row["uid"]
        digest = spec["draft_request_sha256"][uid]
        if digest not in exact:
            continue
        rec, raw = exact[digest]
        if rec["status"] != "OK" or rec["request_sha256"] != digest:
            continue
        try:
            parent.draft.read_draft(roots[uid], raw)
        except (ValueError, TypeError):
            try:
                fixed, reason = wrap_and_merge(roots[uid], raw)
            except (KeyError, TypeError, ValueError):
                continue
            picked[uid] = {"request_sha256": digest, "original_response_sha256": sha(raw),
                           "normalized_response_sha256": sha(fixed), "reason": reason}
            normalized[digest] = [rec, fixed]

    n = len(picked)
    if n != 4:
        raise ValueError("The four pre-score schema cases no longer match")
    base = Path(__file__).resolve().parents[3]
    files = (Path(__file__), parent.OUT / "FROZEN.json", drafts_path,
             Path(__file__).with_name("DECISION_REPAIR_SCHEMA_RECOVERY.md"))
    recovery = {
        "cases": picked, "caps": {parent.PROPOSE: n, parent.REVIEW: n, parent.JUDGE: 4 * n},
        "service_reference_sha256": spec["service_reference_sha256"],
        "inputs_sha256": {str(path.resolve().relative_to(base)): sha(path.read_bytes()) for path in files},
        "independent_confirmation": False,
    }
    return spec, recovery, rows, roots, archive, normalized


def settle(action, prepared):
    main_spec, spec, rows, roots, archive, reused = prepared
    if spec != parent.read(OUT / "FROZEN.json"):
        raise ValueError("Schema recovery freeze changed")
    parent_state = parent.read(parent.OUT / "RUN_STATE.json")
    if parent_state["state"] != "COMPLETE":
        raise ValueError("Wait until the original comparison is terminal")
    original = parent.read(parent.OUT / "SETTLED.json")
    parents = {row["uid"]: row for row in original["rows"]}
    candidates = spec["cases"]
    if any(parents[uid]["execution"]["draft"] != "INVALID_DRAFT"
           or parents[uid]["execution"]["answers"] for uid in candidates):
        raise ValueError("Recovery overlaps a usable parent path")

    source = parent.inherited(archive)
    source[parent.DRAFT] = reused
    for stage in spec["caps"]:
        source[stage].update(parent.read(parent.OUT / f"{stage}_EXACT.json"))
        if any(x != y[0]["request_sha256"] for x, y in source[stage].items()):
            raise ValueError("Inherited downstream receipt hash mismatch")
    live = action == "run"
    if live and parent.probe.read_reference()[1] != spec["service_reference_sha256"]:
        raise ValueError("Frozen service fingerprint changed")
    parent.probe.OUT, parent.probe.RUN, parent.replay.OUT = OUT, RUN, OUT
    selected = [row for row in rows if row["uid"] in candidates]

    def stage(name, work):
        if name == parent.DRAFT:
            return {(uid, arm): reused[sha(wire)] for uid, arm, wire in work}
        new = {sha(wire) for _, _, wire in work} - source[name].keys()
        if len(new) > spec["caps"][name]:
            raise ValueError("Schema recovery exceeds its physical cap")
        value = parent.replay.execute_stage(spec, "schema_recovery", name, work, source[name], live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in value.values()):
            raise RuntimeError(f"Unsettled schema recovery stage {name}")
        return value

    state = OUT / "RUN_STATE.json"
    if live:
        parent.probe.atomic_json(state, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        corrected = parent.generate(selected, {x: roots[x] for x in candidates}, stage)
        parent.grade(corrected, stage)
        for row in corrected:
            row["execution"]["schema_recovery"] = candidates[row["uid"]]
            parents[row["uid"]] = row
        incremental = [rec for name in spec["caps"]
                       for rec, _ in parent.probe.stage_receipts(name).values()]
        receipts = original["ledger"] + incremental
        totals = Counter(r["unit"]["stage"] for r in receipts)
        hashes = {(r["unit"]["stage"], r["request_sha256"]) for r in receipts}
        if len(hashes) != len(receipts) or any(n > main_spec["caps"][k] for k, n in totals.items()):
            raise ValueError("Combined receipts fail original freeze budget or deduplication")
        output = list(parents.values())
        parent.probe.freeze(OUT / "SETTLED.json", {"rows": output, "added_ledger": incremental,
                                                "original_ledger_count": len(original["ledger"])})
        parent.probe.freeze(OUT / "RESULTS.json", parent.summarize(main_spec, output, receipts))
    except (ValueError, RuntimeError, OSError) as error:
        if live:
            parent.probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        parent.probe.atomic_json(state, {"state": "COMPLETE", "new_physical_requests": len(incremental)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    prepared = prepare()
    if action == "freeze":
        parent.probe.freeze(OUT / "FROZEN.json", prepared[1])
        print(json.dumps(prepared[1]["cases"], ensure_ascii=False))
    else:
        with parent.probe.runner_lock(RUN / "runner.lock"):
            settle(action, prepared)
