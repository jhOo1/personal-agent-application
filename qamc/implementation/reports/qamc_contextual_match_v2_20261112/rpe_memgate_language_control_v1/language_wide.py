"""Extend the frozen language control to all available exposed contracts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from language_control import (
    FORMAL, HERE, MODEL_FILES, PILOT, REVISION, RUN, freeze, load_gate, read, sha, test_task,
)

WIDE = RUN / "rpe_memgate_language_wide_v1"


def inputs(translator):
    manifest = read(FORMAL / "MANIFEST_300.json")
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    plan = read(RUN / "rpe_memgate_matched_actor_v1/PREFLIGHT_PRIVATE.json")
    selection, missing = plan["selection"], plan["missing"]
    known = read(PILOT / "RESULTS.json")
    pilot = read(PILOT / "FROZEN.json")
    assets = {name: sha((translator / name).read_bytes()) for name in MODEL_FILES}
    allocated = {r["uid"] for r in manifest}
    if (
        len(allocated) != 300 or len(selection) != 295
        or allocated != set(selection) | set(missing) or set(selection) & set(missing)
        or any(c["independent_confirmation"] for c in manifest)
        or set(known) != set(pilot["uids"]) or set(known) - set(selection)
        or pilot["translation_assets"] != assets or pilot["translation_revision"] != REVISION
        or pilot["memgate_plan_sha256"] != sha(selection)
        or pilot["source_inputs_sha256"] != sha({u: tasks[u] for u in known})
        or pilot["code_sha256"] != sha((HERE / "language_control.py").read_bytes())
    ):
        raise ValueError("Wider panel no longer matches the original frozen contract")
    pin = {
        "uids": [row["uid"] for row in manifest if row["uid"] in selection],
        "missing_contract": missing,
        "source_inputs_sha256": sha({u: tasks[u] for u in selection}),
        "memgate_plan_sha256": sha(selection),
        "translation_assets": assets,
        "translation_revision": REVISION,
        "prior_result_sha256": sha(known),
        "pilot_protocol_sha256": pilot["protocol_sha256"],
        "implementation_sha256": sha(Path(__file__).read_bytes()),
        "protocol_sha256": sha((HERE / "WIDE_PROTOCOL.md").read_bytes()),
    }
    return tasks, plan, known, pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("embedding", type=Path)
    parser.add_argument("translator", type=Path)
    args = parser.parse_args()
    WIDE.mkdir(parents=True, exist_ok=True)
    tasks, plan, known, pin = inputs(args.translator)
    freeze(WIDE / "FROZEN.json", pin)
    torch.set_num_threads(2)
    gate, hashes = load_gate(args.assets, args.embedding)
    if hashes != plan["pins"]["released_artifacts"]:
        raise ValueError("Original released assets differ")
    tokenizer = AutoTokenizer.from_pretrained(args.translator, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.translator, local_files_only=True).eval()
    rows, started = {}, time.monotonic()
    for i, uid in enumerate(pin["uids"], 1):
        path = WIDE / f"task_{i:03}.json"
        if uid in known:
            row = known[uid]
        elif path.exists():
            row = read(path)
        else:
            with torch.inference_mode():
                try:
                    row = test_task(gate, tokenizer, model, tasks[uid], plan["selection"][uid]["kept"])
                except (RuntimeError, ValueError) as exc:
                    row = {"status": "INVALID_TRANSLATION_OR_SCORE", "detail": str(exc)}
        freeze(path, row)
        rows[uid] = row
        if i % 10 == 0 or i == len(pin["uids"]):
            print(i, dict(Counter(r["status"] for r in rows.values())), round(time.monotonic() - started, 1), flush=True)
    freeze(WIDE / "RESULTS.json", rows)
    print(json.dumps({"tasks": len(rows), "reused": len(known), "missing_contract": len(pin["missing_contract"]),
                      "new_cloud_requests": 0, "frozen_sha256": sha(pin)}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
