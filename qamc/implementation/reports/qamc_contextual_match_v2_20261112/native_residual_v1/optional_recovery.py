"""Compile a conditional option without turning a soft preference into a default."""
from copy import deepcopy
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import parse_object
from scope_contract import cited_span

PROMPT = """Find at most one omitted historical preference with concrete optional value
for a current decision. Use only the given task, plan, and omitted history.
Return {} if there is no justified option. Never infer that a different person
shares the historical preference. Return JSON with decision (a plan decision ID),
evidence and owner (each an exact source/quote object from the same history item),
and applicability (TASK_SUPPORTED or RECIPIENT_INTEREST_UNKNOWN). Only choose
RECIPIENT_INTEREST_UNKNOWN when the option can be offered conditionally without
attributing the preference to the recipient. Do not add requirements."""


def omitted_history(guidance, memory_sources):
    bound = {item["source"] for item in guidance["preferences"]}
    return {key: text for key, text in memory_sources.items() if key not in bound}


def proposal_wire(wire, task_sources, memory_sources, guidance):
    omitted = omitted_history(guidance, memory_sources)
    if not omitted or not guidance["decisions"]:
        return None
    payload = {"task": task_sources, "decisions": guidance["decisions"], "omitted": omitted}
    result = {**wire, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]}
    validate_public_request(result)
    return result


def compile_option(answer, guidance, memory_sources):
    candidate = parse_object(answer)
    if candidate == {}:
        return None
    if set(candidate) != {"decision", "evidence", "owner", "applicability"}:
        raise ValueError("Unexpected option fields")
    if candidate["decision"] not in guidance["decisions"]:
        raise ValueError("Option must target an already grounded decision")
    omitted = omitted_history(guidance, memory_sources)
    evidence = cited_span(omitted, candidate["evidence"])
    owner = cited_span(omitted, candidate["owner"])
    if evidence["source"] != owner["source"]:
        raise ValueError("Owner must be grounded in the preference source")
    if candidate["applicability"] not in ("TASK_SUPPORTED", "RECIPIENT_INTEREST_UNKNOWN"):
        raise ValueError("Invalid applicability")
    return {**candidate, "evidence": evidence, "owner": owner}


def render_recovery(wire, guidance, option, *, conditional):
    if option is None:
        return wire
    result = deepcopy(wire)
    system, = [message for message in result["messages"] if message["role"] == "system"]
    target = guidance["decisions"][option["decision"]]["quote"]
    body = {"evidence": option["evidence"]["quote"], "owner_evidence": option["owner"]["quote"],
            "decision": target, "applicability": option["applicability"]}
    directive = (
        "Offer this only as an optional alternative when suitable. If recipient interest is "
        "unknown, make the option explicitly conditional. Do not change the shared default."
        if conditional else
        "Consider the evidence for the stated decision, preserving the task's requirements."
    )
    system["content"] += "\n\n" + directive + "\n" + json.dumps(body, ensure_ascii=False)
    return result
