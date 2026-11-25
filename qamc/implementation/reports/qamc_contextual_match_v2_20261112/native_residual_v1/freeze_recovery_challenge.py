"""Freeze group-disjoint exposed targets and all-A protection cases."""
import argparse
import json
from pathlib import Path

from qamc.common import sha

HERE = Path(__file__).resolve().parent
OUT = HERE / "RECOVERY_CHALLENGE.json"


def build():
    census = json.loads((HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json").read_text())
    prior = json.loads((HERE / "incremental_pair_v1" / "RESULTS.json").read_text())
    roots = census["RPEval"]["roots"]
    prior_uids = {r["uid"] for r in prior["rows"]}
    excluded = {r["group"] for r in roots if r["uid"] in prior_uids}
    target_groups = {r["group"] for r in roots if r["group"] not in excluded and any(
        p["state"] == "HIDDEN" and p["author_label"] == "B" for p in r["positions"])}
    output = []
    for group in sorted(target_groups):
        members = [r for r in roots if r["group"] == group and r["route"] == "TASK_ONLY"]
        for role in ("target", "protection"):
            eligible = [
                r for r in members
                if ((r["stratum"] == "B_only" and any(
                    p["state"] == "HIDDEN" and p["author_label"] == "B" for p in r["positions"]))
                    if role == "target" else r["stratum"] == "all_A")
            ]
            if not eligible:
                raise ValueError(f"Insufficient cases for {role} in an eligible group")
            chosen = min(eligible, key=lambda row: sha(["recovery-challenge-v1", row["uid"]]))
            output.append({"uid": chosen["uid"], "group": group, "role": role})
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check"))
    args = parser.parse_args()
    rows = build()
    if args.action == "freeze":
        with OUT.open("x") as stream:
            json.dump(rows, stream, indent=2)
            stream.write("\n")
    elif json.loads(OUT.read_text()) != rows:
        raise ValueError("Frozen recovery challenge drift")
    print(len(rows), "cases from", len({r["group"] for r in rows}), "groups")
