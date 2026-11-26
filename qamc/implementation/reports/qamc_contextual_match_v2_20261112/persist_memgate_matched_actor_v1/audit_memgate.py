"""Build exact released MemGate Actor requests on the settled GEPA panels."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

import torch

from complete import read
from extend import archived
from qamc.common import sha

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
BU = "beneficial_memory_usage"
RISK = {"sycophancy": 11, "cross_domain": 8}


def load_gate(assets, embedding):
    legacy = run_path(str(BASE / "memgate_persistbench_v1/run_memgate.py"))
    source = assets / "memgate/big_module.py"
    checkpoint = assets / "checkpoints/Memgate.pt"
    paths = (source, checkpoint, embedding / "model.safetensors")
    hashes = {p.name: sha(p.read_bytes()) for p in paths}
    if hashes != legacy["PUBLISHED_SHA256"] or embedding.name != legacy["EMBEDDER_REVISION"]:
        raise ValueError("Released MemGate assets differ from the previously verified versions")
    author = run_path(str(source))
    encoder = author["EmbeddingEncoder"](model_name=str(embedding), device="cpu")
    if encoder.embed_dim != 384:
        raise ValueError("Unexpected embedding width")
    gate = author["BIGDefender"](embed_encoder=encoder, device="cpu")
    gate.load(str(checkpoint))
    gate.eval()
    if not gate.use_memgate_single_sided:
        raise ValueError("Unexpected checkpoint architecture")
    gate.threshold = 0.07
    gate.safety_memory = gate.objective_memory = None
    return gate, hashes


def prepare(assets, embedding):
    safety = run_path(str(BASE / "persist_equal_cap_safety_v1/run_safety.py"))
    utility = run_path(str(BASE / "persist_equal_cap_development_v1/run_bu.py"))
    risk = safety["prepare"]()
    bu = utility["prepare"]()
    for config, panel in ((safety, risk), (utility, bu)):
        if read(config["RUN"] / "FROZEN.json") != panel[0]:
            raise ValueError("Settled comparator protocol changed")
    _, risk_api, risk_cases, data, risk_wires, risk_factorial, risk_judge, risk_bounds = risk
    _, bu_api, bu_cases, bu_tasks, _, bu_factorial, bu_judge, bu_bounds = bu
    cases = {**risk_cases, **bu_cases}
    tasks = {**{u: data[u][0] for u in risk_cases}, **bu_tasks}
    if Counter(x["category"] for x in cases.values()) != {**RISK, BU: 12}:
        raise ValueError("Expected the exact 19 risk and 12 utility tasks")
    if len({c["group_id"] for c in cases.values()}) != len(cases):
        raise ValueError("Source overlap across comparator panels")
    if risk_judge != bu_judge:
        raise ValueError("Grader differs across the two archived panels")
    torch.set_num_threads(2)
    gate, assets_hash = load_gate(assets, embedding)
    actors, selection = {}, {}
    with torch.no_grad():
        for uid, case in sorted(cases.items()):
            task = tasks[uid]
            query, memories = task["query"], task["memories"]
            scores = gate.score_candidates(query, memories)
            kept = [i for i, score in enumerate(scores) if score > gate.threshold]
            selected = [memories[i] for i in kept]
            author_selection, _, _ = gate(query, memories, preserve_order=True)
            if selected != author_selection:
                raise ValueError("Fixed candidate adaptation differs from the author selection")
            api, cfg = (risk_api, risk_factorial) if uid in risk_cases else (bu_api, bu_factorial)
            built = api["actor_request"](case, query, selected, cfg, cfg["prompts"]["gepa"])
            full = api["actor_request"](case, query, memories, cfg, cfg["prompts"]["gepa"])
            if built["max_tokens"] != 8192 or {k: v for k, v in built.items() if k != "messages"} != {
                    k: v for k, v in full.items() if k != "messages"}:
                raise ValueError("Final Actor settings changed")
            if uid in risk_cases and risk_wires[uid]["FULL"] != full:
                raise ValueError("Full history reference request changed")
            actors[uid] = built
            selection[uid] = {"category": case["category"], "kept": kept, "available": len(memories)}
    previous = {
        wave: [row for row in read(safety["RUN"] / f"WAVE{wave}.json")["rows"]]
        for wave in safety["WAVES"]
    }
    previous[0] = [row for row in read(utility["RUN"] / "RESULTS.json")["rows"]
                   if row["arm"] in ("ROUTED", "EMPTY", "FULL")]
    local_cache_matches = {
        wave: len({r["uid"] for r in rows if r["status"] == "OK"
                   and r["actor_sha256"] == sha(actors[r["uid"]])})
        for wave, rows in previous.items()
    }
    matches, ledgers = archived(actors, ROOT)
    pin = {"actors_sha256": sha(actors), "released_artifacts": assets_hash, "threshold": gate.threshold,
           "selection_sha256": sha(selection), "preflight_sha256": sha(Path(__file__).read_bytes()),
           "source_panels_sha256": sha([risk[0], bu[0]]),
           "scoring_sha256": sha([risk_judge, risk_bounds, bu_bounds]),
           "comparison_answers_sha256": sha(previous),
           "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes())}
    report = {
        "protocol_sha256": sha(pin), "tasks": len(actors), "logical_slots": 50, "new_cloud_calls": 0,
        "source_trials": dict(Counter(r["category"] for r in selection.values())),
        "same_wave_successful_actor_matches": local_cache_matches,
        "any_development_exact_actor_positions": len(matches), "development_journals": ledgers,
        "selection": {
            category: {"empty": sum(not r["kept"] for r in selection.values() if r["category"] == category),
                       "selected": sum(len(r["kept"]) for r in selection.values() if r["category"] == category),
                       "available": sum(r["available"] for r in selection.values() if r["category"] == category)}
            for category in (*RISK, BU)
        },
    }
    return pin, report, actors, selection, cases, tasks, previous


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("assets", type=Path)
    cli.add_argument("embedding", type=Path)
    args = cli.parse_args()
    _, summary, *_ = prepare(args.assets, args.embedding)
    print(json.dumps(summary, indent=2, sort_keys=True))
