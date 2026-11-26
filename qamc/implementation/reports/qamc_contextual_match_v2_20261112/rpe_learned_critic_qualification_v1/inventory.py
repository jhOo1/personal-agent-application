"""Find distinct full answers to the exact frozen IPE-C history Actor requests."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import subprocess

from qamc.common import sha

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def eligible():
    endpoints = read(REPORTS / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    base = {row["uid"]: row for row in endpoints if row["old_route"] == "REUSE_RP"}
    entries = {}
    for row in read(REPORTS / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
        if row["method"] != "RPR_PAPER_FULL" or row["uid"] not in base or row["actor_status"] != "OK":
            continue
        reference = base[row["uid"]]
        answer = row["answer"].strip()
        wire = row["actor_request"]
        if sha(answer) != reference["ipe_c"]["answer_sha256"] or sha(wire) != row["actor_request_sha256"]:
            raise ValueError("Frozen endpoint identity mismatch")
        packet = json.loads(wire["messages"][1]["content"])
        ids = {r["memory_id"] for r in packet["source_evidence"]}
        if not any(p["policy"] == "B" and p["memory_id"] in ids for p in packet["preference_use_policy"]):
            continue
        digest = sha(wire)
        if digest in entries:
            raise ValueError("Ambiguous frozen request digest")
        entries[digest] = (reference, packet, wire, answer)
    return entries


def collect(entries):
    found = defaultdict(dict)
    arguments = ["rg", "--files", "-g", "samples.sqlite",
                 "-g", "!**/*seal*/**", "-g", "!**/*holdout*/**", "-g", "!**/*confirm*/**",
                 "runs", "reports"]
    paths = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    if not entries:
        raise ValueError("No eligible frozen Actor requests")
    columns = {"unit_json", "request_sha", "status", "request_json", "response_json"}
    placeholders = ",".join("?" for _ in entries)
    for path in sorted(paths):
        journal = ROOT / path
        with sqlite3.connect(f"{journal.as_uri()}?mode=ro", uri=True) as db:
            available = {col[1] for col in db.execute("PRAGMA table_info(samples)")}
            if not columns <= available:
                continue
            matches = db.execute(
                f"SELECT unit_json, request_sha, request_json, response_json FROM samples "
                f"WHERE status = 'COMPLETE' AND request_sha IN ({placeholders})", tuple(entries)).fetchall()
        for unit, digest, request, response in matches:
            ref, _, exact_wire, baseline = entries[digest]
            if not response or json.loads(unit).get("root_id") != ref["uid"]:
                continue
            if json.loads(request) != exact_wire:
                raise ValueError("Physical request body mismatch")
            payload = json.loads(response)
            answer = payload.get("answer")
            if isinstance(answer, str) and answer.strip() and payload.get("finish_reason") != "length":
                fingerprint = sha(answer.strip())
                found[digest].setdefault(fingerprint, {"archive": path, "is_baseline": answer.strip() == baseline})
    return found, len(paths)


def summarize(entries, found, paths):
    groups = defaultdict(set)
    counts = defaultdict(Counter)
    pairs = []
    for digest, (ref, packet, _, _) in entries.items():
        labels = ref["labels"]
        labels = list(labels) if isinstance(labels, str) else labels
        stratum = "all_A" if set(labels) == {"A"} else "contains_C" if "C" in labels else "only_B"
        counts[stratum]["eligible"] += 1
        predicted = {p["memory_id"] for p in packet["preference_use_policy"] if p["policy"] == "B"}
        visible = {r["memory_id"] for r in packet["source_evidence"]}
        b_visible = any(lab == "B" and f"M{i}" in predicted & visible for i, lab in enumerate(labels))
        counts[stratum]["has_visible_author_and_predicted_B"] += b_visible
        if not any(not x["is_baseline"] for x in found[digest].values()):
            continue
        counts[stratum]["has_distinct_answer"] += 1
        counts[stratum]["has_distinct_answer_with_visible_B"] += b_visible
        groups[stratum].add(ref["source_group"])
        pairs.append({"case": ref["uid"], "stratum": stratum, "distinct_archived_answers": len(found[digest]),
                      "base_receipt_found": any(x["is_baseline"] for x in found[digest].values()),
                      "visible_B": b_visible})
    return {"eligible_tasks": len(entries), "scanned_journals": paths,
            "categories": {k: dict(c) for k, c in sorted(counts.items())},
            "distinct_answer_groups": {k: len(g) for k, g in sorted(groups.items())},
            "pairs": sorted(pairs, key=lambda item: item["case"]),
            "cloud_requests": 0}


if __name__ == "__main__":
    tasks = eligible()
    print(json.dumps(summarize(tasks, *collect(tasks)), ensure_ascii=False, sort_keys=True, indent=2))
