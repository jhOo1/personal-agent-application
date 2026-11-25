"""Freeze distinct mixed-history development groups without ranking by scores."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "ROUND2_RPE_MIXED_ELIGIBILITY.json"


def panel():
    inventory = json.loads(INVENTORY.read_text())
    path = HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != inventory["census_sha256"]:
        raise ValueError("Census drift")
    eligible = {uid: group for group, uids in inventory["groups"].items() for uid in uids}
    candidates = [row for row in json.loads(body)["RPEval"]["roots"] if row["uid"] in eligible]
    if len(candidates) != len(eligible):
        raise ValueError("Eligibility mismatch")
    used = set()
    selected = []
    for stratum in ("B_only", "contains_C"):
        pool = sorted((row for row in candidates if row["stratum"] == stratum),
                      key=lambda row: hashlib.sha256(
                          ("round2-mixed-rpe-v1:" + row["uid"]).encode()).hexdigest())
        count = 0
        for row in pool:
            uid, group = row["uid"], row["group"]
            if eligible[uid] != group:
                raise ValueError(f"Source-group drift: {uid}")
            if group in used:
                continue
            selected.append({"uid": uid, "group": group, "stratum": stratum})
            used.add(group)
            count += 1
            if count == 6:
                break
        if count != 6:
            raise ValueError(f"Insufficient exposed source groups: {stratum}")
    return {"rows": selected, "inventory_sha256": hashlib.sha256(INVENTORY.read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(panel(), indent=2))
