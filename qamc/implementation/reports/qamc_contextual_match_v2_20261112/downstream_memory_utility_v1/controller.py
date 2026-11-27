"""Shared CAR controller contracts. Packets contain only visible task inputs."""
import json

from action_commit import Commit, parse_controller_json, submit


OPPORTUNITY = """Given the current task, original history and two complete proposal answers, identify at most one concrete and feasible change to the actual deliverable that the history supports. A proposal can preserve an applicable constraint, refine a decision, add an executable optional choice, or replace a real decision. It can also use less history when existing history steers the answer away from the task. It must improve the task for an identifiable party and preserve other applicable conditions, fact qualifiers, and the requested deliverable. The person who owns a preference can differ from who acts and who benefits. A current task may require using a history fact even without restating it. A soft preference may add value without controlling a shared decision. Neither answer is privileged. Do not invent a fact, requirement, commitment, person, or source.
Return JSON only. If there is no justified opportunity, return {"mode":"NO_INTERVENTION"}. Otherwise return {"mode":"PROPOSE","operation":"REFINE|REPLACE|ADD_OPTION","actor":"who carries it out","affected_party":"who it affects","change":"the real change","protect":"the most important existing requirement to preserve","evidence":[{"id":"original source ID","quote":"one exact contiguous quote carrying the necessary condition"}]}. Include only original sources needed to support the change. If the correction is to remove history influence, evidence can be empty; the current task must support the replacement. Do not return a complete answer."""

COMMON = """The current task, its facts, original history and all complete candidate answers are supplied. Use only relevant history. Preserve known facts and unknown qualifiers, the intended output, all legitimate restrictions, and applicable soft preferences. Do not turn personal choices into unattributed shared requirements. Compare what the candidates actually deliver. A claimed action in the proposal is not evidence that a candidate executes it. Choose the best deliverable grounded in the provided input. Respect the same fixed fallback and protected literals shown in the packet."""

FINAL = {
    "WHOLE": COMMON + """ Return only JSON {"mode":"SELECT","base":"candidate ID"}. Evaluate every available candidate. Use the fallback if none is clearly an improvement. Return the entire selected answer by ID.""",
    "FREE": COMMON + """ You can preserve, combine or rewrite candidates and may make local changes. If a complete candidate is already best, return only JSON {"mode":"SELECT","base":"candidate ID"}. Otherwise return only JSON {"mode":"REVISE","answer":"complete deliverable"}. Do not show your evaluation to the recipient.""",
    "COMMIT": COMMON + """ Select an existing complete answer or submit already written blocks of one donor to one different base. Do not write any new text. Include changes to all dependent parts of the actual task, such as invitations and timings linked to a venue. Every unchanged base block will remain verbatim. Use ordered zero-based half-open block ranges. Return only JSON {"mode":"SELECT","base":"candidate ID"} or {"mode":"COMMIT","base":"base ID","donor":"donor ID","replacements":[{"base":[1,3],"donor":[2,4]}]}. Empty base ranges insert existing donor blocks. Select a complete candidate if the actual change needs a whole-document rewrite or a coherent group of donor blocks cannot be found.""",
}


def opportunity(raw, source_text):
    proposed = parse_controller_json(raw)
    if proposed == {"mode": "NO_INTERVENTION"}:
        return None
    fields = {"mode", "operation", "actor", "affected_party", "change", "protect", "evidence"}
    if (not isinstance(proposed, dict) or proposed.keys() != fields or proposed["mode"] != "PROPOSE"
            or proposed["operation"] not in ("REFINE", "REPLACE", "ADD_OPTION")):
        raise ValueError("Invalid action proposal")
    for field in ("actor", "affected_party", "change", "protect"):
        value = proposed[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise ValueError("Invalid opportunity description")
    evidence = proposed["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("Expected source list")
    selected = set()
    for row in evidence:
        if not isinstance(row, dict) or row.keys() != {"id", "quote"}:
            raise ValueError("Malformed opportunity source")
        key, quote = row["id"], row["quote"]
        if (not isinstance(key, str) or key not in source_text or key in selected
                or not isinstance(quote, str) or not quote.strip() or quote not in source_text[key]):
            raise ValueError("Opportunity has no exact original evidence")
        selected.add(key)
    return proposed


def finalize(arm, raw, candidates, fallback, protected_literals=()):
    if arm not in FINAL:
        raise ValueError("Unknown CAR comparison arm")
    if arm == "COMMIT":
        return submit(raw, candidates, fallback, protected_literals)
    keep = submit(json.dumps({"mode": "SELECT", "base": fallback}), candidates, fallback, protected_literals)
    try:
        result = parse_controller_json(raw)
        if not isinstance(result, dict):
            raise ValueError("Expected final controller object")
        if result.get("mode") == "SELECT":
            return submit(raw, candidates, fallback, protected_literals)
        if (arm != "FREE" or result.keys() != {"mode", "answer"} or result["mode"] != "REVISE"
                or not isinstance(result["answer"], str) or not result["answer"].strip()
                or any(literal not in result["answer"] for literal in protected_literals)):
            raise ValueError("Control result violates the common contract")
        for name, blocks in candidates.items():
            if result["answer"] == "".join(blocks):
                return Commit(result["answer"], "SELECTED", name)
        return Commit(result["answer"], "REVISED", fallback)
    except (ValueError, TypeError):
        return Commit(keep.answer, "CONTRACT_FALLBACK", fallback)
