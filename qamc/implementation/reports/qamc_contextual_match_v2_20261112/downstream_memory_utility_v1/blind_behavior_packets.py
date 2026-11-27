"""Build a private, score-masked behavior audit from completed final-stage receipts."""
from collections import Counter, defaultdict
import json

from controller import finalize
from qamc.common import sha
from run_car import ARMS, RUN, preflight, probe
from summarize_pilot import METHODS


def pack_jobs(plan, cards, manifest, receipts):
    known = {r["root"]["uid"]: r for r in cards}
    units = defaultdict(dict)
    for item in manifest["units"]:
        job = item["unit"]
        uid, method = job["root_id"], job["method"]
        if uid not in known or method not in ARMS or method in units[uid]:
            raise ValueError("Invalid final-stage allocation")
        units[uid][method] = item["request"]
    blind, crosswalk = [], {}
    counts = defaultdict(Counter)
    for uid, card in known.items():
        if not units[uid]:
            counts[card["benchmark"]]["unissued"] += 1
            continue
        if units[uid].keys() != set(ARMS):
            raise ValueError("Expected all registered user controllers")
        shared = units[uid]["WHOLE"]["messages"][1]
        if any(w["messages"][1] != shared for w in units[uid].values()):
            raise ValueError("Final controllers saw different user packets")
        counts[card["benchmark"]]["issued"] += 1
        payload = json.loads(shared["content"])
        groups = defaultdict(list)
        groups[card["base_answer"]].append("BASE")
        missing = []
        for arm in ARMS:
            rec, raw = receipts[uid, arm]
            if not rec or rec["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Final stage is still in flight")
            if rec["request_sha256"] != sha(units[uid][arm]):
                raise ValueError("Cannot match final transport response to the original wire")
            if rec["status"] != "OK":
                missing.append(arm)
                continue
            assembled = finalize(arm, raw, payload["candidates"], payload["fallback"], payload["protected_literals"])
            groups[assembled.answer].append(arm)
        key = sha(["car-behavior-case", plan["panel_sha256"], uid])[:20]
        outputs = {}
        mapping = {}
        for answer, methods in sorted(groups.items(), key=lambda group: sha([key, group[0]])):
            label = sha(["car-behavior-answer", key, answer])[:12]
            outputs[label] = answer
            mapping[label] = sorted(methods, key=METHODS.index)
        blind.append({"case": key, "benchmark": card["benchmark"], "task": payload["task"],
                      "original_sources": payload["source_evidence"], "answers": outputs})
        crosswalk[key] = {"uid": uid, "methods": mapping, "missing_delivery": missing}
        counts[card["benchmark"]]["distinct_answers"] += len(outputs)
        counts[card["benchmark"]]["missing_delivery"] += len(missing)
    return sorted(blind, key=lambda x: x["case"]), crosswalk, counts


if __name__ == "__main__":
    plan, cards = preflight()
    if probe.read(RUN / "FROZEN.json") != plan:
        raise ValueError("Behavior audit does not match the frozen trial")
    probe.RUN = probe.OUT = RUN
    manifest = probe.read(RUN / "Final_MANIFEST.json")
    review, key, counts = pack_jobs(plan, cards, manifest, probe.stage_receipts("Final"))
    probe.freeze(RUN / "PRIVATE_BEHAVIOR_PACKETS.json", review)
    probe.freeze(RUN / "PRIVATE_BEHAVIOR_CROSSWALK.json", key)
    print(json.dumps(counts, indent=2, sort_keys=True))
