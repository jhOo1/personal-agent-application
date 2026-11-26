"""Freeze a source-disjoint audit and emit private, endpoint-anonymous packets."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SALT = "rpe-paper-behavior-alignment-v1"
METHODS = ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
sys.path.insert(0, str(HERE.parent / "paper_rpe_paired_uncertainty_v1"))
from analyze import matched, verify_allocated_labels


def digest(s):
    return sha256(s.encode()).hexdigest()


def freeze(base):
    archive = base / "ipe_c_two_endpoint_completion_v1/RESULTS.json"
    rows = json.loads(archive.read_bytes())["rows"]
    verify_allocated_labels(archive.resolve(), rows)
    common = [r for r in rows if "C" in r["labels"] and all(matched(r, m) is not None for m in METHODS)]
    if len(common) != 110:
        raise ValueError("The common contains-C panel has changed")
    previous = {"explicit/114", "explicit/128", "implicit/118"}
    used = {r["source_group"] for r in common if any(r["uid"].endswith("/" + uid) for uid in previous)}
    selected = []
    for kind in ("route_off", "multiple_C", "one_C"):
        quota = {"route_off": 3, "multiple_C": 5, "one_C": 12 - len(selected)}[kind]
        count = 0
        for row in sorted(common, key=lambda r: digest(SALT + r["uid"])):
            category = ("route_off" if row["old_route"] != "REUSE_RP"
                        else "multiple_C" if row["labels"].count("C") > 1 else "one_C")
            if category != kind or row["source_group"] in used:
                continue
            used.add(row["source_group"])
            selected.append((kind, row))
            count += 1
            if count == quota:
                break
        if count != quota and kind != "route_off":
            raise ValueError(f"Insufficient distinct sources for {kind}")
    task_dir = base / "rpeval_formal_multi_coverage_v1"
    tasks = json.loads((task_dir / "PUBLIC_TASKS.json").read_bytes())
    full = {r["uid"]: r for r in json.loads((task_dir / "RESULT_ROWS.json").read_bytes())
            if r["method"] == "RPR_PAPER_FULL"}
    packets, key = [], {}
    for i, (kind, row) in enumerate(selected, 1):
        uid = row["uid"]
        task = tasks[uid]
        archives = {
            "TASK_ONLY": row["no_history_state"]["answer"],
            "RPR_PAPER_FULL": full[uid]["answer"],
        }
        for name, answer in archives.items():
            if digest(answer) != row["scores"][name]["answer_sha256"]:
                raise ValueError("Saved answer hash disagrees with the scored answer")
        decision = "RPR_PAPER_FULL" if row["old_route"] == "REUSE_RP" else "TASK_ONLY"
        if row["scores"]["IPE_C"]["answer_sha256"] != digest(archives[decision]):
            raise ValueError("IPE-C diverges from its recorded endpoint")
        if len(task["memories"]) != len(row["labels"]):
            raise ValueError("Author positions are not aligned with memories")
        order = sorted(archives, key=lambda a: digest(SALT + uid + a))
        case = f"{i:02d}"
        packets.append({"case": case, "query": task["query"], "context": task["current_context"],
                        "facts": task["fixed_facts"],
                        "C": [m["text"] for m, label in zip(task["memories"], row["labels"]) if label == "C"],
                        "answers": {letter: archives[arm] for letter, arm in zip("XY", order)}})
        key[case] = {"uid": uid, "kind": kind, "group": row["source_group"],
                     "mapping": dict(zip("XY", order)), "ipe_c_endpoint": decision}
    raw = json.dumps(packets, ensure_ascii=False, indent=2).encode()
    fingerprint = {"archive_sha256": sha256(archive.read_bytes()).hexdigest(), "strata": Counter(k for k, _ in selected),
                   "tasks": len(selected), "groups": len({r["source_group"] for _, r in selected}),
                   "C_positions": sum(r["labels"].count("C") for _, r in selected),
                   "packet_sha256": sha256(raw).hexdigest()}
    return raw, key, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research_report_root", type=Path)
    parser.add_argument("private_output", type=Path)
    args = parser.parse_args()
    raw, key, fingerprint = freeze(args.research_report_root)
    args.private_output.mkdir(parents=True, exist_ok=True)
    files = {"PACKETS.json": raw, "KEY.json": json.dumps(key, indent=2).encode()}
    for name, content in files.items():
        path = args.private_output / name
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"Refusing to change frozen artifact {name}")
        path.write_bytes(content)
    print(json.dumps(fingerprint, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
