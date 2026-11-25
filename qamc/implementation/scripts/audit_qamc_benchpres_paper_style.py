"""Replay attribute-only scores and literal diagnostics for filtered paper inputs."""
from collections import Counter
import json
import re

from markdown_it import MarkdownIt

from audit_qamc_benchpres_bold_sensitivity import visible_strong
from audit_qamc_benchpres_paper_prompt_bridge import NICKNAME, attribute_labels
import run_qamc_benchpres_paper_style as trial


def audit(plan, candidate, original):
    parser = MarkdownIt("commonmark")
    methods = (trial.PAPER, trial.METHOD)
    by_case = {(r["uid"], method): r for method, rows in zip(methods, (original, candidate), strict=True)
               for r in rows}
    totals = {method: Counter() for method in methods}
    positions, missing = [], []
    for case in plan["cases"]:
        uid = case["uid"]
        rows = {method: by_case[uid, method] for method in methods}
        labels = {method: attribute_labels(r) for method, r in rows.items()}
        if any(label is None for label in labels.values()):
            missing.append({"uid": uid, "row_index": case["row_index"],
                            "methods": [m for m, values in labels.items() if values is None]})
            continue
        ref = trial.read(trial.ROOT / case["evaluation_path"])
        assert trial.paper.bench.digest(ref) == case["evaluation_hash"]
        for i, (attribute, appropriate) in enumerate(zip(
            ref["preference_attribute"], ref["preference_label"], strict=True
        )):
            nick = NICKNAME.search(attribute)
            bold = "bold text" in attribute.casefold()
            kind = "nickname" if nick else "bold" if bold else "other"
            row = {"uid": uid, "row_index": case["row_index"], "attribute": attribute,
                   "appropriate": appropriate, "kind": kind, "results": {}}
            for method, judgments in labels.items():
                answer = rows[method]["answer"]
                followed = judgments[i] == "follow"
                diag = None
                if nick:
                    diag = bool(re.search(rf"(?<!\w){re.escape(nick.group(1))}(?!\w)", answer))
                elif bold:
                    diag = visible_strong(answer, parser)
                prefix = "aar" if appropriate else "mr"
                for key in (prefix, f"{prefix}_{kind}"):
                    totals[method][key + "_n"] += followed
                    totals[method][key + "_d"] += 1
                row["results"][method] = {"followed": followed, "literal_or_rendered": diag}
            positions.append(row)
    return {"totals": totals, "positions": positions, "missing": missing, "model_calls": 0}


if __name__ == "__main__":
    plan = trial.read(trial.OUT / "PLAN.json")
    trial.check(plan)
    args = (trial.read(folder / "PILOT.json")["rows"] for folder in (trial.OUT, trial.PARENT))
    print(json.dumps(audit(plan, *args), ensure_ascii=False, indent=2))
