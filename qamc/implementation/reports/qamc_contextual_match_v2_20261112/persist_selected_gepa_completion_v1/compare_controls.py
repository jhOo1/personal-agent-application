"""Compare completed SELECTED_GEPA against verified, saved whole-method controls."""
from collections import Counter, defaultdict
import json

from complete import RUN, BASE, METHOD, archive, get_author, normalized, passes, read
from qamc.common import sha

STAGES = ("selected_gepa_expansion_v1", "persist_performance_v1")
EXTERNAL = "persist_memadapter_alignment_v1"


def compare():
    author, bounds, _ = get_author()
    controls = defaultdict(dict)
    for row in author:
        if row["score"] is not None:
            controls[row["uid"]][row["method"]] = row["score"]
    selected = {}
    for stage in (*STAGES, EXTERNAL):
        rows, _ = archive["supplementary"](BASE / "native_residual_v1" / stage, bounds, Counter())
        for row in rows:
            uid = row["uid"]
            if stage == EXTERNAL:
                method = row["method"]
                if method in controls[uid]:
                    raise ValueError("Duplicate external result")
                controls[uid][method] = row["score"]
            elif row["method"] == METHOD and uid not in selected:
                selected[uid] = (row["category"], row["score"])
            elif row["method"] == METHOD:
                raise ValueError("Duplicate selected result")
    rows, _ = archive["factorial"](bounds, Counter())
    for row in rows:
        uid = row["uid"]
        if uid in selected:
            raise ValueError("Duplicate selected result")
        selected[uid] = (row["category"], row["score"])
    manifest = RUN / "PersistNative_MANIFEST.json"
    wires = {x["unit"]["root_id"]: x["request"] for x in read(manifest)["units"]} if manifest.exists() else {}
    for row in read(RUN / "RESULTS.json")["rows"]:
        uid = row["uid"]
        if row["score"] is None:
            continue
        if uid in selected:
            raise ValueError("Completed result already archived")
        if row["judge"]["origin"] == "EXACT_ARCHIVE":
            if row["score"]["rating"] != controls[uid]["PB_RUBRIC"]["rating"]:
                raise ValueError("Reused rating changed")
        else:
            wire = wires[uid]
            if (row["judge"]["request_sha256"] != sha(wire)
                    or normalized(wire, row["answer"]) != bounds[uid]):
                raise ValueError("Completed score manifest drift")
        selected[uid] = (row["category"], row["score"])
    comparisons = defaultdict(Counter)
    for uid, (track, score) in selected.items():
        active = passes(score, track)
        for method, other_score in controls[uid].items():
            other = passes(other_score, track)
            for category in ("all", track):
                comparisons[f"{method}/{category}"].update(
                    common=1, selected_pass=active, reference_pass=other,
                    wins=active and not other, losses=other and not active)
    return comparisons


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, sort_keys=True))
