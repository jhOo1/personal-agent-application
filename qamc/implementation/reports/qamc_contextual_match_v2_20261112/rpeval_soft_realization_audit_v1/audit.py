"""Distinguish exposure, actual action, and grading for recovered author-B sources."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
trial = run_path(str(BASE / "rpeval_concordant_evidence_v1" / "trial.py"))
archive, engine, probe, sha = (trial[k] for k in ("archive", "engine", "probe", "sha"))
RUN = engine.RUN.with_name(HERE.name)
OUT = RUN / "private"
STAGE = "ConcreteSoftUse"
PROMPT = """Read one current task, one or more focal historical preferences, and the candidate answers independently. For each answer and each focal source record, classify what the answer actually delivers: ABSENT if no relevant action is present; MENTION if it only describes or acknowledges the preference; CONCRETE if it includes a specific compatible action, option, feature, or practice implementing it; OVERREACH if it turns a soft preference into a binding requirement, applies it to someone else without warrant, or compromises a directly stated part of the task; UNCERTAIN if the evidence is ambiguous. Do not infer where a similar suggestion came from or which answer saw history. Judge only the visible answer. For MENTION, CONCRETE and OVERREACH, quote a short exact contiguous substring that supports the observation, with no paraphrase. Otherwise leave quote empty. If the focal source describes many things, assess the actionable user preference that can serve the current task. Return valid JSON only: {"observations":[{"candidate":"V1","source":"existing ID","state":"CONCRETE","quote":"exact answer phrase"}]}. Include every candidate/source pair. Do not give scores, method labels, or overall recommendations."""
STATES = {"ABSENT", "MENTION", "CONCRETE", "OVERREACH", "UNCERTAIN"}
SUPPORTED = {"MENTION", "CONCRETE", "OVERREACH"}
METHODS = ("IPE_C", "RANKED", "CONCORDANT")


def prepare():
    pin, cards, wires = trial["prepare"]()
    source_run = trial["OUT"]
    if archive.read(source_run / "FROZEN.json") != pin:
        raise ValueError("Underlying experiment drifted")
    outcomes = archive.read(source_run / "RESULTS.json")
    new = {(r["uid"], r["method"]): r for r in outcomes["rows"]}
    baseline = {r["uid"]: r for r in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
                if r["method"] == engine.RP and r["actor_status"] == "OK"}
    jobs, targets = {}, {}
    for uid, c in cards.items():
        added = set(c["retained"]["CONCORDANT"]) - set(c["retained"]["RANKED"])
        focal = [s for s in c["records"] if s["memory_id"] in added and c["labels"][s["memory_id"]] == "B"]
        if not focal:
            continue
        original = baseline[uid]
        if sha(original["answer"]) != c["archive"]["answer_sha256"]:
            raise ValueError("Original answer identity changed")
        others = {arm: new[uid, arm]["answer"] for arm in METHODS[1:]}
        answers = {"IPE_C": original["answer"], **others}
        if not all(answers.values()):
            raise ValueError("A prespecified three-answer panel is absent")
        order = sorted(METHODS, key=lambda m: sha(["soft-use-observation-order", uid, m]))
        mapping = {f"V{i}": m for i, m in enumerate(order, 1)}
        wire = wires[uid, "RANKED"]
        current = json.loads(wire["messages"][1]["content"])
        payload = {"task": {key: current[key] for key in ("query", "current_context", "facts")},
                   "focal_sources": focal, "candidates": {k: answers[m] for k, m in mapping.items()}}
        opaque = sha(["soft-realization-v1", uid])
        jobs[opaque, "OBSERVE"] = {**wire, "messages": [
            {"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
        targets[opaque] = {"case": "/".join(uid.split("/")[-2:]), "mapping": mapping,
                           "original_scores": {"IPE_C": c["archive"]["grade"]} | {m: new[uid, m]["score"] for m in METHODS[1:]}}
    if len(jobs) != 6:
        raise ValueError("Original audit must contain all six concrete B-swap roots")
    freeze = {"prior_result_sha": sha((source_run / "RESULTS.json").read_bytes()),
              "wire_hash": sha(list(jobs.values())), "cap": len(jobs),
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
              "reference": probe.read_reference()[1]}
    return freeze, targets, jobs


def observations(answer, packet):
    received = trial["previous"]["support"]["prior"]["parse"](answer)
    rows = received.get("observations") if isinstance(received, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Expected observation records")
    count, usable, seen = Counter(), {}, set()
    candidates = packet["candidates"]
    sources = {s["memory_id"] for s in packet["focal_sources"]}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"candidate", "source", "state", "quote"}
                or any(not isinstance(v, str) for v in row.values())):
            count["bad_schema"] += 1
            continue
        key = (row["candidate"], row["source"])
        if key in seen:
            usable.pop(key, None)
            count["duplicate"] += 1
            continue
        seen.add(key)
        state, quote = row["state"], row["quote"]
        if key[0] not in candidates or key[1] not in sources or state not in STATES:
            count["unknown_cell"] += 1
            continue
        if (state in SUPPORTED and (not quote or len(quote) > 320 or quote not in candidates[key[0]])
                or state not in SUPPORTED and quote):
            count["bad_quote"] += 1
            continue
        usable[key] = row
    count["missing"] = len(candidates) * len(sources) - len(usable)
    return usable, count


def execute(pin, targets, jobs, live):
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {STAGE: pin["cap"]}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        received = engine.stage(STAGE, jobs, identity, live, ledger)
        data, traces, counts, errors = [], [], {m: Counter() for m in METHODS}, Counter()
        for key, receipt in received.items():
            opaque = key[0]
            item = targets[opaque]
            packet = json.loads(jobs[key]["messages"][1]["content"])
            cells, status = {}, receipt["status"]
            if status == "OK":
                try:
                    cells, issues = observations(receipt["answer"], packet)
                    errors.update(issues)
                except (KeyError, TypeError, ValueError, AttributeError):
                    status = "INVALID_REVIEW"
            methods = item["mapping"]
            local = {}
            common_sources = {s["memory_id"] for s in packet["focal_sources"] if all(
                (candidate, s["memory_id"]) in cells and cells[candidate, s["memory_id"]]["state"] != "UNCERTAIN"
                for candidate in methods)}
            for candidate, method in methods.items():
                local[method] = Counter(cells[candidate, s]["state"] for s in common_sources)
                counts[method].update(local[method])
            data.append({"case": item["case"], "status": status, "eligible_B": len(packet["focal_sources"]),
                         "common_determinate_B": len(common_sources), "behavior": local,
                         "original_match": {m: v.get("match") if v else None for m, v in item["original_scores"].items()}})
            traces.append({"case": item["case"], "entries": [dict(v, method=methods[k[0]]) for k, v in cells.items()]})
        aggregate = {"assigned": len(targets), "behavior": counts, "cases": data, "errors": errors,
                     "requests": len(ledger), "statuses": Counter(r["status"] for r in ledger),
                     "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                     "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                     "retries": sum(r["automatic_retries"] for r in ledger)}
        result = {"summary": aggregate, "traces": traces, "ledger": ledger}
        location = OUT / "RESULTS.json"
        if live:
            probe.freeze(location, result)
        elif sha(result) != sha(archive.read(location)):
            raise ValueError("Exact audit replay differs")
    print(json.dumps(aggregate, sort_keys=True, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "run", "replay"))
    action = cli.parse_args().action
    data = prepare()
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    pin_path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(pin_path, data[0])
        seen, _ = trial["previous"]["support"]["prior"]["find_archived"](data[2], BASE.parents[1])
        if seen:
            raise ValueError("Previously seen audit requests must not be reissued")
        print({"roots": len(data[1]), "max_calls": data[0]["cap"]})
    elif archive.read(pin_path) != data[0]:
        raise ValueError("Frozen readout changed")
    else:
        execute(*data, live=action == "run")
