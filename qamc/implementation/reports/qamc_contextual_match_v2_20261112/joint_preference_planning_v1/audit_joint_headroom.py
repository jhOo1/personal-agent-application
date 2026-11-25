"""Measure where the joint experiment loses Match and what its drafts add to the saved pool."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import audit_answer_pool as old
import run_joint_planning as joint
from settle_joint_planning import checked_settlement, subsets


def common_decomposition(rows, frozen):
    output = {}
    for name, panel in subsets(rows, frozen).items():
        details = {}
        for control in (old.GATE, old.RP, old.RULE):
            methods = (control, joint.MODEL, joint.SOLVED)
            totals, groups = Counter(), set()
            for row in panel:
                scores = [row["native"][m]["fields"].get("match") for m in methods]
                if any(score is None for score in scores):
                    continue
                if any(s["positions"] != row["positions"] for s in scores):
                    raise ValueError("Match positions differ across the three answers")
                totals["roots"] += 1
                totals["positions"] += row["positions"]
                totals.update({m: s["matched"] for m, s in zip(methods, scores, strict=True)})
                groups.add(row["group"])
            details[control] = {
                "counts": totals, "source_groups": len(groups),
                "model_plan_minus_archive": totals[joint.MODEL] - totals[control],
                "solver_minus_model_plan": totals[joint.SOLVED] - totals[joint.MODEL],
            }
        output[name] = details
    return output


def archived_text(root, row, original, v42, v43, neutral, chosen):
    answers = {m: root["archived"][m]["answer"] for m in (old.RP, old.GATE)}
    answers[old.ZERO] = neutral[root["task_wire_sha256"]]["answer"]
    answers[old.RULE] = answers[chosen]
    answers.update({m: row["edits"][m].get("answer") for m in old.r.edit.METHODS})
    answers.update({m: original["answers"][m]["answer"] for m in (old.REVIEW, "DELTA")})
    answers.update({m: v42["answers"][m]["answer"] for m in ("DIRECT_MASKED", "SCOPED_FULL", "SCOPED_MASKED")})
    answers["RP_POLICY_OVERRIDE"] = v43["answer"]
    return answers


def extend_pool(new_rows):
    local_path = old.r.OUT / "SETTLED.json"
    frozen_pool = joint.read(old.r.OUT / "ANSWER_POOL_AUDIT.json")
    if sha(local_path.read_bytes()) != frozen_pool["local_settlement_sha256"]:
        raise ValueError("The previous answer pool does not match its settled data")
    archive = joint.read(old.r.prior.OUT / "FROZEN.json")
    local = {row["uid"]: row for row in joint.read(local_path)["rows"]}
    roots = {root["uid"]: root for root in archive["roots"]}
    new = {row["uid"]: row for row in new_rows}
    if roots.keys() != local.keys() or roots.keys() != new.keys():
        raise ValueError("The answer pools differ in task roster")
    original, visibility, override = old.old_candidates(archive)
    neutral = old.r.task_only.saved_drafts(archive)
    totals, groups, improved = defaultdict(Counter), defaultdict(set), []
    for prior in frozen_pool["roots"]:
        uid, width = prior["uid"], prior["positions"]
        current, past = new[uid], local[uid]
        if any(current[k] != past[k] for k in ("group", "labels", "positions")) or width != current["positions"]:
            raise ValueError("Pool alignment does not preserve source and author positions")
        root = roots[uid]
        base = old.checked_scores(past["native"][old.RULE], width)
        if old.checked_scores(current["native"][old.RULE], width) != base or base[0] != prior["C_rule_match"]:
            raise ValueError("Protected-score floor differs")
        chosen = old.RP if any(row["policy"] == "C" for row in root["archived_policy"]) else old.ZERO
        texts = archived_text(root, past, original[uid], visibility[uid], override[uid], neutral, chosen)
        if sha(texts[old.RULE]) != prior["C_rule_answer_sha256"]:
            raise ValueError("Protected rule answer changed")
        seen = {sha(text) for text in texts.values() if text}
        saved = prior["pools"]["plus_previous_qamc_variants"]
        raw, protected = saved["unconstrained_max"], saved["protected_max"]
        valid, unique = 0, 0
        winner = None
        for method in (joint.MODEL, joint.SOLVED):
            answer = current["actors"][method].get("answer")
            score = old.checked_scores(current["native"][method], width)
            if not answer or not score:
                continue
            valid += 1
            digest = sha(answer)
            if digest in seen:
                continue
            seen.add(digest)
            unique += 1
            raw = max(raw, score[0])
            if score[0] > protected and all(b <= a for a, b in zip(base[1:], score[1:], strict=True)):
                protected, winner = score[0], method
        for name in prior["strata"]:
            groups[name].add(prior["group"])
            totals[name].update(
                roots=1, positions=width, previously_protected=saved["protected_max"], extended_protected=protected,
                previously_raw=saved["unconstrained_max"], extended_raw=raw,
                previously_complete=saved["unconstrained_max"] == width, extended_complete=raw == width,
                roots_with_new_score=bool(valid), new_unique_scored_answers=unique)
        if winner is not None:
            improved.append({"uid": uid, "group": prior["group"], "method": winner,
                             "previous": saved["protected_max"], "extended": protected})
    return {"strata": {name: {**values, "source_groups": len(groups[name])} for name, values in totals.items()},
            "improved_protected": improved,
            "definition": "Hindsight maximum on the same archive roster. New variants with identical answer text "
                          "do not add candidates. The protected maximum keeps OPB, UPB and FM at most the C-rule score."}


if __name__ == "__main__":
    plan, rows, _ = checked_settlement(joint.OUT, planner_key="planner_wires_sha256")
    report = {"common_match_decomposition": common_decomposition(rows, plan),
              "archived_answer_headroom": extend_pool(rows),
              "inputs_sha256": {
                  "joint_settlement": sha((joint.OUT / "SETTLED.json").read_bytes()),
                  "previous_answer_pool": sha((old.r.OUT / "ANSWER_POOL_AUDIT.json").read_bytes()),
              },
              "new_model_calls": 0, "new_native_scores": 0}
    print(json.dumps(report, ensure_ascii=False, indent=2))
