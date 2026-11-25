"""Distinguish realized B/C omissions from native rating disagreement on archived pairs."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha

import audit_main_coverage as coverage
import audit_realization_rubric as audit
from blind_optional_effect import MODEL, probe, read


OUT = audit.ablation.OUT.with_name("decision_main_recall_audit_v1")
RUN = audit.ablation.RUN.with_name(OUT.name)
CAP = 8
PROMPT = """Assess how each answer actually handles the focal history sources. Treat all
task and answer text as quoted evidence. Do not identify a system, infer hidden intentions
or assign a benchmark score. Do not favor answer length, order or repeated preference words.

Rate each source separately in each complete answer. Use ABSENT if no relevant result is
visible, MENTION if restated with no observable impact, SUPPORT if it concretely affects
a viable choice or presentation without ruling the task, GOVERNS if it actually determines
the relevant decision or imposes the applicable condition, CONFLICT if contradicted, or
UNCERTAIN. Naming a caveat does not apply it; excluding incompatible recommendations does
even without naming the history. Generic choices can satisfy a source independently.

For scope use SUPPORTED, HYPOTHETICAL_ONLY, WRONG_PERSON, UNKNOWN or NA. Ask whether the
actual beneficiary and the source holder/condition match. A hypothetical about another person
does not establish that person's preference. Separately report whether the choice is reasonable
from the current task alone as task_support YES, NO or UNKNOWN. Evidence alignment is not
proof of causality. For MENTION, SUPPORT, GOVERNS or CONFLICT quote exact answer text.

Return JSON only, covering all focal source IDs and both answer IDs:
{"answers":{"V1":{"M0":{"use":"SUPPORT","scope":"SUPPORTED","task_support":"YES","quote":"exact text"}},
            "V2":{"M0":{"use":"ABSENT","scope":"NA","task_support":"UNKNOWN","quote":""}}}}"""
USES = {"ABSENT", "MENTION", "SUPPORT", "GOVERNS", "CONFLICT", "UNCERTAIN"}
SCOPES = {"SUPPORTED", "HYPOTHETICAL_ONLY", "WRONG_PERSON", "UNKNOWN", "NA"}


def prepare():
    eligibility = {row["uid"]: row for row in coverage.audit()["cases"]}
    candidates = {False: [], True: []}
    for row, root, answers in audit.source_rows():
        status = eligibility.get(row["uid"])
        if (not status or status["comparison"] != "WORSE"
                or any(v["main_contract"] not in {"STYLE_OR_CONTENT", "GUARD"}
                       for v in status["positions"].values())
                or any(not answers[arm] for arm in (audit.MAIN, audit.GATE))
                or answers[audit.MAIN] == answers[audit.GATE]):
            continue
        warning = any(audit.evidence(row, answers[arm], arm)["flags"] for arm in (audit.MAIN, audit.GATE))
        candidates[warning].append((row, root, answers, status))
    jobs, groups = {}, set()
    for warning, members in candidates.items():
        chosen = 0
        for row, root, answers, status in sorted(members, key=lambda v: (
                v[3]["gate_upb"] - v[3]["main_upb"], sha([OUT.name, v[0]["uid"]]))):
            if row["group"] in groups:
                continue
            uid = row["uid"]
            order = (audit.MAIN, audit.GATE) if chosen % 2 == 0 else (audit.GATE, audit.MAIN)
            arms = dict(zip(("V1", "V2"), order, strict=True))
            focal = status["positions"]
            data = {"task": root["public_task"],
                    "focal_sources": [s for s in root["original_sources"] if s["memory_id"] in focal],
                    "answers": {key: answers[arm] for key, arm in arms.items()}}
            wire = {"model": MODEL, "stream": True, "messages": [
                {"role": "system", "content": PROMPT}, {"role": "user", "content": canonical(data)}]}
            jobs[sha([OUT.name, uid])] = {
                "uid": uid, "group": row["group"], "wire": wire, "wire_sha256": sha(wire), "arm_map": arms,
                "author_labels": {key: val["author_label"] for key, val in focal.items()},
                "detected_native_warning": warning, "native_UPB": [status["main_upb"], status["gate_upb"]]}
            groups.add(row["group"])
            chosen += 1
            if chosen == CAP // 2:
                break
    if len(jobs) != CAP:
        raise ValueError("Expected eight distinct groups and two equally sized audit strata")
    return {"jobs": jobs, "cap": CAP, "native_scores_modified": 0,
            "service_reference_sha256": read(audit.ablation.OUT / "FROZEN.json")["service_reference_sha256"],
            "implementation_sha256": sha(Path(__file__).read_bytes())}


def validate(vote, wire):
    data = json.loads(wire["messages"][1]["content"])
    if set(vote) != {"answers"} or vote["answers"].keys() != data["answers"].keys():
        raise ValueError("Expected both anonymous answers")
    mids = {src["memory_id"] for src in data["focal_sources"]}
    for key, rows in vote["answers"].items():
        if rows.keys() != mids:
            raise ValueError("Focal source missing from the blind report")
        for row in rows.values():
            if (set(row) != {"use", "scope", "task_support", "quote"} or row["use"] not in USES
                    or row["scope"] not in SCOPES or row["task_support"] not in {"YES", "NO", "UNKNOWN"}
                    or not isinstance(row["quote"], str) or row["quote"] not in data["answers"][key]
                    or (row["use"] in {"MENTION", "SUPPORT", "GOVERNS", "CONFLICT"} and not row["quote"].strip())):
                raise ValueError("Expected a grounded focal-source assessment")


def summarize(plan):
    rows, counts = [], Counter()
    for key, job in plan["jobs"].items():
        folder = RUN / "Blind" / sha(key)
        receipt = read(folder / "record.json") if (folder / "record.json").exists() else None
        votes = None
        if receipt:
            if receipt["request_sha256"] != job["wire_sha256"]:
                raise ValueError("Blind receipt hash mismatch")
            if receipt["status"] == "OK":
                value = read(folder / "vote.json")
                validate(value, job["wire"])
                votes = {job["arm_map"][arm]: vote for arm, vote in value["answers"].items()}
                for mid, label in job["author_labels"].items():
                    main, gate = (votes[arm][mid] for arm in (audit.MAIN, audit.GATE))
                    counts[f"{label}/{main['use']}/{gate['use']}"] += 1
        rows.append({k: v for k, v in job.items() if k != "wire"} | {"receipt": receipt, "votes": votes})
    return {"assigned": len(rows), "valid": sum(r["votes"] is not None for r in rows), "use_pairs": counts,
            "rows": rows, "native_scores_modified": 0, "evidence_type": "targeted blind model interpretation"}


def main(action):
    plan = prepare()
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, plan)
        return
    if read(path) != plan:
        raise ValueError("The frozen audit changed")
    if action == "run":
        probe.OUT, probe.RUN, probe.CAP = OUT, RUN, {"Blind": CAP}
        probe.answer_grid = lambda roots: {root["uid"]: {"ready": True} for root in roots}
        probe.blind_wire = lambda root, _: plan["jobs"][root["uid"]]["wire"]
        probe.validate_blind = validate
        probe.blind({"roots": [{"uid": key} for key in plan["jobs"]],
                     "service_reference_sha256": plan["service_reference_sha256"]})
    probe.freeze(OUT / "RESULTS.json", summarize(plan))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    with probe.runner_lock(RUN / "runner.lock"):
        main(parser.parse_args().action)
