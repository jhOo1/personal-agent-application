"""Freeze visible-B extractive development targets and intact C protections."""
from collections import Counter
import json
import re

from incremental_panel import HERE, prior, read, sha

OUT = HERE / "RPE_PROJECTION_PANEL.json"
QUOTAS = {False: 1, True: 4}
USER_TURN = re.compile(r"(?m)^用户：")


def build():
    census = read(HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json")["RPEval"]["roots"]
    v41 = prior.R["archived"].v41
    freeze = read(v41.OUT / "FROZEN.json")
    if freeze["independent_confirmation"]:
        raise ValueError("Expected exposed development sources")
    allowed = {row["uid"] for row in freeze["roots"]}
    originals = {
        r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
        if r["uid"] in allowed and r["method"] == "RPR_PAPER_FULL" and r["actor_status"] == "OK"
    }
    pilot = read(HERE / "source_projection_diagnostic_v1" / "RESULTS.json")
    pilot_uids = {row["uid"] for row in pilot["rows"]}
    groups = {row["group"] for row in census if row["uid"] in pilot_uids}
    counts, targets = Counter(), []
    for row in sorted(census, key=lambda r: sha(["projection-automatic-v1", r["uid"]])):
        uid, group = row["uid"], row["group"]
        if group in groups or row["route"] != "RPR_PAPER_FULL" or uid not in originals:
            continue
        old = originals[uid]
        wire = old["actor_request"]
        if sha(wire) != old["actor_request_sha256"]:
            raise ValueError("Actor input drift")
        packet = json.loads(wire["messages"][1]["content"])
        visible = {source["memory_id"]: source["text"] for source in packet["source_evidence"]}
        protected = [p["id"] for p in row["positions"]
                     if p["author_label"] == "C" and p["id"] in visible]
        if any(p["author_label"] == "C" for p in row["positions"]) and not protected:
            continue
        has_c = bool(protected)
        if counts[has_c] >= QUOTAS[has_c]:
            continue
        eligible = [p for p in row["positions"]
                    if p["author_label"] == "B" and p["state"] == "VISIBLE_B"
                    and p["id"] in visible and len(USER_TURN.findall(visible[p["id"]])) >= 2]
        if not eligible:
            continue
        target = min(eligible, key=lambda p: sha([uid, p["id"]]))
        if sha(visible[target["id"]]) != target["source_sha256"]:
            raise ValueError("Source digest mismatch")
        targets.append({
            "uid": uid, "group": group, "source_id": target["id"],
            "source_sha256": target["source_sha256"], "actor_sha256": sha(wire),
            "protected_c": protected, "base_score": row["base_scores"],
        })
        groups.add(group)
        counts[has_c] += 1
    if counts != QUOTAS:
        raise ValueError(f"Insufficient exposed source groups: {counts}")
    return targets


if __name__ == "__main__":
    rows = build()
    if OUT.exists():
        if read(OUT) != rows:
            raise ValueError("Projection panel drift")
    else:
        OUT.write_text(json.dumps(rows, indent=2) + "\n")
    print(len(rows), sum(bool(row["protected_c"]) for row in rows))
