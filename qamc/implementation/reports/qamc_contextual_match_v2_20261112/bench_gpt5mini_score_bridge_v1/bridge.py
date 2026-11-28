"""Check the paper-validated GPT-5-mini alias on the existing fixed-answer audit."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
old = run_path(str(BASE / "bench_reflection_prompt_bridge_v1" / "bridge.py"))
engine, probe, sha, parent = (old[k] for k in ("engine", "probe", "sha", "parent"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
MODEL = "gpt-5-mini"
CANARY, SCORE = "GPT5MiniCanary", "GPT5MiniPaired"


def prepare():
    old_jobs, history, baseline = old["locked_work"]()
    cases = defaultdict(list)
    for key, h in history.items():
        cases[h["pair"]].append(key)
    if len(cases) != 14 or any(len(keys) != 2 for keys in cases.values()):
        raise ValueError("Expected exact original paired assignment")
    canary = min(cases, key=lambda pair: sha(["gpt5mini-fixed-canary", pair]))
    previous = run_path(str(BASE / "strong_wire_pruning_replay_v1" / "run.py"))
    archive = previous["archive"]
    old_run = old["RUN"]
    if not (old_run / "SUMMARY.json").is_file():
        raise ValueError("Qwen companion comparison must be settled")
    masks = {}
    for path in old_run.glob("*/visible/*/record.json"):
        item = archive.read(path)
        unit = item["unit"]["root_id"], "BLIND"
        if unit not in old_jobs:
            continue
        if item["request_sha256"] != sha(old_jobs[unit]) or archive.read(path.with_name("request.json")) != old_jobs[unit]:
            raise ValueError("Qwen companion request drift")
        if unit in masks:
            raise ValueError("Companion grade not unique")
        parsed = archive.read(path.with_name("response.json")) if path.with_name("response.json").is_file() else {}
        masks[unit] = old["verdict"]({"status": item["status"], "answer": parsed.get("answer")}, old_jobs[unit])[1]
    if set(masks) != set(old_jobs):
        raise ValueError("Missing fixed-answer masked Qwen receipt")
    jobs = {key: dict(wire, model=MODEL) for key, wire in old_jobs.items()}
    pin = {"source_pin_sha256": sha(baseline), "wire_manifest_sha256": sha(list(jobs.values())),
           "canary_pair_sha256": sha(canary), "code_sha256": sha(Path(__file__).read_bytes()),
           "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service_reference_sha256": probe.read_reference()[1], "caps": {CANARY: 2, SCORE: 26}}
    selected = {(key, "BLIND") for key in cases[canary]}
    return pin, archive, history, masks, jobs, selected


def execute(pin, archive, history, masks, jobs, selected, live):
    engine.OUT = probe.OUT = PRIVATE
    probe.RUN = RUN
    engine.CAP = pin["caps"]
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    ledger, retained = [], {}

    def stage(name, wires):
        location = PRIVATE / f"{name}_archive.json"
        if live and not location.is_file():
            found, _ = old["archived"](wires, BASE.parents[1])
            rows = []
            for (label, arm), item in found.items():
                info = (BASE.parents[1] / item["archive"]).parent / "visible" / item["archive_unit"] / "record.json"
                profile = archive.read(info).get("reference_config_sha256") if info.is_file() else None
                if item["status"] == "OK" and profile != pin["service_reference_sha256"]:
                    item = dict(item, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                rows.append([label, arm, item])
            probe.freeze(location, rows)
        known = {(label, arm): r for label, arm, r in archive.read(location)}
        if any(sha(wires[key]) != r["request_sha256"] for key, r in known.items()):
            raise ValueError("Saved model request drift")
        retained[name] = dict(Counter(r["status"] for r in known.values()))
        pending = {k: w for k, w in wires.items() if k not in known}
        return known | (engine.stage(name, pending, identity, live, ledger) if pending else {})

    with probe.runner_lock(RUN / "runner.lock"):
        canary = stage(CANARY, {k: v for k, v in jobs.items() if k in selected})
        qualifies = all(old["verdict"](answer, jobs[key])[0] == "OK" for key, answer in canary.items())
        scores = canary | (stage(SCORE, {k: v for k, v in jobs.items() if k not in selected}) if qualifies else {})
        result, counts = defaultdict(dict), Counter()
        for (key, _), wire in jobs.items():
            receipt = scores.get((key, "BLIND"))
            status, vote = old["verdict"](receipt, wire) if receipt else ("NOT_DISPATCHED", None)
            counts[status] += 1
            row = history[key]
            result[row["pair"]][row["arm"]] = {"stratum": row["stratum"], "masked_qwen": masks[key, "BLIND"],
                "old_qwen": int(row["old_follow"]), "gpt41": row["masked_gpt41"], "gpt5mini": vote, "status": status}
        aggregated = {}
        for record in result.values():
            if any(r["gpt5mini"] is None or r["masked_qwen"] is None for r in record.values()):
                continue
            for arm, row in record.items():
                cells = aggregated.setdefault(row["stratum"], {}).setdefault(arm, Counter())
                cells.update(complete=1, **{k: row[k] for k in ("old_qwen", "masked_qwen", "gpt41", "gpt5mini")})
                cells.update(same_gpt41=int(row["gpt41"] == row["gpt5mini"]),
                             same_masked_qwen=int(row["masked_qwen"] == row["gpt5mini"]))
        rep = {"canary_pass": qualifies, "logical_outcomes": counts, "totals": aggregated,
               "physical": len(ledger), "transport_statuses": Counter(r["status"] for r in ledger),
               "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
               "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
               "retries": sum(r["automatic_retries"] for r in ledger), "exact_reuse": retained}
        result_path = PRIVATE / "RESULTS.json"
        raw = {"results": result, "ledger": ledger, "aggregate": rep}
        if live:
            probe.freeze(result_path, raw)
        elif archive.read(result_path) != raw:
            raise ValueError("Exact comparison replay changed")
        print(json.dumps(rep, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if action == "freeze":
        probe.freeze(PRIVATE / "FROZEN.json", data[0])
        print(data[0]["caps"])
    elif data[1].read(PRIVATE / "FROZEN.json") != data[0]:
        raise ValueError("Frozen scope changed")
    else:
        execute(*data, live=action == "run")
