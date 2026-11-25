"""Verify the frozen development panel and reconstruct initial requests offline."""
import json
from hashlib import sha256
from pathlib import Path

from build_jobs import archive_inputs
from persist_grounding_gepa_wires import check_archive, input_requests, smoke, transfer
from qamc.common import sha

HERE = Path(__file__).resolve().parent


def prepare():
    panel = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())
    for path, expected in panel["inputs"].items():
        if sha256((transfer.ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen input drift: {path}")
    source_rows = smoke.source()
    public_by_digest = {}

    for row in source_rows:
        public = smoke.public(row)
        public_by_digest[sha(public)] = public
    protocol = transfer.read(transfer.OUT / "PLAN.json")
    wires, _ = archive_inputs()
    items = {}
    for case in panel["cases"]:
        uid = case["uid"]
        baseline = wires["PersistBench", uid]
        for field in ("actor_request", "answer"):
            if sha(baseline[field]) != case[f"{field}_sha256"]:
                raise ValueError(f"{uid}: archived {field} drift")
        prefix = uid.split("/")[-1]
        matches = [public for digest, public in public_by_digest.items() if digest.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"{uid}: expected exactly one source match")
        items[uid] = input_requests(case, matches[0], protocol)
    if len(items) != len(panel["cases"]):
        raise ValueError("Duplicate frozen case")
    return items, check_archive(source_rows)


if __name__ == "__main__":
    items, historical = prepare()
    print(json.dumps({"panel_cases": len(items), "historical_exact": historical,
                      "request_hashes": {uid: {key: sha(wire) for key, wire in requests.items()}
                                         for uid, requests in items.items()}}, indent=2))
