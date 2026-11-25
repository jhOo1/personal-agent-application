"""Use the frozen edit contract and original benchmark-specific grading adapters."""
import json
from collections import Counter, defaultdict

from qamc.common import sha

import decision_edit as edit
from preflight_decision_edit import prior
from run_decision_edit import EDIT, parse_edit
from transfer_execution import (
    bench, bench_context, bench_pair, checked_dispatch, development, development_roots,
    grade, grading_jobs, persist, persist_context, persist_pair,
)
from transfer_grading import PERSIST_RP

TASK_ONLY, DRAFT = "TASK_ONLY", "TaskDraft"
RP = "RPR_PAPER_FULL"
PANELS = ("BenchPreS", "PersistBench")


def read(path):
    return json.loads(path.read_text())


def draft_wires(panel):
    jobs = {}
    for root in panel:
        uid = root["uid"]
        wire = prior.task_only_request(root)
        frozen = root["archived_actor_request"]
        if wire["messages"][0] != frozen["messages"][0]:
            raise ValueError("Task-only draft changed the archived Actor instructions")
        fields = json.loads(wire["messages"][1]["content"])
        if fields != {**root["public_task"], "source_evidence": [], "preference_use_policy": []}:
            raise ValueError("Task-only draft diverged from the public baseline")
        jobs[uid, TASK_ONLY, DRAFT] = wire
    return jobs


def generate(panel, dispatch):
    draft_jobs = draft_wires(panel)
    drafts = checked_dispatch(dispatch, draft_jobs)
    payloads, edit_jobs = {}, {}
    for root in panel:
        uid = root["uid"]
        draft = drafts[uid, TASK_ONLY, DRAFT]
        if draft["status"] == "OK":
            payloads[uid] = edit.packet(root, draft["answer"])
            for method in edit.METHODS:
                edit_jobs[uid, method, EDIT] = edit.request(payloads[uid], method)
    replies = checked_dispatch(dispatch, edit_jobs)
    rows = []
    for root in panel:
        uid = root["uid"]
        draft = drafts[uid, TASK_ONLY, DRAFT]
        rows.append({"uid": uid, "method": TASK_ONLY, "actor_status": draft["status"],
                     "answer": draft.get("answer"), "draft_request_sha256": draft["request_sha256"], "score": None})
        for method in edit.METHODS:
            key = uid, method, EDIT
            if key in replies:
                response = replies[key]
                compiled = parse_edit(response, response.get("answer"), payloads[uid], sha(edit_jobs[key]))
            else:
                compiled = {"status": "NO_USABLE_DRAFT"}
            rows.append({"uid": uid, "method": method, "actor_status": compiled["status"],
                         "draft_request_sha256": draft["request_sha256"], "score": None,
                         "answer": compiled.get("answer"), "edit": compiled})
    return rows


def context(benchmark):
    if benchmark == "BenchPreS":
        return bench_context()
    if benchmark == "PersistBench":
        return persist_context()
    raise ValueError("Unknown transfer benchmark")


def summarize(benchmark, rows, cases, controls):
    cells = {(r["uid"], r["method"]): r["score"] for r in (*rows, *controls) if r["score"] is not None}
    paired = bench_pair if benchmark == "BenchPreS" else persist_pair
    methods = [m for m in (*edit.METHODS, TASK_ONLY) if m != "DECISION_EDIT"]
    methods.extend(sorted({r["method"] for r in controls}))
    return {
        "valid_new_native_rows": dict(Counter(r["method"] for r in rows if r["score"] is not None)),
        "actor_status": dict(Counter(r["method"] + "/" + r["actor_status"] for r in rows)),
        "pairwise": {method: paired(method, "DECISION_EDIT", cases, cells) for method in methods},
    }


def archived_answers(benchmark, allowed):
    sources = [read(development.OUT / "RESULT_ROWS.json")]
    if benchmark == "BenchPreS":
        sources.append(read(bench.OUT / "RESULT_ROWS.json"))
    else:
        sources.extend(read(path)["rows"] for path in sorted((persist.AUTHOR_OUT / "waves").glob("*.json")))
    return [r for rows in sources for r in rows if r["uid"] in allowed and r.get("answer")]


def matching_grading_receipts(benchmark, cases, protocol, archive):
    """Use only previously returned scores for reconstructable, exact public wire hashes."""
    candidates = defaultdict(set)
    if benchmark == "BenchPreS":
        for row in archive:
            if not row.get("raw_scores") or row["actor_status"] != "OK":
                continue
            wires, _ = grading_jobs(benchmark, [row], cases, protocol)
            for stage, raw in row["raw_scores"].items():
                candidates[sha(wires[row["uid"], row["method"], stage])].add(raw)
    else:
        authors = [r for r in archive if r["method"] in ("PB_RUBRIC", "PB_GEPA", "PB_NO_MEMORY")
                   and r.get("raw_scores") and r["actor_status"] == "OK"]
        for row in authors:
            wires, _ = grading_jobs(benchmark, [row], cases, protocol)
            wire, = wires.values()
            candidates[sha(wire)].add(row["raw_scores"][persist.STAGE])
        verified = {(r["uid"], r["method"]): r for r in archive}
        paired = read(PERSIST_RP / "RESULTS.json")["rows"]
        adapted = read(persist.OUT / "RESULTS.json")["rows"]
        for row in (*paired, *adapted):
            uid, method = row["uid"], row.get("method", RP)
            if uid not in cases or (uid, method) not in verified:
                continue
            answer = verified[uid, method]
            if sha(answer["answer"]) != row["answer_sha256"]:
                raise ValueError("PersistBench score is for a different answer")
            wires, _ = grading_jobs(benchmark, [answer], cases, protocol)
            wire, = wires.values()
            digest, raw = ((row["RP_gpt41_request_sha256"], row["raw_score"]) if method == RP
                           else (row["judge_request_sha256"], row.get("raw_judge")))
            if sha(wire) != digest:
                raise ValueError("PersistBench grading wire does not match the aligned archive")
            if raw is not None:
                candidates[digest].add(raw)
    unambiguous = {digest: next(iter(raws)) for digest, raws in candidates.items() if len(raws) == 1}
    ambiguous = sorted(digest for digest, raws in candidates.items() if len(raws) > 1)
    return unambiguous, ambiguous


def cached_dispatch(dispatch, jobs, raw_cache, conflicts, counts):
    index, by_wire, outgoing = {}, {}, {}
    for key, wire in jobs.items():
        digest = sha(wire)
        index[key] = digest
        if digest in raw_cache:
            by_wire[digest] = {"status": "OK", "request_sha256": digest, "answer": raw_cache[digest]}
            counts["archived_grade_reuse"] += 1
        elif digest in conflicts:
            by_wire[digest] = {"status": "AMBIGUOUS_ARCHIVED_SCORE", "request_sha256": digest, "answer": None}
            counts["archived_grade_conflicts"] += 1
        elif digest not in outgoing:
            outgoing[digest] = key, wire
        else:
            counts["same_stage_wire_reuse"] += 1
    emitted = {key: wire for key, wire in outgoing.values()}
    returned = checked_dispatch(dispatch, emitted) if emitted else {}
    counts["new_wire_positions"] += len(emitted)
    by_wire.update({digest: returned[key] for digest, (key, _) in outgoing.items()})
    return {key: by_wire[digest] for key, digest in index.items()}


def evaluate(benchmark, dispatch):
    """Run only the exposed roster. The caller controls transport and exact-cache policy."""
    counts = Counter()
    answers = generate(development_roots(benchmark), lambda jobs: cached_dispatch(dispatch, jobs, {}, (), counts))
    cases, protocol, controls = context(benchmark)
    if cases.keys() != {r["uid"] for r in answers}:
        raise ValueError("Transfer scorer and draft roster do not match")
    archive = archived_answers(benchmark, cases)
    cache, conflicts = matching_grading_receipts(benchmark, cases, protocol, archive)
    grade(benchmark, answers, cases, protocol,
          lambda jobs: cached_dispatch(dispatch, jobs, cache, conflicts, counts))
    return answers, {**summarize(benchmark, answers, cases, controls), "request_positions": counts}


if __name__ == "__main__":
    for benchmark in PANELS:
        cases, protocol, controls = context(benchmark)
        panel = development_roots(benchmark)
        archive = archived_answers(benchmark, cases)
        wires = draft_wires(panel)
        observed = {sha(r["actor_request"]) for r in archive if r.get("actor_request") and r["actor_status"] == "OK"}
        drafts = {sha(wire) for wire in wires.values()}
        raw, ambiguous = matching_grading_receipts(benchmark, cases, protocol, archive)
        print(json.dumps({
            "benchmark": benchmark, "roots": len(panel), "distinct_task_only_wires": len(drafts),
            "exact_draft_hits_in_exposed_actor_archives": len(drafts & observed),
            "exact_archived_scoring_wires": len(raw), "ambiguous_old_scoring_wires": len(ambiguous),
            "old_valid_by_method": dict(Counter(r["method"] for r in controls if r["score"] is not None)),
            "new_model_calls": 0, "new_method_scores": 0,
        }, ensure_ascii=False))
