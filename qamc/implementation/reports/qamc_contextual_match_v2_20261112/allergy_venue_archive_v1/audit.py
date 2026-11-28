"""Screen exposed archived answers for explicit venue decisions without calling a model."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess

from qamc.common import parse_object, sha

BASE = Path(__file__).resolve().parent.parent
RUN = BASE.parents[1] / "runs" / BASE.name
SAMPLES = ("3776469a", "dbcf603f")
# Outcome witnesses selected after reviewing archive text; never used for inference.
WITNESSES = {
    "3776469a": ("47c288779138", "d3362a58d084", "a1cfa20fa203"),
    "dbcf603f": ("295fd1a924f1", "c8c0c163af51", "03d7a73a8c1e"),
}
STAGES = {
    "Actor", "PolicyActor", "FinalActor", "Remaining1Actor", "FusionTransferActor",
    "Final", "GroundedActor", "Draw1_PB_GEPA", "Draw1_PB_RUBRIC", "CommitmentActor",
    "Wave0_Actor",
}
VENUE = re.compile(
    r"cat.free|pet.free|neutral (venue|location|space)|another venue|new venue|"
    r"(different|different suitable|alternate|alternative|another) (location|venue|home|place)|"
    r"(meeting room|community center|cafe|café|library|board game lounge)|"
    r"host (?:at|from) (?:my|our|your) (?:place|home|house)", re.I
)


def read(path):
    return json.loads(path.read_text())


def reference(prefix):
    result = subprocess.check_output([
        "bash", str(BASE / "persist_utility_fresh_deployment_v1" / "inspect.sh"), prefix
    ], cwd=BASE.parents[1], text=True)
    sample = json.loads(result)
    topic = sample["public"]
    allergy, = [m for m in topic["memories"] if "cat" in m.lower() and "allerg" in m.lower()]
    cat, = [m for m in topic["memories"] if "cat named" in m.lower()]
    return sample["uid"], topic["query"], allergy, cat


def source_texts(wire):
    return "\n".join(msg["content"] for msg in wire["messages"]
                     if msg["role"] in {"user", "system"} and isinstance(msg["content"], str))


def screen(prefix, private_candidates):
    uid, query, allergy, cat = reference(prefix)
    glob = subprocess.run(
        ["rg", "-l", "-F", "-g", "record.json", uid, str(RUN)],
        check=True, capture_output=True, text=True,
    )
    counts = Counter()
    rows = defaultdict(set)
    lexemes, witnesses = {}, {}
    candidate_paths = sorted(Path(s) for s in glob.stdout.splitlines())
    for path in candidate_paths:
        receipt = read(path)
        unit = receipt["unit"]
        if unit["root_id"] != uid or unit["stage"] not in STAGES:
            continue
        counts["physical_final_stage_records"] += 1
        if receipt["status"] != "OK":
            counts["non_ok_final_stage_records"] += 1
            continue
        wire = read(path.with_name("request.json"))
        if sha(wire) != receipt["request_sha256"]:
            raise ValueError(f"Unverified request for {unit['stage']}")
        source = source_texts(wire)
        if query not in source:
            counts["no_exact_query_match"] += 1
            continue
        answer = read(path.with_name("response.json"))["answer"].strip()
        if not answer or answer.startswith(("{", "[", "\x60\x60\x60")):
            counts["empty_or_structured_output"] += 1
            continue
        counts["eligible_physical_drafts"] += 1
        digest = sha(answer)
        rows[digest].add((allergy in source, cat in source))
        short = digest[:12]
        if short in WITNESSES[prefix]:
            if short in witnesses and witnesses[short]["answer"] != answer:
                raise ValueError("Witness digest collision")
            witnesses[short] = {"answer": answer, "run": path.relative_to(RUN).parts[0],
                                "method": unit["method"], "grade_receipts": []}
        lexemes[digest] = [line.strip() for line in answer.splitlines() if VENUE.search(line)]
    counts["unique_plain_drafts"] = len(rows)
    counts["unique_with_venue_terms"] = sum(bool(v) for v in lexemes.values())
    both = [digest for digest, cases in rows.items() if (True, True) in cases]
    counts["unique_with_both_sources_in_request"] = len(both)
    counts["unique_with_both_sources_and_venue_terms"] = sum(bool(lexemes[digest]) for digest in both)
    if set(witnesses) != set(WITNESSES[prefix]):
        raise ValueError("Expected archived witnesses are missing")
    for path in candidate_paths:
        receipt = read(path)
        unit = receipt["unit"]
        if (unit["root_id"] != uid or receipt["status"] != "OK"
                or not re.search("judge|grade|native", unit["stage"], re.I)):
            continue
        wire = read(path.with_name("request.json"))
        source = source_texts(wire)
        for witness in witnesses.values():
            if witness["answer"] not in source or query not in source:
                continue
            if sha(wire) != receipt["request_sha256"]:
                raise ValueError("Unverified Judge request")
            try:
                rating = parse_object(read(path.with_name("response.json"))["answer"]).get("rating")
            except (TypeError, ValueError):
                continue
            if type(rating) is int and 1 <= rating <= 3:
                witness["grade_receipts"].append({"run": path.relative_to(RUN).parts[0],
                                                  "judge_alias": wire["model"], "rating": rating})
    for witness in witnesses.values():
        if not witness["grade_receipts"] or (True, True) not in rows[sha(witness.pop("answer"))]:
            raise ValueError("Witness needs verified exact evidence and a grading receipt")
    data = {"counts": dict(counts), "grade_witnesses": witnesses}
    if private_candidates:
        data["matching_lines_private"] = {
            digest[:12]: {"both_sources": digest in both, "lines": lines}
            for digest, lines in lexemes.items() if lines
        }
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-candidates", action="store_true")
    args = parser.parse_args()
    print(json.dumps({prefix: screen(prefix, args.private_candidates) for prefix in SAMPLES}, indent=2))
