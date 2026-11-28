"""Shared-candidate comparison of free and precondition-guarded commitment."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "branch_constraint_repair_v1"))

from trial import PARENT, archive, body, engine, grading, parse, probe, public_packet, sha
from summarize_reassembly import aligned, bounds, measure, paired

RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("FREE", "GUARDED")
SUFFIXES = (
    "implicit/094", "explicit/116", "implicit/148",
    "3776469a39baf2df0418", "dbcf603fc3b52d91814d", "65666d8de543a3151b42",
    "b22cff4ac78cf9a8829d", "43a1728d8ded3220472c",
)
PROMPT = """Answer the original task in its language. The reference answer is a strong draft.
Preserve its correct task facts, deliverable, applicable preferences, and independent decisions.
Find whether its main proposed action depends on a concrete precondition that supplied evidence
contradicts or leaves unverified. Restrict this to actual commitments (an action, venue, factual claim,
eligibility, or excluded item), not generic uncertainty, relevance, desired tone or inferred taste.
A user's constraint can bind even if not restated. Never invent a constraint for another person.
Propose complete answers. 'direct' is your best direct answer. 'conditional' is a complete useful
answer that makes a feasible alternative the primary action when supported, or explicitly makes
that particular commitment conditional on verification with a viable next step. It must preserve
other correct content and cannot merely mention uncertainty while leaving the disputed action as
the unconditional primary recommendation. No meta commentary, citations to internal IDs, or claims
you performed external verification. Use this JSON:
{"preferred":"direct|conditional|draft","direct":"complete answer","conditional":"complete answer or null",
 "gate":null or {"decision":"unique verbatim span of draft naming the commitment",
 "constraint":{"id":"QUERY or supplied memory ID","quote":"verbatim text"},
 "situation":{"id":"QUERY or another supplied memory ID","quote":"verbatim text"},
 "state":"CONTRADICTED|UNVERIFIED"}}
The two independent quotes must jointly apply to the same actual commitment. If not applicable or
already resolved, set gate and conditional to null. Your preferred answer is your free overall choice;
choose it by usefulness and correctness, regardless of whether you return a gate. The conditional
answer must be distinct from the direct answer if a gate is proposed. Return JSON only."""
CAP = {"FeasibilityActor": len(SUFFIXES), engine.RPE: 6, "BenchAttrs": 36, "PersistNative": 6}


def choose(raw, packet):
    result = parse(raw)
    if not isinstance(result, dict) or set(result) != {"preferred", "direct", "conditional", "gate"}:
        raise ValueError("Invalid result fields")
    direct = result["direct"]
    conditional = result["conditional"]
    if not isinstance(direct, str) or not direct.strip() or result["preferred"] not in ("direct", "conditional", "draft"):
        raise ValueError("Invalid base answer choice")
    choices = {"direct": direct.strip(), "draft": packet["draft"]}
    if isinstance(conditional, str) and conditional.strip():
        choices["conditional"] = conditional.strip()
    free = choices.get(result["preferred"])
    if free is None:
        raise ValueError("Missing preferred answer")
    gate = result["gate"]
    if gate is None:
        return free, free, "NO_GATE"
    if not isinstance(gate, dict) or set(gate) != {"decision", "constraint", "situation", "state"}:
        return free, free, "INVALID_GATE"
    decision = gate["decision"]
    if not isinstance(decision, str) or not decision.strip() or packet["draft"].count(decision) != 1:
        return free, free, "INVALID_DRAFT_ANCHOR"
    if gate["state"] not in ("CONTRADICTED", "UNVERIFIED"):
        return free, free, "INVALID_STATE"
    sources = {item["memory_id"]: item["text"] for item in packet["source_evidence"]}
    sources["QUERY"] = packet["task"]["query"]
    ids = []
    for key in ("constraint", "situation"):
        witness = gate[key]
        if not isinstance(witness, dict) or set(witness) != {"id", "quote"}:
            return free, free, "INVALID_SOURCE_ANCHOR"
        sid, quote = witness["id"], witness["quote"]
        if not isinstance(sid, str) or not isinstance(quote, str) or not quote.strip() or quote not in sources.get(sid, ""):
            return free, free, "INVALID_SOURCE_ANCHOR"
        ids.append(sid)
    if len(set(ids)) != 2 or "conditional" not in choices or choices["conditional"] == choices["direct"]:
        return free, free, "MISSING_INDEPENDENT_WITNESS_OR_ALTERNATIVE"
    return free, choices["conditional"], gate["state"]


def prepare():
    parent = archive.read(PARENT)
    assert parent["exposed_development_only"] is True
    rows = {}
    for suffix in SUFFIXES:
        row, = [r for r in parent["rows"] if r["uid"].endswith("/" + suffix)]
        assert row["base_score"] and sha(row["base_answer"].strip()) == row["baseline_answer_sha256"]
        rows[row["uid"]] = row
    assert len({row["group"] for row in rows.values()}) == len(rows)
    wires = {(uid, "SHARED"): body(PROMPT, public_packet(row)) for uid, row in rows.items()}
    frozen = {"parents": sha(PARENT.read_bytes()), "code": sha(Path(__file__).read_bytes()),
              "protocol": sha((HERE / "PROTOCOL.md").read_bytes()), "cap": CAP,
              "wires": {uid: sha(wires[uid, "SHARED"]) for uid in rows}}
    return frozen, rows, wires


def run(frozen, cards, wires):
    engine.OUT = probe.OUT = PRIVATE
    probe.RUN = RUN
    engine.CAP = CAP
    ledger = []
    identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": probe.read_reference()[1]}

    def stage(name, jobs, cache=None):
        return engine.stage(name, jobs, identity, True, ledger, cache) if jobs else {}

    with probe.runner_lock(RUN / "runner.lock"):
        replies = stage("FeasibilityActor", wires)
        rows, dispositions = [], {}
        for uid, card in cards.items():
            receipt = replies[uid, "SHARED"]
            free = guarded = None
            disposition = receipt["status"]
            if disposition == "OK":
                try:
                    free, guarded, disposition = choose(receipt["answer"], public_packet(card))
                except (ValueError, TypeError, KeyError):
                    disposition = "INVALID_REPLY"
            dispositions[uid] = disposition
            for arm, answer in zip(ARMS, (free, guarded), strict=True):
                exact = answer == card["base_answer"]
                rows.append({**{k: card[k] for k in ("uid", "benchmark", "group", "stratum")},
                             "method": arm, "answer": answer, "actor_status": "OK" if answer else "MISSING",
                             "sources": card["packet"]["source_evidence"],
                             "score": card["base_score"] if exact else None,
                             "score_flags": card["base_flags"] if exact else None})
        # Score each distinct answer once for the identical task and grading contract.
        unique = {}
        for row in rows:
            unique.setdefault((row["uid"], row["answer"]), row)
        grading(list(unique.values()), stage)
        for row in rows:
            primary = unique[row["uid"], row["answer"]]
            for key in ("score", "score_flags", "judge"):
                row[key] = primary.get(key)
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "dispositions": dispositions, "ledger": ledger})


def report(cards):
    settled = archive.read(PRIVATE / "RESULTS.json")
    rows = {(row["uid"], row["method"]): row for row in settled["rows"]}
    parts = defaultdict(list)
    differences = Counter()
    for uid, card in cards.items():
        observed = {arm: rows[uid, arm] for arm in ARMS}
        if all(observed[a]["answer"] for a in ARMS) and observed["FREE"]["answer"] != observed["GUARDED"]["answer"]:
            differences[card["benchmark"]] += 1
        b, s = card["benchmark"], card["stratum"]
        metrics = {"BASE": measure(b, s, card["base_score"])}
        metrics.update({arm: measure(b, s, row["score"]) for arm, row in observed.items()})
        parts[b].append((card, observed, metrics))
    reports = {}
    labels = ("BASE", *ARMS)
    for b, entries in parts.items():
        reports[b] = {"common": paired(entries, labels), "assigned": len(entries),
                      "valid_triples": sum(aligned(m, labels) for _, _, m in entries),
                      "guard_minus_free_bounds": bounds(entries, "GUARDED", "FREE"),
                      "changed_between_arms": differences[b]}
    ledger = settled["ledger"]
    records = [archive.read(path) for path in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(key, records)) != Counter(map(key, ledger)):
        raise ValueError("Physical receipt mismatch")
    print(json.dumps({"benchmarks": reports, "dispositions": Counter(settled["dispositions"].values()),
                      "stages": Counter(x["unit"]["stage"] for x in ledger),
                      "statuses": Counter(x["status"] for x in ledger),
                      "retries": sum(x["automatic_retries"] for x in ledger),
                      "tokens": sum((x["usage"] or {}).get("total_tokens", 0) for x in ledger),
                      "unknown_usage": sum("total_tokens" not in (x["usage"] or {}) for x in ledger)},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    frozen, cards, wires = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(marker, frozen)
        print("Frozen", Counter(card["benchmark"] for card in cards.values()))
    elif archive.read(marker) != frozen:
        raise ValueError("Experiment identity drift")
    elif action == "run":
        run(frozen, cards, wires)
    else:
        report(cards)
