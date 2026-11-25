"""Recover the exact frozen selection from successful request receipts."""
import json

from persist_grounding_gepa_wires import select, transfer
from preflight_selected_gepa import HERE, prepare
from qamc.common import sha

ARCHIVE = transfer.ROOT / "runs" / HERE.parent.name / "selected_gepa_expansion_v1"


def receipts(stage):
    results = {}
    for path in (ARCHIVE / stage).glob("visible/*/record.json"):
        record = json.loads(path.read_text())
        uid = record["unit"]["root_id"]
        if uid in results or record["status"] != "OK":
            raise ValueError(f"Unexpected {stage} receipt for {uid}")
        response = json.loads(path.with_name("response.json").read_text())
        results[uid] = record["request_sha256"], response["answer"]
    return results


def recover():
    items, _ = prepare()
    cases = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())["cases"]
    routes, selectors = receipts("QueryRoute"), receipts("EvidenceSelect")
    result = {}
    for case in cases:
        uid = case["uid"]
        wires = items[uid]
        raw = json.loads(wires["grounding"]["messages"][1]["content"])
        public = {"query": raw["query"], "memories": [m["text"] for m in raw["memories"]]}
        route_hash, route = routes[uid]
        selector_hash, selected = selectors[uid]
        branch = "style" if transfer.confirmation.route.decode(route, public["query"])["check_history"] else "grounding"
        if route_hash != sha(wires["query"]) or selector_hash != sha(wires[branch]):
            raise ValueError(f"Archived preparation request mismatch: {uid}")
        result[uid] = {
            "branch": branch, "public": public,
            "evidence": select(case, public, route, selected),
        }
    return result


if __name__ == "__main__":
    rows = recover()
    print(f"Verified {len(rows)} frozen evidence selections")
