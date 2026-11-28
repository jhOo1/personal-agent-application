"""Audit screened candidate strings against the separate strong Actor's captured wire."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from baselines import archive
from qamc.common import sha

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUN = HERE.parents[2] / "runs" / BASE.name / HERE.name


def read(path):
    return json.loads(path.read_text())


def visible(messages, source):
    """Exact literal presence, accounting for canonical JSON escaping of a source."""
    plain = [m["content"] for m in messages if isinstance(m.get("content"), str)]
    spellings = {source, json.dumps(source, ensure_ascii=False)[1:-1], json.dumps(source)[1:-1]}
    return any(original in text for original in spellings for text in plain)


def main():
    freeze = read(RUN / "private/FREEZE.json")
    panel = set(u for u, _ in freeze["requests"])
    rows = {r["uid"]: r for r in read(BASE / "transactional_reassembly_v1/FROZEN.json")["rows"]
            if r["uid"] in panel}
    if set(rows) != panel:
        raise ValueError("Panel mismatch")
    rpe_rows = {r["uid"]: r for r in read(
        BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"] if r["uid"] in panel}
    decisions = {r["uid"]: r for r in read(RUN / "private/RESULTS.json")["rows"]}
    bank = {r["uid"]: r for r in read(archive.v41.formal.OUT / "RESULT_ROWS.json")
            if r["uid"] in panel and r["method"] == archive.engine.RP and r["actor_status"] == "OK"}
    for b, method in (("BenchPreS", archive.engine.GATE), ("PersistBench", "PB_RUBRIC")):
        cases, _, _ = archive.transfer.context(b)
        selected = {u: c for u, c in cases.items() if u in panel}
        for r in archive.transfer.archived_answers(b, selected):
            if r["method"] == method and r["actor_status"] == "OK" and r.get("actor_request"):
                if r["uid"] in bank:
                    raise ValueError("Ambiguous archived strong request")
                bank[r["uid"]] = r
    counts = defaultdict(Counter)
    for uid, row in rows.items():
        c = counts[row["benchmark"]]
        c["assigned"] += 1
        sources = [m["text"] for m in row["packet"]["source_evidence"]]
        c["candidate_sources"] += len(sources)
        rpe = rpe_rows.get(uid)
        exposure = None
        if rpe and rpe["old_route"] == "REUSE_ORIGINAL_TASK_ONLY_STATE":
            c["task_only_strong_draft"] += 1
            exposure = [False] * len(sources)
        else:
            r = bank.get(uid)
            if r and sha(r["answer"].strip()) == row["baseline_answer_sha256"]:
                wire = r["actor_request"]
                if sha(wire) != r["actor_request_sha256"]:
                    raise ValueError("Actor archive hash mismatch")
                exposure = [visible(wire["messages"], s) for s in sources]
        if exposure is None:
            c["unverified_strong_actor"] += 1
        else:
            n = sum(exposure)
            c["literal_seen"] += n
            c["all_seen" if n == len(sources) else "none_seen" if n == 0 else "part_seen"] += 1
        for name in ("direct", "conflict"):
            choice = decisions[uid][name]
            if choice is None:
                continue
            item = row["packet"]["source_evidence"][choice - 1]
            seen = "unknown" if exposure is None else "seen" if exposure[choice - 1] else "not_seen"
            c[name + "/" + seen] += 1
            if rpe and [s["memory_id"] for s in row["packet"]["source_evidence"]] == [
                    f"M{i}" for i in range(len(rpe["labels"]))]:
                label = rpe["labels"][choice - 1]
            elif row["benchmark"] == "BenchPreS":
                labels = {d["appropriate"] for d in row["base_score"]["decisions"]
                          if d["preference"] == item["text"]}
                label = ("appropriate" if True in labels else "inappropriate") if len(labels) == 1 else "unknown"
            else:
                label = "unknown"
            c[name + "/" + label] += 1
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
