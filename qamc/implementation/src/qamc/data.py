"""Benchmark adapters: inference histories and private evaluation references separate."""
from __future__ import annotations

import collections
import datetime as dt
import json
import random
import subprocess
from pathlib import Path

from .common import ROOT, dump, sha, token_estimate

SEED = 20261023
MEMSYCO_TASKS = ("objective_fact_judgment", "contextual_scope_control", "memory_evidence_conflict",
                 "valid_memory_selection", "personalized_memory_use")


def date_iso(raw):
    if not raw:
        return None
    for fmt in ("%Y/%m/%d (%a) %H:%M", "%Y/%m/%d (%A) %H:%M", "%Y-%m-%d", "%Y/%m/%d",
                "%I:%M %p on %d %B, %Y", "%I:%M %p on %d %B %Y"):
        try:
            return dt.datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            pass
    return raw


def stratified(items, n, key, rng):
    groups = collections.defaultdict(list)
    for item in items:
        groups[key(item)].append(item)
    for group in groups.values():
        rng.shuffle(group)
    selected = []
    names = sorted(groups, key=str)
    rng.shuffle(names)
    while len(selected) < n:
        changed = False
        for name in names:
            if groups[name] and len(selected) < n:
                selected.append(groups[name].pop())
                changed = True
        if not changed:
            raise ValueError("insufficient stratified candidates")
    return selected


def prepare():
    out = ROOT / "data"
    if (out / "cases.json").exists():
        raise RuntimeError("manifest already exists; never silently reselect")
    rng = random.Random(SEED)
    cases, refs, sources = [], {}, {}
    for task in MEMSYCO_TASKS:
        path = ROOT / "vendor" / "MemSyco-Bench" / "data" / (task + ".jsonl")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        # Three question phrasings for one situation are not independent roots.
        roots = {}
        for row in rows:
            signature = sha(row["dialogue"])
            roots.setdefault(signature, []).append(row)
        representatives = [rng.choice(group) for group in roots.values()]
        selected = stratified(representatives, 20, lambda r: r["metadata"].get("topic", r["metadata"].get("subtype", "unknown")), rng)
        sources[task] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes()),
                         "rows": len(rows), "distinct_histories": len(roots)}
        for row in selected:
            uid = "memsyco/" + task + "/" + row["id"]
            history = [{"id": f"h{i:03d}", "role": t["role"], "content": t["content"]}
                       for i, t in enumerate(row["dialogue"], 1)]
            cases.append({"uid": uid, "benchmark": "memsyco", "namespace": uid, "query": row["question"],
                          "query_time": None, "history": history, "category": task, "native_id": row["id"]})
            refs[uid] = row
    path = out / "longmemeval_s_cleaned.json"
    rows = json.loads(path.read_text())
    selected = stratified(rows, 50, lambda r: ("abstention" if "_abs" in r["question_id"] else r["question_type"]), rng)
    sources["longmemeval"] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes()),
                              "rows": len(rows), "dataset_revision": "98d7416c24c778c2fee6e6f3006e7a073259d48f"}
    for row in selected:
        uid = "longmemeval/" + row["question_id"]
        sessions = sorted(zip(row["haystack_dates"], row["haystack_session_ids"], row["haystack_sessions"]),
                          key=lambda x: (date_iso(x[0]), x[1]))
        history = []
        for date, sid, turns in sessions:
            for n, turn in enumerate(turns, 1):
                history.append({"id": f"{sid}/t{n}", "role": turn["role"], "content": turn["content"],
                                "session_id": sid, "recorded_at": date_iso(date)})
        cases.append({"uid": uid, "benchmark": "longmemeval", "namespace": uid,
                      "query": row["question"], "query_time": date_iso(row["question_date"]),
                      "history": history, "category": "abstention" if "_abs" in row["question_id"] else row["question_type"],
                      "native_id": row["question_id"]})
        refs[uid] = row
    path = ROOT / "vendor" / "locomo" / "data" / "locomo10.json"
    conversations = json.loads(path.read_text())
    # Select two entire conversations before sampling any question or answer.
    shuffled = list(conversations)
    rng.shuffle(shuffled)
    chosen = shuffled[:2]
    if set(q["category"] for conv in chosen for q in conv["qa"]) != {1, 2, 3, 4, 5}:
        chosen = next([a, b] for j, a in enumerate(shuffled) for b in shuffled[j + 1:]
                      if set(q["category"] for conv in (a, b) for q in conv["qa"]) == {1, 2, 3, 4, 5})
    sources["locomo"] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes()),
                         "conversations": len(conversations), "selected_conversations": [c["sample_id"] for c in chosen],
                         "modality": "official text plus provided image captions; image pixels not sent"}
    for conv in chosen:
        history = []
        sessions = sorted([k for k in conv["conversation"] if k.startswith("session_") and not k.endswith("_date_time")], key=lambda k: int(k.split("_")[1]))
        for sid in sessions:
            date = date_iso(conv["conversation"][sid + "_date_time"])
            for turn in conv["conversation"][sid]:
                text = turn["text"]
                if turn.get("blip_caption"):
                    text += "\n[Provided image caption] " + turn["blip_caption"]
                history.append({"id": turn["dia_id"], "role": "user", "speaker": turn["speaker"],
                                "content": text, "session_id": sid, "recorded_at": date})
        indices = stratified(list(range(len(conv["qa"]))), 25, lambda j: conv["qa"][j]["category"], rng)
        for j in indices:
            row = conv["qa"][j]
            uid = f"locomo/{conv['sample_id']}/q{j:03d}"
            cases.append({"uid": uid, "benchmark": "locomo", "namespace": "locomo/" + conv["sample_id"],
                          "query": row["question"], "query_time": history[-1]["recorded_at"], "history": history,
                          "category": str(row["category"]), "native_id": f"{conv['sample_id']}/q{j:03d}"})
            refs[uid] = row
    assert len(cases) == 200 and len({c["uid"] for c in cases}) == 200
    for c in cases:
        assert all(set(t) <= {"id", "role", "content", "speaker", "session_id", "recorded_at"} for t in c["history"])
    summary = [{k: c[k] for k in ("uid", "benchmark", "namespace", "native_id", "category")} |
               {"history_turns": len(c["history"]), "history_sha256": sha(c["history"]),
                "history_tokens_cl100k_estimate": token_estimate(json.dumps(c["history"], ensure_ascii=False))}
               for c in cases]
    commits = {repo: subprocess.check_output(["git", "-C", str(ROOT / "vendor" / repo), "rev-parse", "HEAD"], text=True).strip()
               for repo in ("LongMemEval", "locomo")}
    commits["MemSyco-Bench"] = "3c3aa013ac5bee2f0e252fe8748644edc7f9af0a"
    dump(out / "cases.json", cases)
    dump(out / "evaluation_references.json", refs)
    dump(ROOT / "DATA_MANIFEST.json", {"seed": SEED, "phase": "development_200", "sources": sources,
                                       "commits": commits, "selected": summary, "gold_separate": True,
                                       "writer_does_not_receive_query": True, "oracle_history": False})
    print(json.dumps({"cases": len(cases), "categories": dict(collections.Counter(c["benchmark"] + "/" + c["category"] for c in cases)),
                      "namespaces": len({c["namespace"] for c in cases})}, indent=2))


if __name__ == "__main__":
    prepare()
