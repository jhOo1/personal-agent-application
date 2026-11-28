"""Snapshot verified current crossover answers without accessing any scores."""
from collections import defaultdict
import json
from pathlib import Path

from backbone_interface import OUT, prepare, read, sha

DESTINATION = OUT / "private"


def stable_receipts(pin, jobs):
    expected = {digest for _, _, digest in pin["schedule"]} - pin["fixed_answer_hashes"].keys()
    rows = {}
    for stage in ("QActor", "DActor"):
        for path in sorted((OUT / stage / "visible").glob("*/record.json")):
            row = read(path)
            if row["status"] == "PENDING_DELIVERY_UNKNOWN":
                continue
            unit = row["unit"]
            digest = row["request_sha256"]
            wire = jobs[unit["root_id"], unit["method"]]
            if digest not in expected or sha(wire) != digest:
                raise ValueError("Actor receipt does not match the frozen schedule")
            if digest in rows:
                raise ValueError("Unexpected duplicate physical Actor")
            answer = None
            if row["status"] == "OK":
                answer = read(path.with_name("response.json"))["answer"]
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError("Successful Actor receipt is missing its final answer")
            rows[digest] = {"answer": answer, "status": row["status"]}
    return rows


def snapshot(pin, roster, jobs, cache, receipts):
    result = {}
    for item in roster:
        card = item["card"]
        uid = card["uid"]
        arms = {}
        task_payload = None
        for (root, arm), wire in jobs.items():
            if root != uid:
                continue
            digest = sha(wire)
            payload = json.loads(wire["messages"][1]["content"])
            if task_payload is None:
                task_payload = payload["task"]
            elif task_payload != payload["task"]:
                raise ValueError("Current task differs across crossover wires")
            row = receipts.get(digest, {"answer": None, "status": "NOT_TERMINAL"})
            if digest in cache:
                answer = cache[digest]
                if sha(answer) != pin["fixed_answer_hashes"][digest]:
                    raise ValueError("Cached answer identity changed")
                row = {"answer": answer, "status": "EXACT_ARCHIVE"}
            arms[arm] = {**row, "source_evidence": payload["source_evidence"],
                         "request_sha256": digest, "plan": payload.get("plan")}
        result[uid] = {"benchmark": card["domain"], "stratum": card["stratum"],
                       "task": task_payload, "arms": arms}
    return result


def main():
    pin, roster, jobs, cache, _, _ = prepare()
    if read(DESTINATION / "FROZEN.json") != pin:
        raise ValueError("Current crossover wires differ from the registered experiment")
    receipts = stable_receipts(pin, jobs)
    data = snapshot(pin, roster, jobs, cache, receipts)
    # Snapshot paths include only an aggregate digest and are never overwritten.
    fingerprint = sha(data)
    path = DESTINATION / f"BEHAVIOR_SNAPSHOT_{fingerprint[:12]}.json"
    path.parent.mkdir(exist_ok=True)
    blob = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text() != blob:
            raise ValueError("Conflicting existing behavior snapshot")
    else:
        with path.open("x", encoding="utf-8") as sink:
            path.chmod(0o600)
            sink.write(blob)
    counts = defaultdict(int)
    for case in data.values():
        for arm, row in case["arms"].items():
            counts[case["benchmark"] + "/" + arm.split("/")[0] + "/" + row["status"]] += 1
    print(json.dumps({"snapshots": len(data), "counts": dict(sorted(counts.items())),
                      "private_file": path.name, "snapshot_sha256": fingerprint}, indent=2))


if __name__ == "__main__":
    main()
