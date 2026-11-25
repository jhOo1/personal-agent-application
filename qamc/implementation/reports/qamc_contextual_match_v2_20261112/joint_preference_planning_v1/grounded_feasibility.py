"""Replay one candidate judgement as direct, status-routed, or evidence-routed output."""
import json

import beneficiary_ranking as rank


DIRECT, STATUS, ANCHORED, DRAFT = "MODEL_PLACEMENT", "STATUS_MATRIX", "GROUNDED_MATRIX", rank.DRAFT
MODES = (DIRECT, STATUS, ANCHORED, DRAFT)
KINDS = ("DIRECT", "CHECK", "OMIT")
MARKS = ("SUPPORTED", "CONFLICT", "UNKNOWN")
PROMPT = rank.HISTORY_PROMPT + """

Amend the required JSON schema for each emitted decision row with one extra field named feasibility.
If guard is null, feasibility is null. Otherwise use:
{"conditions":["specific property to verify for guard source 1"],
 "candidates":[{"option":"O1","disposition":"DIRECT","checks":[
 {"condition":1,"status":"SUPPORTED","location":"OPTION","quote":"exact phrase"}]}]}.
Each guard source quote should express one independently checkable condition. Conditions is an ordered list
of concise properties, one per guard.sources entry, in the language of the correct answer (e.g., "酱汁和配料无乳制品").
State the known requirement. Do not phrase the property as asking whether an explicitly stated requirement applies.
Candidates lists all original options O1,... and any guard replacements G1,... in their exact stored order.
For each, give your best disposition DIRECT for suitable recommendations, CHECK for conditional candidates,
OMIT for unsuitable candidates. This is your overall judgement. Also compare each candidate to EVERY condition.
SUPPORTED means the candidate explicitly implements the property by design or the CURRENT task facts establish it.
CONFLICT means the candidate or task explicitly contradicts it. For either, quote the actual relevant words from
the option's own text (location OPTION) or the current task/context/facts (location TASK). A memory defining the
condition does not prove a business, venue, ingredient or product meets it. A label such as 'suitable' or
'alternative' proves nothing. Verify the property itself. If the property depends on missing world facts,
use UNKNOWN with location null and quote null. Do not infer that a restaurant stock, opening hours, noise,
or an ingredient is verified. Review the effect on the actual affected people. Report each condition index
exactly once per option. Do not offer new options except documented constraint repairs. Return JSON only.
The extra feasibility field replaces no field in the required schema.
"""


def request(root, blocks):
    wire = rank.history_request(root, blocks)
    wire["messages"][0]["content"] = PROMPT
    return wire


def read_matrix(root, blocks, raw):
    value = rank.model_object(raw, "decisions")
    if set(value) != {"decisions"} or not isinstance(value["decisions"], list) or len(value["decisions"]) > 10:
        raise ValueError("Invalid decision list")
    records, common, shape = {}, [], []
    for row in value["decisions"]:
        keys = {"block", "guard", "preferences", "feasibility"}
        if not isinstance(row, dict) or set(row) != keys or not isinstance(row["block"], str):
            shape.append("FOREIGN_ROW")
            continue
        slot = row["block"]
        if slot in records:
            shape.append("DUPLICATE_MATRIX")
            continue
        records[slot] = row["feasibility"]
        common.append({k: v for k, v in row.items() if k != "feasibility"})
    choices = {slot: block for slot, block in blocks.items() if block["kind"] == "CHOICE"}
    policy, rejected = rank.read_policy(root, choices, json.dumps({"decisions": common}, ensure_ascii=False))
    programs = {}
    for slot, decision in policy.items():
        guard, matrix = decision["guard"], records[slot]
        if guard is None:
            continue
        n = len(guard["sources"])
        if (not isinstance(matrix, dict) or set(matrix) != {"conditions", "candidates"}
                or not isinstance(matrix["conditions"], list) or len(matrix["conditions"]) != n
                or not all(rank.planning.text(x, 220) for x in matrix["conditions"])
                or not isinstance(matrix["candidates"], list) or len(matrix["candidates"]) > 12):
            shape.append("INVALID_MATRIX")
            continue
        options = {f"O{i}": text for i, text in enumerate(choices[slot]["lines"], 1)}
        options.update({f"G{i}": text for i, text in enumerate(guard["replacements"], 1)})
        entries = {}
        for item in matrix["candidates"]:
            if (not isinstance(item, dict) or set(item) != {"option", "disposition", "checks"}
                    or not isinstance(item["option"], str) or item["option"] not in options
                    or item["option"] in entries or item["disposition"] not in KINDS
                    or not isinstance(item["checks"], list) or len(item["checks"]) > n):
                shape.append("INVALID_CANDIDATE")
                continue
            by_condition = {}
            for check in item["checks"]:
                if (not isinstance(check, dict) or set(check) != {"condition", "status", "location", "quote"}
                        or type(check["condition"]) is not int or not 1 <= check["condition"] <= n
                        or check["condition"] in by_condition or check["status"] not in MARKS):
                    shape.append("INVALID_CHECK")
                    continue
                idx = check["condition"]
                fields = (options[item["option"]],) if check["location"] == "OPTION" else (
                    tuple(rank.draft.task_text(root["public_task"])) if check["location"] == "TASK" else ())
                quoted = rank.planning.text(check["quote"], 420) and any(check["quote"] in x for x in fields)
                by_condition[idx] = {"predicted": check["status"], "exact_witness": quoted,
                                     "location": check["location"], "quote": check["quote"]}
            entries[item["option"]] = {"disposition": item["disposition"], "checks": by_condition}
        programs[slot] = {"conditions": matrix["conditions"], "entries": entries}
    return policy, programs, rejected + shape


def placement(entry, n, mode):
    original = entry["disposition"]
    raw = [entry["checks"].get(i, {}) for i in range(1, n + 1)]
    marks = [check.get("predicted", "UNKNOWN")
             if mode != ANCHORED or check.get("exact_witness") else "UNKNOWN" for check in raw]
    unresolved = [i for i, mark in enumerate(marks) if mark != "SUPPORTED"]
    if mode == DIRECT:
        return original, unresolved
    if original == "OMIT" or "CONFLICT" in marks:
        return "OMIT", unresolved
    return ("CHECK" if unresolved else original), unresolved


def render(root, blocks, policy, programs, mode):
    answer, trace = [], {}
    query = root["public_task"]["query"]
    chinese = any("\u3400" <= char <= "\u9fff" for char in query)
    for slot, block in blocks.items():
        if block["kind"] == "CONTENT":
            answer.extend(block["lines"])
            continue
        decision = policy.get(slot, {})
        guard = decision.get("guard")
        if mode == DRAFT or not guard:
            lines, log = rank.emit_choice(query, block, decision, rank.DRAFT if mode == DRAFT else rank.GENERIC)
            answer.extend(lines)
            trace[slot] = log
            continue
        options = {f"O{i}": text for i, text in enumerate(block["lines"], 1)}
        options.update({f"G{i}": text for i, text in enumerate(guard["replacements"], 1)})
        # Build the complete common ranking before applying a shared output limit.
        whole = {**block, "display": len(options)}
        _, ranked = rank.emit_choice(query, whole, decision, rank.GENERIC)
        matrix = programs.get(slot, {})
        checks, candidates = matrix.get("conditions", []), matrix.get("entries", {})
        if not checks:
            lines, log = rank.emit_choice(query, block, decision, rank.GENERIC)
            answer.extend(lines)
            trace[slot] = {**log, "matrix_status": "UNAVAILABLE"}
            continue
        routed = {"DIRECT": [], "CHECK": [], "OMIT": []}
        points = {}
        for option_id in ranked["shown"]:
            entry = candidates.get(option_id)
            if entry is None:
                entry = {"disposition": "DIRECT", "checks": {}}
            kind, unresolved = placement(entry, len(checks), mode)
            routed[kind].append(option_id)
            points[option_id] = unresolved
        shown = (routed["DIRECT"] + routed["CHECK"])[:block["display"]]
        for i, option_id in enumerate(shown, 1):
            text = options[option_id]
            if option_id in routed["CHECK"]:
                properties = [checks[j] for j in points[option_id]] or checks
                joined = ("、" if chinese else ", ").join(properties)
                text = (f"待核实（{joined}）后再考虑：{text}" if chinese else
                        f"Consider only after verifying {joined}: {text}")
            answer.append(f"{i}. {text}" if len(shown) > 1 else text)
        if not shown:
            answer.append("现有候选都不符合要求，需要另找满足条件的选项。" if chinese else
                          "The available candidates do not meet the requirements. A suitable alternative is needed.")
        trace[slot] = {"shown": shown, "routed": routed, "unresolved": points,
                       "excluded": ranked["excluded"], "matrix_status": "AVAILABLE"}
    return {"answer": "\n\n".join(answer), "decisions": trace}
