"""Build initial optimization feedback only from the frozen search panel."""
from build_jobs import archive_inputs
from freeze_feedback_panel import PATH, archive
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from summarize_reassembly import measure

PARENT = (
    "Preserve current task requirements and use past preferences only within their applicable scope.",
)


def excerpt(text, limit):
    if len(text) <= limit:
        return text
    edge = limit // 2
    return text[:edge] + "\n[Middle omitted for feedback capacity]\n" + text[-edge:]


def initial_feedback():
    wires, cards = archive_inputs()
    entries = archive.read(PATH)["rows"]
    search = [row for row in entries if row["split"] == "search"]
    if len(search) != 12:
        raise ValueError("Unexpected search allocation")
    traces = []
    for row in search:
        key = row["benchmark"], row["uid"]
        original, card = wires[key], cards[key]
        wire = original["actor_request"]
        if (sha(wire) != row["actor_sha256"] or sha(card["base_answer"]) != row["answer_sha256"]
                or sha(card["base_score"]) != row["grade_sha256"]):
            raise ValueError("Archived search trace drift")
        traces.append({
            "benchmark": key[0],
            "role": row["role"],
            "actor_message_excerpts": [
                {"role": message["role"], "content": excerpt(message["content"], 1400)}
                for message in wire["messages"]
            ],
            "actor_answer_excerpt": excerpt(card["base_answer"], 1400),
            "observed_metrics": measure(key[0], row["stratum"], card["base_score"]),
        })
    # Keep both roles from each benchmark. Excerpts disclose omitted text.
    traces.sort(key=lambda t: token_estimate(canonical(t)))
    first = {}
    for trace in traces:
        first.setdefault((trace["benchmark"], trace["role"]), trace)
    used = list(first.values())
    if token_estimate(canonical(used)) > 26000:
        raise ValueError("Minimum balanced feedback exceeds capacity")
    for trace in traces:
        if trace not in used and token_estimate(canonical([*used, trace])) <= 26000:
            used.append(trace)
    if {(t["benchmark"], t["role"]) for t in used} != {
        (t["benchmark"], t["role"]) for t in traces
    }:
        raise ValueError("Feedback capacity excludes a benchmark or trace role")
    reference = wires[search[0]["benchmark"], search[0]["uid"]]["actor_request"]
    return PARENT, used, reference
