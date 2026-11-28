"""Audit candidate visibility from saved requests without model calls."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def require(ok, description):
    if not ok:
        raise ValueError(description)


def registered(run, stage):
    units = read(run / "private" / f"{stage}_MANIFEST.json")["units"]
    requests = {(row["unit"]["root_id"], row["unit"]["method"]): row["request"] for row in units}
    require(len(requests) == len(units), f"Duplicate logical unit in {stage}")
    return requests


def body(request):
    return json.loads(request["messages"][1]["content"])


def text_fields(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for entry in value:
            yield from text_fields(entry)
    elif isinstance(value, dict):
        for entry in value.values():
            yield from text_fields(entry)


def request_shell(request):
    return ({key: value for key, value in request.items() if key != "messages"},
            request["messages"][0])


def audit(run):
    review = registered(run, "CandidateReview")
    actors = registered(run, "FusionActor")
    counts = Counter()
    for uid, kind in review:
        original = body(review[uid, kind])
        direct = actors[uid, "DIRECT_FUSION"]
        unmasked = actors.get((uid, "REVIEW_FUSION"))
        masked = actors.get((uid, "QUARANTINED_FUSION"))
        require(body(direct) == {**original, "rejected": []}, "Direct input diverged from reviewer input")
        counts["reviewed_roots"] += 1
        if unmasked is None:
            require(masked is None, "Masked generation registered without its matched control")
            counts["no_separate_unmasked_wire"] += 1
            continue
        values = body(unmasked)
        rejected = values["rejected"]
        blocks = [block for draft in original["candidates"] for block in draft["blocks"]]
        require(len(set(rejected)) == len(rejected) and set(rejected) <= {b["id"] for b in blocks},
                "Reviewer produced invalid rejection IDs")
        require(values == {**original, "rejected": rejected}, "Unmasked actor input adds unintended data")
        require(request_shell(direct) == request_shell(unmasked), "Direct and reviewed actor settings differ")
        if not rejected:
            require(masked is None, "Empty rejection unexpectedly launched a separate masked request")
            counts["empty_reviews_with_distinct_direct_wire"] += direct != unmasked
            counts["empty_reviews"] += 1
            continue
        require(masked is not None, "Missing registered intervention")
        expected = [{**draft, "blocks": [
            {**block, "text": "[WITHHELD CANDIDATE BLOCK]"} if block["id"] in rejected else block
            for block in draft["blocks"]]} for draft in values["candidates"]]
        require(body(masked) == {**values, "candidates": expected}, "Masked actor changed other input")
        require(list(body(masked)) == list(values), "Paired intervention changed payload key order")
        require(request_shell(masked) == request_shell(unmasked), "Paired actor settings differ")
        counts["activated_roots"] += 1
        counts["masked_blocks"] += len(rejected)
        subjects = [block["text"].strip() for block in blocks if block["id"] in rejected]
        input_text = list(text_fields({"task": original["task"], "source_evidence": original["source_evidence"]}))
        kept_blocks = [block["text"] for block in blocks if block["id"] not in rejected]
        counts["roots_with_exact_masked_text_in_original_inputs"] += any(
            fragment and fragment in surface for fragment in subjects for surface in input_text)
        counts["roots_with_exact_masked_text_in_kept_draft_blocks"] += any(
            fragment and fragment in surface for fragment in subjects for surface in kept_blocks)
    return {"registered_fusion_wires": len(actors), "visibility": dict(counts)}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run), indent=2))


if __name__ == "__main__":
    main()
