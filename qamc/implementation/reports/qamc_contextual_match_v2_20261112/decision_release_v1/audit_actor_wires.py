"""Verify separation on the scheduled Actor requests, without exporting text."""
from collections import Counter, defaultdict
import json

from amp_controller import ADAPTER, authorize, free_view, task_frame
from qamc.common import sha
from run_amp import ARMS, RUN, frame_wire, probe, roster


def audit(manifest, cards):
    by_uid = {r["root"]["uid"]: r for r in cards}
    totals = defaultdict(Counter)
    views = defaultdict(dict)
    for entry in manifest["units"]:
        uid = entry["unit"]["root_id"]
        arm = entry["unit"]["method"]
        if arm not in ARMS or arm in views[uid]:
            raise ValueError("Invalid or duplicate Actor arm")
        card = by_uid[uid]
        request = entry["request"]
        original = card["T"]
        if set(request) != set(original) or any(request[k] != original[k] for k in original if k != "messages"):
            raise ValueError("Actor model or settings changed")
        if request["messages"][:1] != original["messages"][:1]:
            raise ValueError("Actor system message changed")
        actual = request["messages"][1]["content"]
        prefix = original["messages"][1]["content"] + "\n\n" + ADAPTER + "\n"
        if not actual.startswith(prefix):
            raise ValueError("Original Actor task payload changed")
        view = json.loads(actual[len(prefix):])
        if set(view) != {"history", "grounded_facts", "decision_controls", "memory_view"}:
            raise ValueError("Unexpected model-visible field")
        if arm == "AMP" and (view["history"] or view["memory_view"]):
            raise ValueError("Unexpected raw history channel")
        if arm == "RAW" and (view["grounded_facts"] or view["memory_view"]):
            raise ValueError("Unexpected transformed history channel")
        if arm == "FREE" and (view["history"] or view["grounded_facts"] or view["decision_controls"]):
            raise ValueError("Unexpected structured history channel")
        counter = totals[card["benchmark"]]
        counter[arm + "_wires"] += 1
        counter[arm + "_empty_view"] += not any(bool(x) for x in view.values())
        if arm == "AMP":
            outputs = [str(value) for channel in ("grounded_facts", "decision_controls")
                       for row in view[channel] for value in row.values()]
            sources = [r["text"].strip() for r in card["root"]["original_sources"]]
            counter["AMP_facts"] += len(view["grounded_facts"])
            counter["AMP_effects"] += len(view["decision_controls"])
            if any(src in output for src in sources if len(src) >= 30 for output in outputs):
                counter["AMP_wires_with_whole_source_in_a_field"] += 1
        views[uid][arm] = view
    for uid, arms in views.items():
        counter = totals[by_uid[uid]["benchmark"]]
        if ("RAW" in arms) != ("AMP" in arms):
            # The dispatch manifest keeps one representative per exact wire.
            # Logical pair counts live in the terminal result's view_counts.
            counter["RAW_AMP_one_representative"] += 1
        if "AMP" not in arms:
            continue
        if "RAW" not in arms:
            continue
        if arms["RAW"]["decision_controls"] != arms["AMP"]["decision_controls"]:
            raise ValueError("Shared arm actions changed")
        counter["RAW_AMP_joint"] += 1
        counter["RAW_AMP_view_diff"] += arms["RAW"] != arms["AMP"]
        counter["RAW_full_records"] += len(arms["RAW"]["history"])
    return totals


def audit_controllers(cards):
    by_uid = {r["root"]["uid"]: r for r in cards}
    probe.OUT = probe.RUN = RUN
    frame_receipts = probe.stage_receipts("Frame")
    frame_manifest = probe.read(RUN / "Frame_MANIFEST.json")
    frame_by_sha = {sha(j["request"]): frame_receipts[j["unit"]["root_id"], j["unit"]["method"]]
                    for j in frame_manifest["units"]}
    counts = defaultdict(Counter)
    for (uid, method), (record, reply) in probe.stage_receipts("Authority").items():
        card = by_uid[uid]
        counter = counts[card["benchmark"]]
        if not record or record["status"] != "OK":
            counter[method + "/nonusable_transport"] += 1
            continue
        try:
            if method == "FREE":
                free_view(reply)
                counter["FREE/valid"] += 1
            else:
                slots = task_frame(frame_by_sha[sha(frame_wire(card))][1])
                sources = {r["memory_id"]: r["text"] for r in card["root"]["original_sources"]}
                permissions = authorize(reply, slots, sources)
                counter["SHARED/valid"] += 1
                counter["SHARED/empty"] += not permissions
        except json.JSONDecodeError:
            counter[method + "/invalid_json"] += 1
        except TypeError:
            counter[method + "/invalid_type"] += 1
        except ValueError as error:
            counter[method + "/" + str(error)] += 1
    return counts


if __name__ == "__main__":
    cards = roster()
    results = {"physical_actor_wires": audit(probe.read(RUN / "Actor_MANIFEST.json"), cards),
               "physical_controller_receipts": audit_controllers(cards)}
    print(json.dumps(results, indent=2, sort_keys=True))
