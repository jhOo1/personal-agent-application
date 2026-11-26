"""Report ranking and retention effects after the local selection outputs are frozen."""
import argparse
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path

from qamc.pa.core import digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORMAL = HERE.parent / "rpeval_formal_multi_coverage_v1"
RUN = ROOT / "runs" / HERE.parent.name / HERE.name
MODES = ("threshold", "matched_zh_count", "matched_en_count")


def read(path):
    return json.loads(path.read_text())


def deltas(zh, en, labels):
    events = Counter()
    for i, label in enumerate(labels):
        key = f"M{i}"
        events[label + "_available"] += 1
        events.update({
            label + "_old": key in zh, label + "_new": key in en,
            label + "_dropped": key in zh - en, label + "_added": key in en - zh,
        })
    return events


def separation(scores, labels, positive):
    relevant = [scores[i] for i, label in enumerate(labels) if label in positive]
    irrelevant = [scores[i] for i, label in enumerate(labels) if label == "A"]
    pairs = list(product(relevant, irrelevant))
    if not pairs:
        return None
    return sum(1 if a > b else 0.5 if a == b else 0 for a, b in pairs) / len(pairs)


def report(run=RUN):
    result = read(run / "RESULTS.json")
    frozen = read(run / "FROZEN.json")
    manifest = {r["uid"]: r for r in read(FORMAL / "MANIFEST_300.json") if r["uid"] in frozen["uids"]}
    if set(frozen["uids"]) != result.keys() or result.keys() != manifest.keys():
        raise ValueError("Missing frozen diagnostic task")
    summary = {
        "cloud_requests": 0,
        "allocated_tasks": len(result) + len(frozen.get("missing_contract", {})),
        "unavailable_original_contracts": len(frozen.get("missing_contract", {})),
        "statuses": Counter(row["status"] for row in result.values()),
        "assets": frozen["translation_assets"],
        "effects": defaultdict(Counter),
        "by_label": defaultdict(Counter),
        "local_translation": Counter(),
        "macro_within_task_auc": {},
    }
    aucs = defaultdict(list)
    for uid, row in result.items():
        if row["status"] != "OK":
            continue
        case = manifest[uid]
        if case["independent_confirmation"]:
            raise ValueError("Unexpected confirmation reference")
        ref = read(ROOT / case["evaluation_path"])
        labels = ref["intent_type"]
        if digest(ref) != case["evaluation_hash"] or len(labels) != row["candidates"] or set(labels) - set("ABC"):
            raise ValueError("Mismatch in original candidate labels")
        zh, en = (row["modes"][language] for language in ("ZH", "EN"))
        for mode in MODES:
            old, new = set(zh[mode]), set(en[mode])
            if mode != "threshold" and len(old) != len(new):
                raise ValueError("Amount-matched comparison changed retention count")
            summary["effects"][mode].update(
                tasks=1, selected_zh=len(old), selected_en=len(new), membership_changed=old != new,
                interior_zh=0 < len(old) < len(labels), interior_en=0 < len(new) < len(labels),
                common_ids=len(old & new), swapped_out=len(old - new), swapped_in=len(new - old),
            )
            summary["by_label"][mode].update(deltas(old, new, labels))
        for tag, positives in (("BC_vs_A", "BC"), ("C_vs_A", "C"), ("B_vs_A", "B")):
            for language, mode in (("ZH", zh), ("EN", en)):
                auc = separation(mode["scores"], labels, positives)
                if auc is not None:
                    aucs[tag, language].append(auc)
        summary["local_translation"].update(row["accounting"])
    summary["macro_within_task_auc"] = {
        f"{tag}/{language}": {"roots": len(values), "macro": round(sum(values) / len(values), 6)}
        for (tag, language), values in aucs.items()
    }
    return summary


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--wide", action="store_true")
    run = RUN.with_name("rpe_memgate_language_wide_v1") if cli.parse_args().wide else RUN
    print(json.dumps(report(run), sort_keys=True, indent=2))
