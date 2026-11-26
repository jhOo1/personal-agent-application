"""Replace only the original IPE-C history branch by archived Des2Gen FULL."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = "DES2GEN_FULL"
HISTORY = "REUSE_RP"
TASK_ONLY = {"REUSE_DRAFT", "REUSE_ORIGINAL_TASK_ONLY_STATE", "NEW_DRAFT"}


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(value):
    encoded = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def replay():
    route_rows = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    scores = {}
    for row in read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
        if row["method"] != TARGET or row["actor_status"] != "OK":
            continue
        uid = row["uid"]
        if uid in scores or digest(row["actor_request"]) != row["actor_request_sha256"]:
            raise ValueError(f"Invalid archived Des2Gen request: {uid}")
        scores[uid] = row
    metrics = defaultdict(Counter)
    missing = Counter()
    for row in route_rows:
        uid, route, labels = row["uid"], row["old_route"], row["labels"]
        if route not in TASK_ONLY and route != HISTORY:
            missing["unknown_route"] += 1
            continue
        scope = "all_A" if labels and set(labels) == {"A"} else "contains_C" if labels and "C" in labels else "only_B"
        base = row["ipe_c"]
        if route == HISTORY:
            if base["answer_sha256"] != row["controls"]["RPR_PAPER_FULL"]["answer_sha256"]:
                raise ValueError(f"Routing does not match the archived RP answer: {uid}")
            new = scores.get(uid, {}).get("native_fields") or {}
        else:
            new = base.get("grade") or {}
        old = base.get("grade") or {}
        if not labels or not old.get("match") or not new.get("match"):
            missing["history_missing" if route == HISTORY else "task_only_missing"] += 1
            continue
        n = len(labels)
        if old["match"]["positions"] != n or new["match"]["positions"] != n:
            raise ValueError(f"Position count differs: {uid}")
        a, b = old["match"]["matched"], new["match"]["matched"]
        scopes = ["all", scope]
        if route == HISTORY:
            scopes += ["history", f"history/{scope}"]
        for part in scopes:
            metrics[part].update({"n": 1, "positions": n, "ipe_c": a, "combined": b,
                                  "win": b > a, "loss": b < a, "tie": b == a})
            for field in ("OPB", "UPB", "FM"):
                if old.get(field) is not None and new.get(field) is not None:
                    metrics[part].update({f"base_{field}": old[field], f"new_{field}": new[field]})
    return {"metrics": metrics, "missing": missing}


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
