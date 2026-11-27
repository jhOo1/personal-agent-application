"""Independently compare each manifest and available receipt with the frozen archive."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from settle import ARMS, RUN, read


def digest(wire):
    raw = json.dumps(wire, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def verify():
    material = RUN / "material"
    f = read(material / "FROZEN.json")
    policies = read(material / "POLICIES.json")
    old = read(RUN.with_name("benchpres_repeat_matched_v1") / "PLAN_PRIVATE.json")
    wires = {j["unit"]["root_id"]: j["request"] for j in old["generation"].values()
             if j["unit"]["method"] == "GEPA_SELECTED_BOUNDS" and j["unit"]["replicate"] == 0}
    expected = {}
    for u, w in wires.items():
        if digest(w) != f["wire_hashes"][u]:
            raise ValueError("Frozen Gate request changed")
        for arm in ARMS:
            reconstruction = deepcopy(w)
            if arm != "baseline":
                reconstruction["messages"][0]["content"] += "\n\n" + policies[f"{f['folds'][u]}/{arm}"]
            expected[u, arm] = reconstruction
    units = read(material / "Actor_MANIFEST.json")["units"]
    observed = {(e["unit"]["root_id"], e["unit"]["method"]): e["request"] for e in units}
    if len(units) != len(observed) or expected != observed:
        raise ValueError("Unexpected Actor wire or assignment")
    profiles = {}
    for c in old["cases"]:
        group = c["analysis_group_id"]
        group_fold = profiles.setdefault(group, f["folds"][c["uid"]])
        if group_fold != f["folds"][c["uid"]]:
            raise ValueError("Same profile assigned to both folds")
    statuses = Counter()
    seen = set()
    for p in RUN.glob("Actor/visible/*/record.json"):
        r = read(p)
        k = (r["unit"]["root_id"], r["unit"]["method"])
        if k in seen or read(p.with_name("request.json")) != expected[k] or r["request_sha256"] != digest(expected[k]):
            raise ValueError("Receipt does not match unique assigned wire")
        seen.add(k)
        statuses[r["status"]] += 1
    return {"manifest_verified": len(units), "eligible_tasks": len(wires), "assigned_profiles": len(profiles),
            "receipt_status_at_read": dict(statuses), "missing_receipt_at_read": len(units)-len(seen)}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
