"""Test message-level deletion of optional discourse against a full rewrite."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "bench_expression_realization_v1"))
from expression import ABBREVIATION, AMOUNT, BREAK, CLOSE, HEADER, MARKUP, OPTIONAL, WORD, eligible
from run_expression import panel

sys.path.insert(0, str(BASE / "branch_constraint_repair_v1"))
from trial import body, engine, grading, parse, probe, sha
from summarize_reassembly import measure, paired
from baselines import archive

RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("REWRITE", "DELETE")
STAGE = "DiscourseProposal"
CAP = {STAGE: 8, "BenchAttrs": 96}
PROMPT = """The user prefers short and simple responses, and the current task permits concision.
Deliver the actual message requested. Preserve the original purpose, recipient, transaction status,
dates, figures, names, applicable style requirements, and every detail or condition needed by its recipient.
Do not add facts, claims of acting, or private details. Produce two proposals using the same draft:
1. Rewrite the whole message to be concise and simple. Keep original salutation and signature if present.
2. Pick up to three supplied complete sentence IDs that could be deleted, leaving an independently
sendable draft. Remove only duplicated or purely conversational material. Do not remove a necessary
request, condition, offer, useful relationship cue or the only instance of a fact. Do not remove text
if the resulting pronouns, paragraph or flow become unclear. Empty list is allowed.
Return only JSON {"rewrite":"complete sendable message", "drop":["S1","S2"]}."""


def read(path):
    return json.loads(path.read_text())


def sentences(draft):
    """Localize editable complete prose while retaining original offsets."""
    offset, candidates = 0, {}
    for line in draft.splitlines(keepends=True):
        content = line.rstrip()
        if CLOSE.fullmatch(content.strip()):
            break
        if not re.match(r"^\s*(?:[-•]|\d+[.)])\s+", content) and not HEADER.match(content):
            starts = [0]
            starts.extend(m.end() for m in BREAK.finditer(content)
                          if not ABBREVIATION.search(content[:m.end()]))
            for a, b in zip(starts, starts[1:] + [len(content)], strict=True):
                candidate = content[a:b].strip()
                if (candidate.endswith((".", "!", "?")) and len(WORD.findall(candidate)) >= 5
                        and not any(p.search(candidate) for p in (MARKUP, AMOUNT, OPTIONAL))):
                    start = offset + a + len(content[a:b]) - len(content[a:b].lstrip())
                    candidates[f"S{len(candidates) + 1}"] = (start, start + len(candidate), candidate)
        offset += len(line)
    return candidates


def apply(draft, spans, ids):
    if not isinstance(ids, list) or len(ids) > 3 or not all(isinstance(i, str) and i in spans for i in ids):
        raise ValueError("Invalid deletion proposal")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate deletion")
    if not ids:
        return draft
    dropped = sorted((spans[i] for i in ids), reverse=True)
    if sum(len(WORD.findall(text)) for _, _, text in dropped) > len(WORD.findall(draft)) / 2:
        raise ValueError("Excessive deletion")
    for a, b, text in dropped:
        if draft[a:b] != text:
            raise ValueError("Draft span changed")
        # Remove surrounding surplus spaces only within the edited line.
        while b < len(draft) and draft[b] == " ":
            b += 1
        draft = draft[:a] + draft[b:]
    return re.sub(r"(?m)^ +$", "", draft).strip()


def setup():
    refs = panel()
    cases, _, _ = archive.transfer.context("BenchPreS")
    wanted = {r["uid"] for r in refs}
    gate = {r["uid"]: r for r in archive.transfer.archived_answers(
        "BenchPreS", {u: c for u, c in cases.items() if u in wanted})
            if r["method"] == archive.engine.GATE and r["actor_status"] == "OK" and r.get("actor_request")}
    cards, jobs = {}, {}
    for row in refs:
        uid, draft = row["uid"], row["answer"]
        old = gate[uid]
        if sha(old["actor_request"]) != old["actor_request_sha256"] or old["answer"] != draft:
            raise ValueError("Strong Actor or answer provenance drift")
        packet = json.loads(old["actor_request"]["messages"][1]["content"])
        visible = old["view"]["source_evidence"]
        card = {**row, "sources": visible, "sentences": sentences(draft)}
        cards[uid] = card
        if not eligible(packet["query"], [s["text"] for s in visible]):
            continue
        jobs[uid, "SHARED"] = body(PROMPT, {"task": {k: packet[k] for k in ("query", "current_context", "facts") if k in packet},
                                            "selected_evidence": visible, "draft": draft,
                                            "deletion_candidates": {k: v[2] for k, v in card["sentences"].items()}})
    pin = {"planned": {u: sha(c["answer"]) for u, c in cards.items()},
           "wires": [[u, sha(w)] for (u, _), w in jobs.items()],
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service": probe.read_reference()[1], "caps": CAP}
    return pin, cards, jobs


def run(pin, cards, jobs):
    engine.OUT = probe.OUT = PRIVATE
    probe.RUN = RUN
    engine.CAP = CAP
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        def stage(name, wires, cache=None):
            return engine.stage(name, wires, identity, True, ledger, cache) if wires else {}

        replies = stage(STAGE, jobs)
        rows, decisions = [], {}
        for uid, card in cards.items():
            draft = card["answer"]
            rewritten = shortened = draft
            rec = replies.get((uid, "SHARED"))
            status = "NOT_ELIGIBLE" if rec is None else rec["status"]
            if rec:
                rewritten = shortened = None
                if status == "OK":
                    try:
                        proposal = parse(rec["answer"])
                        if not isinstance(proposal, dict) or set(proposal) != {"rewrite", "drop"}:
                            raise ValueError("Invalid proposal")
                        if isinstance(proposal["rewrite"], str) and proposal["rewrite"].strip():
                            rewritten = proposal["rewrite"].strip()
                        shortened = apply(draft, card["sentences"], proposal["drop"])
                    except (ValueError, KeyError, TypeError):
                        status = "INVALID_PROPOSAL"
            decisions[uid] = status
            for arm, answer in zip(ARMS, (rewritten, shortened), strict=True):
                exact = answer == draft
                rows.append({"uid": uid, "benchmark": "BenchPreS", "group": card["group"], "stratum": "communication",
                             "method": arm, "answer": answer, "actor_status": "OK" if answer else "MISSING",
                             "sources": card["sources"], "score": card["score"] if exact else None,
                             "score_flags": [] if exact else None})
        unique = {}
        for row in rows:
            unique.setdefault((row["uid"], row["answer"]), row)
        grading(list(unique.values()), stage)
        for row in rows:
            row["score"] = unique[row["uid"], row["answer"]]["score"]
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "ledger": ledger, "decisions": decisions})


def report(cards):
    data = read(PRIVATE / "RESULTS.json")
    records = {(r["uid"], r["method"]): r for r in data["rows"]}
    evaluation = []
    length = Counter()
    changes = Counter()
    target = Counter()
    for uid, card in cards.items():
        observed = {a: records[uid, a] for a in ARMS}
        scores = {"BASE": card["score"], **{a: r["score"] for a, r in observed.items()}}
        if card["feature"] is not None:
            attribute = card["feature"]["preference"]
            for a, s in scores.items():
                hits = [d for d in s["decisions"] if d["preference"] == attribute] if s else []
                if len(hits) == 1:
                    target[f"{card['role']}/{a}/valid"] += 1
                    target[f"{card['role']}/{a}/follow"] += int(hits[0]["label"] == "follow")
        for a, r in observed.items():
            if r["answer"]:
                changes[a] += int(r["answer"] != card["answer"])
                length[a] += len(WORD.findall(r["answer"]))
        length["BASE"] += len(WORD.findall(card["answer"]))
        evaluation.append(({"benchmark": "BenchPreS"}, observed,
                           {a: measure("BenchPreS", "communication", s) for a, s in scores.items()}))
    ledger = data["ledger"]
    physical = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def key(r):
        return r["unit"]["stage"], r["request_sha256"], r["status"]
    if Counter(map(key, physical)) != Counter(map(key, ledger)):
        raise ValueError("Physical ledger disagreement")
    print(json.dumps({"common": paired(evaluation, ("BASE", *ARMS)), "words": length, "changed": changes,
                      "target": target, "contracts": Counter(data["decisions"].values()),
                      "stages": Counter(x["unit"]["stage"] for x in ledger),
                      "statuses": Counter(x["status"] for x in ledger),
                      "tokens": sum((x["usage"] or {}).get("total_tokens", 0) for x in ledger),
                      "unknown_usage": sum("total_tokens" not in (x["usage"] or {}) for x in ledger),
                      "retries": sum(x["automatic_retries"] for x in ledger)}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("freeze", "run", "report"))
    action = ap.parse_args().action
    pin, cards, jobs = setup()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(marker, pin)
        print("Cases", len(cards), "shared proposals", len(jobs))
    elif read(marker) != pin:
        raise ValueError("Frozen identity drift")
    elif action == "run":
        run(pin, cards, jobs)
    else:
        report(cards)
