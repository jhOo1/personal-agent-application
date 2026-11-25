"""Census the role assignments in the archived outcome-compiler experiment."""
from collections import Counter
import json

from qamc.common import parse_object, sha

import run_outcome_contract as run


def audit():
    settled_path = run.OUT / "item_header_recovery" / "SETTLED.json"
    settled = run.read(settled_path)
    original = run.read(run.OUT / (run.CONTRACT + "_EXACT.json"))
    manifest = run.read(run.OUT / (run.CONTRACT + "_MANIFEST.json"))
    requests = {item["unit"]["root_id"]: sha(item["request"]) for item in manifest["units"]}
    proposed, accepted, outcomes = Counter(), Counter(), Counter()
    traces = []
    for row in settled["rows"]:
        uid = row["uid"]
        state = settled["contracts"][uid]
        digest = requests[uid]
        record, reply = original[digest]
        if state["request_sha256"] != digest or record["request_sha256"] != digest:
            raise ValueError("Outcome role trace no longer matches its original request")
        raw_roles = []
        if record["status"] == "OK":
            try:
                values = parse_object(reply)["uses"]
                raw_roles = [(entry["site"], entry["authority"]) for entry in values]
            except (ValueError, KeyError, TypeError):
                outcomes["unparseable_proposals"] += 1
        final = [(entry["site"], entry["authority"]) for entry in state.get("uses", [])]
        proposed.update(raw_roles)
        accepted.update(final)
        outcomes.update({state["status"]: 1, "nonempty": int(bool(final)),
                         "multiple_accepted_sites": int(len({site for site, _ in final}) > 1)})
        traces.append({"uid": uid, "task_sha256": row["task"], "request_sha256": digest,
                       "proposed_roles": raw_roles, "accepted_roles": final, "state": state["status"]})
    return {"new_model_calls": 0, "settled_sha256": sha(settled_path.read_bytes()),
            "state_counts": outcomes,
            "proposed": [{"site": site, "authority": authority, "count": n}
                         for (site, authority), n in sorted(proposed.items())],
            "accepted": [{"site": site, "authority": authority, "count": n}
                         for (site, authority), n in sorted(accepted.items())],
            "traces": traces}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
