"""Check frozen current-choice protection on source-disjoint development rows."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PARENT = BASE / "transactional_reassembly_v1/FROZEN.json"
implementation = run_path(str(BASE / "persist_task_commitment_v1/trial.py"))
PROMPT, compile_decisions, body = (implementation[name] for name in ("PROMPT", "compile_decisions", "body"))
engine, probe, sha = (implementation[name] for name in ("engine", "probe", "sha"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
STAGE = "CommitmentTransfer"
LIMIT = 24
QUOTAS = {"RPEval": {"all_A": 3, "B_only": 2, "contains_C": 3},
          "BenchPreS": {None: 8}, "PersistBench": {None: 8}}


def read(path):
    return json.loads(path.read_text())


def prepare():
    old = read(implementation["RUN"] / "private/FREEZE.json")
    exposed = read(PARENT)
    if not exposed["exposed_development_only"]:
        raise ValueError("Archive eligibility drift")
    prior_groups = {r["group"] for r in exposed["rows"] if r["uid"] in old["cases"]}
    private, requests = {}, {}
    for benchmark, strata in QUOTAS.items():
        used = set(prior_groups)
        for stratum, n in strata.items():
            pool = [r for r in exposed["rows"] if r["benchmark"] == benchmark
                    and (stratum is None or r["stratum"] == stratum)
                    and r["packet"]["source_evidence"]]
            pool.sort(key=lambda r: sha(["commitment-transfer-v1", r["group"], r["uid"]]))
            selected = 0
            for row in pool:
                if row["uid"] in old["cases"] or row["group"] in used:
                    continue
                uid = row["uid"]
                if sha(row["base_answer"].strip()) != row["baseline_answer_sha256"]:
                    raise ValueError("Archived strong answer drift")
                packet = row["packet"]
                memories = [m["text"] for m in packet["source_evidence"]]
                query = packet["task"]["query"]
                requests[uid, "SHARED"] = body(PROMPT, {"query": query, "selected": [
                    {"id": i, "text": text} for i, text in enumerate(memories, 1)]})
                private[uid] = {"query": query, "memories": memories, "benchmark": benchmark,
                                "stratum": row["stratum"], "group": row["group"],
                                "prior_answer_sha256": row["baseline_answer_sha256"]}
                used.add(row["group"])
                selected += 1
                if selected == n:
                    break
            if selected != n:
                raise ValueError(f"Cannot fill {benchmark}/{stratum} with nonempty distinct history")
    assert len(private) == LIMIT
    marker = {"requests": [[u, sha(w)] for (u, _), w in requests.items()],
              "prompts": sha(PROMPT), "archive": sha(PARENT.read_bytes()),
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
              "service": probe.read_reference()[1], "cap": LIMIT}
    return marker, private, requests


def run(pin, cards, requests):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {STAGE: LIMIT}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, rows = [], []
    with probe.runner_lock(RUN / "runner.lock"):
        replies = engine.stage(STAGE, requests, identity, True, ledger)
        for (uid, _), reply in replies.items():
            card = cards[uid]
            direct = conflict = None
            status = reply["status"]
            if status == "OK":
                try:
                    direct, conflict, status = compile_decisions(reply["answer"], card["query"], card["memories"])
                except (ValueError, KeyError, TypeError):
                    status = "INVALID_REPLY"
            rows.append({"uid": uid, "benchmark": card["benchmark"], "stratum": card["stratum"],
                         "group": card["group"], "status": status, "direct": direct, "conflict": conflict})
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "ledger": ledger})


def report():
    data = read(PRIVATE / "RESULTS.json")
    counts = defaultdict(Counter)
    for row in data["rows"]:
        c = counts[row["benchmark"]]
        c["assigned"] += 1
        c[row["status"]] += 1
        c["direct_removes"] += int(row["direct"] is not None)
        c["anchors_different_from_direct"] += int(row["conflict"] is not None and row["direct"] != row["conflict"])
        c["same_removal"] += int(row["conflict"] is not None and row["direct"] == row["conflict"])
    ledger = data["ledger"]
    physical = [read(f) for f in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(key, ledger)) != Counter(map(key, physical)):
        raise ValueError("Physical receipts drift")
    print(json.dumps({"counts": counts, "physical": Counter(r["status"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, cards, jobs = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(lock, pin)
        print("Exposed sources", Counter(x["benchmark"] for x in cards.values()))
    elif read(lock) != pin:
        raise ValueError("Frozen scope drift")
    elif action == "run":
        run(pin, cards, jobs)
    else:
        report()
