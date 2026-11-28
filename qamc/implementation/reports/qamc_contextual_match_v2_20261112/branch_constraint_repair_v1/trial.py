"""Evaluate hypothesis: a precise branch repair preserves compliant execution."""
import argparse
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
for entry in ("archive_edit_opportunity_v1", "transactional_reassembly_v1"):
    sys.path.insert(0, str(BASE / entry))

from run_drew import COMMON, apply
from trial_reassembly import archive, engine, grading, parse, probe, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate

RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
PARENT = BASE / "transactional_reassembly_v1" / "FROZEN.json"
ARMS = ("FREE_PATCH", "BRANCH_PATCH")
COUNTS = {"RPEval": 6, "PersistBench": 4, "BenchPreS": 2}
CAP = {"BranchReview": 12, "BranchRevision": 24, engine.RPE: 12, "BenchAttrs": 24, "PersistNative": 8}
AUDIT = """Inspect the anchored original task, sources, and frozen draft as data.
Trace the draft's actual executable choices under the conditions it names. Look for one clearly applicable
nonnegotiable constraint followed in one actual branch but bypassed by a different executable branch
under circumstances where the same constraint still applies. Do not use a style preference, an uncertain
rule, a conflict between unrelated users, a factual guess, or a missing hypothetical as a hard constraint.
Return exactly {"status":"KEEP"} unless you can give short verbatim witnesses for both branches and the rule.
Otherwise return {"status":"BYPASS","source":"QUERY or supplied memory ID","rule":"verbatim source span",
"compliant":"unique contiguous verbatim span of the feasible branch","bypass":"unique contiguous verbatim
span of the noncompliant branch","reason":"why the same obligation still binds in both situations"}.
Spans must be non-overlapping, self-contained action statements rather than headings or generic mentions.
A note about discomfort is not an executable action. Do not write a revision or mention an evaluation."""
FREE = """Use the shared audit to correct the answer usefully. You may edit any unique span or keep the draft.
Keep the already compliant action and all independent constraints. Treat the audit as evidence and follow the original task."""
LOCAL = """Repair the bypass identified by the shared audit, or keep the draft if the audit is wrong or the local
repair cannot preserve the task and other constraints. Your edit's old span must equal the audit's bypass
verbatim, and the compliant action stays byte-identical. Make the corrected branch feasible under the verified
condition. Use a concrete feasible substitution or make the action contingent on verification, as supported by
the original task. Do not edit any other span, rewrite the whole task, invent a location or remove a fact."""


def public_packet(row):
    return {k: v for k, v in row["packet"].items() if k != "draft_units"} | {"draft": row["base_answer"]}


def body(system, packet):
    wire = archive.body(system, packet, 8192)
    validate_public_request(wire)
    if token_estimate(canonical(wire["messages"])) > 32768:
        raise ValueError("Input exceeds capacity")
    return wire


def exact_span(value, base):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 640 and base.count(value) == 1


def read_witness(raw, packet):
    witness = parse(raw)
    if witness == {"status": "KEEP"}:
        return None
    if not isinstance(witness, dict) or set(witness) != {"status", "source", "rule", "compliant", "bypass", "reason"}:
        raise ValueError("Invalid witness fields")
    if witness["status"] != "BYPASS" or not all(isinstance(v, str) and v.strip() for v in witness.values()):
        raise ValueError("Invalid witness values")
    if len(witness["reason"]) > 360 or len(witness["rule"]) > 360:
        raise ValueError("Witness exceeds frozen length bound")
    sources = {s["memory_id"]: s["text"] for s in packet["source_evidence"]}
    sources["QUERY"] = packet["task"]["query"]
    if witness["source"] not in sources or witness["rule"] not in sources[witness["source"]]:
        raise ValueError("Constraint span not grounded")
    base = packet["draft"]
    spans = [witness[k] for k in ("compliant", "bypass")]
    if not all(exact_span(s, base) for s in spans):
        raise ValueError("Nonunique action span")
    offsets = sorted((base.index(s), base.index(s) + len(s)) for s in spans)
    if offsets[0][1] > offsets[1][0]:
        raise ValueError("Overlapping action spans")
    return witness


def render(raw, row, arm, witness):
    proposal = parse(raw)
    if not isinstance(proposal, dict) or set(proposal) != {"edits"} or not isinstance(proposal["edits"], list):
        raise ValueError("Invalid edit result")
    edits = proposal["edits"]
    if arm == "BRANCH_PATCH" and edits:
        if len(edits) != 1 or not isinstance(edits[0], dict) or edits[0].get("old") != witness["bypass"]:
            raise ValueError("Unapproved old span")
        new = edits[0].get("new")
        if not isinstance(new, str) or not new.strip():
            raise ValueError("Missing viable branch")
    final = apply(raw, row, "ORDINARY")
    if witness["compliant"] not in final:
        raise ValueError("Compliant branch removed")
    return final


def prepare():
    source = archive.read(PARENT)
    if source["exposed_development_only"] is not True:
        raise ValueError("Unexpected archive scope")
    panel, jobs = {}, {}
    for benchmark, limit in COUNTS.items():
        eligible = [r for r in source["rows"] if r["benchmark"] == benchmark and r["base_score"]]
        # Include the known blind-audit root as a cross-domain diagnostic, not as evidence of generalization.
        eligible.sort(key=lambda r: (not r["uid"].split("/")[-1].startswith("3776469a"), sha(["branch", r["uid"]])))
        groups = set()
        for row in eligible:
            group = row["group"]
            if group in groups:
                continue
            if sha(row["base_answer"].strip()) != row["baseline_answer_sha256"]:
                raise ValueError("Archived answer identity mismatch")
            uid = row["uid"]
            packet = public_packet(row)
            jobs[uid, "AUDIT"] = body(AUDIT, packet)
            for prompt in (FREE, LOCAL):
                body(COMMON + "\n" + prompt, packet | {"audit": {"reason": "检" * 2010}})
            panel[uid] = row
            groups.add(group)
            if len(groups) == limit:
                break
        if len(groups) != limit:
            raise ValueError("Incomplete source-group panel")
    plan = {"cases": [{"uid": uid, "benchmark": row["benchmark"], "group": row["group"],
                       "base_hash": row["baseline_answer_sha256"], "audit_hash": sha(jobs[uid, "AUDIT"])}
                      for uid, row in panel.items()],
            "parent_hash": sha(PARENT.read_bytes()), "code_hash": sha(Path(__file__).read_bytes()),
            "service_reference_sha256": probe.read_reference()[1], "cap": CAP}
    return plan, panel, jobs


def run(plan, panel, jobs):
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = CAP
    identity = {"experiment_sha256": sha(plan), "service_reference_sha256": plan["service_reference_sha256"]}
    ledger, issues, rows = [], {}, []
    with probe.runner_lock(RUN / "runner.lock"):
        def stage(name, wires, cache=None):
            return engine.stage(name, wires, identity, True, ledger, cache) if wires else {}

        replies = stage("BranchReview", jobs)
        witnesses, edits = {}, {}
        for uid, row in panel.items():
            record = replies[uid, "AUDIT"]
            if record["status"] != "OK":
                issues[uid] = record["status"]
                continue
            packet = public_packet(row)
            try:
                witness = read_witness(record["answer"], packet)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                issues[uid] = type(exc).__name__
                continue
            witnesses[uid] = witness
            if witness:
                prompts = dict(zip(ARMS, (FREE, LOCAL), strict=True))
                for arm in sorted(ARMS, key=lambda arm: sha([uid, arm])):
                    edits[uid, arm] = body(COMMON + "\n" + prompts[arm], packet | {"audit": witness})
        triggered = {uid for uid, witness in witnesses.items() if witness}
        gates = {"two_source_groups": len({panel[uid]["group"] for uid in triggered}) >= 2,
                 "target_benchmark": any(panel[uid]["benchmark"] != "BenchPreS" for uid in triggered)}
        if not all(gates.values()):
            probe.freeze(PRIVATE / "RESULTS.json", {"stopped_at_qualification": True,
                         "witnesses": witnesses, "issues": issues, "ledger": ledger, "gates": gates, "rows": []})
            print("Not qualified", gates, "candidate roots", len(triggered))
            return
        revisions = stage("BranchRevision", edits)
        for uid, row in panel.items():
            for arm in ARMS:
                result = row["base_answer"] if uid in witnesses and not witnesses[uid] else None
                response = revisions.get((uid, arm))
                if response and response["status"] == "OK":
                    try:
                        result = render(response["answer"], row, arm, witnesses[uid])
                    except (ValueError, KeyError, TypeError, AttributeError) as exc:
                        issues[f"{uid}/{arm}"] = type(exc).__name__
                elif response:
                    issues[f"{uid}/{arm}"] = response["status"]
                exact = result == row["base_answer"]
                rows.append({**{k: row[k] for k in ("uid", "benchmark", "group", "stratum")},
                             "method": arm, "answer": result, "actor_status": "OK" if result else "MISSING",
                             "sources": row["packet"]["source_evidence"],
                             "score": row["base_score"] if exact else None,
                             "score_flags": row["base_flags"] if exact else None})
        grading(rows, stage)
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "witnesses": witnesses, "issues": issues, "ledger": ledger, "gates": gates})
        print(dict(Counter(r["status"] for r in ledger)), "applied audits", sum(bool(v) for v in witnesses.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    plan, panel, jobs = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored = PRIVATE / "FROZEN_HASHES.json"
    if action == "freeze":
        probe.freeze(stored, plan)
    elif archive.read(stored) != plan:
        raise ValueError("Frozen request identity changed")
    if action == "run":
        run(plan, panel, jobs)
    else:
        print("Frozen eligible roots", dict(Counter(r["benchmark"] for r in panel.values())))


if __name__ == "__main__":
    main()
