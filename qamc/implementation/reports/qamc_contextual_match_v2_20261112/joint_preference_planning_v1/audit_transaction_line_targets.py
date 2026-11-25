"""Test whether draft line addresses preserve existing committed patches."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_decision_transactions as run


def line_range(text, start, end):
    left = text.rfind("\n", 0, start) + 1
    newline = text.find("\n", end - 1)
    right = len(text) if newline < 0 else max(end, newline)
    if not left <= start < end <= right:
        raise ValueError("Patch does not lie in its draft line range")
    return left, right


def merge_addressed_patches(text, spans, report):
    ranges = []
    for left, right, decision, patch in sorted(spans, key=lambda span: (span[0], span[1])):
        if ranges and left < ranges[-1]["end"]:
            current = ranges[-1]
            if current["decision"] != decision:
                report["new_cross_decision_overlap"] += 1
                return None
            current["end"] = max(right, current["end"])
            current["patches"].append(patch)
        else:
            ranges.append({"start": left, "end": right, "decision": decision, "patches": [patch]})
    rebuilt = []
    for window in ranges:
        start, end = window["start"], window["end"]
        content = text[start:end]
        for patch in sorted(window["patches"], key=lambda item: item["start"], reverse=True):
            content = content[:patch["start"] - start] + patch["after"] + content[patch["end"] - start:]
        rebuilt.append({**window["patches"][0], "start": start, "end": end, "before": text[start:end], "after": content})
    return rebuilt


def audit(panel):
    _, _, roots, data, _ = run.prepare(panel)
    path = run.BASE_OUT / panel / "SETTLED.json"
    rows = run.read(path)["rows"]
    counts, mismatches = Counter(), []
    for row in rows:
        if run.method.ATOMIC not in row["outputs"]:
            continue
        uid = row["uid"]
        blocks = data[uid]["blocks"]
        units = {unit["index"]: unit for unit in row["units"]}
        intervals = defaultdict(list)
        counts["compiled"] += 1
        for trace in row["execution"][run.method.ATOMIC]["committed"]:
            unit = units[trace["decision"]]
            variant = next(v for v in unit["variants"] if v["index"] == trace["variant"])
            for edit in variant["patches"]:
                key = edit["block"], edit["line"]
                text = blocks[key[0]]["lines"][key[1]]
                left, right = line_range(text, edit["start"], edit["end"])
                intervals[key].append((left, right, unit["index"], edit))
                counts.update(committed_patches=1, original_write_chars=edit["end"] - edit["start"],
                              covered_line_chars=right - left)
                counts["unchanged_bounds"] += (left, right) == (edit["start"], edit["end"])
        patches = []
        for (block, line), spans in intervals.items():
            replaced = merge_addressed_patches(blocks[block]["lines"][line], spans, counts)
            if replaced is None:
                mismatches.append({"uid": uid, "reason": "NEW_CROSS_DECISION_OVERLAP"})
                break
            patches.extend(replaced)
        else:
            answer, _, failures = run.method.scoped.render(roots[uid], blocks, {}, patches, scope=False)
            if failures or answer != row["outputs"][run.method.ATOMIC]:
                mismatches.append({"uid": uid, "reason": "REBUILT_OUTPUT_DIFFERS"})
            else:
                counts["unchanged_compiled_answers"] += 1
    return {"counts": counts, "exceptions": mismatches, "settled_sha256": sha(path.read_bytes()),
            "new_requests": 0, "new_scores": 0}


if __name__ == "__main__":
    print(json.dumps({panel: audit(panel) for panel in ("smoke", "pilot")}, ensure_ascii=False, indent=2))
