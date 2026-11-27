"""Target archived replacement losses with the original fixed-prompt masking intervention."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
base = here.parent
spec = importlib.util.spec_from_file_location("original_visibility", base / "des2gen_suppressed_visibility_v1/trial.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)

def prepare():
    prior = original.read(base / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    formal = original.read(original.formal.OUT / "RESULT_ROWS.json")
    index = {(r["uid"], r["method"]): r for r in formal}
    seen = set()
    wires = {}
    for row in sorted(prior, key=lambda r: original.sha([here.name, r["uid"]])):
        uid = row["uid"]
        if row["old_route"] != "REUSE_RP" or row["source_group"] in seen:
            continue
        rp, des = (index[uid, name] for name in ("RPR_PAPER_FULL","DES2GEN_FULL"))
        a, b = row["ipe_c"]["grade"], des.get("native_fields") or {}
        if not all(g.get("match") and all(g.get(k) is not None for k in ("OPB","UPB","FM")) for g in (a,b)):
            continue
        if b["match"]["matched"] >= a["match"]["matched"]:
            continue
        wire = des["actor_request"]
        assert original.sha(wire) == des["actor_request_sha256"]
        p, d = [json.loads(x["actor_request"]["messages"][-1]["content"]) for x in (rp, des)]
        assert p["source_evidence"] == d["source_evidence"]
        allow = {x["memory_id"] for x in p["preference_use_policy"] if x["policy"] != "A"}
        hard = {x["memory_id"] for x in p["preference_use_policy"] if x["policy"] == "C"}
        keep = {x["memory_id"] for x in d["applicability_decisions"] if x["decision"] == "Apply"}
        if not (keep < allow and hard <= keep):
            continue
        assert json.dumps(d, ensure_ascii=False) == wire["messages"][-1]["content"]
        for source in d["source_evidence"]:
            if source["memory_id"] not in keep:
                source["text"] = ""
        masked = deepcopy(wire)
        masked["messages"][-1]["content"] = json.dumps(d, ensure_ascii=False)
        wires[uid,"full"] = wire
        wires[uid,"masked"] = masked
        seen.add(row["source_group"])
        if len(seen) == 4:
            break
    assert wires
    return wires

original.HERE = here
original.RUN = original.RUN.with_name(here.name)
original.OUT = original.RUN / "private"
original.prepare = prepare
if __name__ == "__main__":
    original.main(sys.argv[1])
