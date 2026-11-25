"""Deterministic paired policy proposals and conservative search selection."""
from residual import atomic, policy
from summarize_reassembly import aligned, measure

FOCUS = (
    "Use personal preferences to refine choices for the person who holds them; "
    "for a shared decision, preserve viable options unless the task supports narrowing them.",
    "Fulfill every requested action and preserve all necessary facts when applying style preferences; "
    "use concise wording only after the deliverable is complete.",
)
SUPPORT = (
    "Treat a preference as optional unless the current task makes it a requirement; "
    "preserve explicit constraints and the requested deliverable.",
    "Separate factual justification from the user's beliefs; "
    "use useful personal context without generalizing it to others.",
)


def proposal(parent, mode, step):
    """One controlled rule change or one whole-block replacement."""
    parent = policy(parent)
    focus = FOCUS[step]
    if mode == "atomic":
        return atomic(parent, "ADD", len(parent), focus)
    if mode == "block":
        return policy((focus, SUPPORT[step]))
    raise ValueError("Unknown mutation mode")


def choose(parent, trial, baseline):
    """Promote a complete, non-regressing candidate with a strict primary gain."""
    if len(trial) != len(baseline) or len(parent) != len(baseline):
        raise ValueError("Candidate and references must cover the full frozen panel")
    primary = 0
    seen = set()
    for row in trial:
        benchmark, uid, stratum = row["benchmark"], row["uid"], row["stratum"]
        key = benchmark, uid
        if key in seen:
            raise ValueError("Duplicate task in candidate")
        seen.add(key)
        base = baseline[key]
        old = parent[key]
        cells = {"base": measure(benchmark, stratum, base["base_score"]),
                 "parent": measure(benchmark, stratum, old["score"]),
                 "trial": measure(benchmark, stratum, row["score"])}
        if not aligned(cells, ("base", "parent", "trial")):
            return False
        score = cells["trial"]
        for reference in (cells["base"], cells["parent"]):
            if any(score[k] > reference[k] for k in ("OPB", "UPB", "FM", "MR") if k in score):
                return False
            if any(score[k] < reference[k] for k in ("primary", "completeness", "nonbold",
                                                     "strict_pass") if k in score):
                return False
        primary += score["primary"] - cells["parent"]["primary"]
    return primary > 0
