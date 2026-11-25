"""Build the exact matched incremental-value requests for exposed pairs."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "source_local_reentry_v1"
sys.path.insert(0, str(LOCAL))

from freeze_probe import CONTROL, build
from incremental_decision import selector_messages
from run_probe import actor_wire, index, prior, read, saved_drafts, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate


def prepare():
    frozen = read(LOCAL / "FROZEN_ESTIMATES.json")
    if frozen != build():
        raise ValueError("Original comparison plan drift")
    v41 = prior.R["archived"].v41
    old = read(v41.OUT / "FROZEN.json")
    if old["independent_confirmation"]:
        raise ValueError("Expected exposed development cases")
    roots, drafts = index(old["roots"]), saved_drafts(old)
    archived = {r["uid"]: r for pair in read(LOCAL / "ELIGIBILITY.json")["pairs"]
                for r in pair["endpoints"]}
    jobs, cards = {}, {}
    for row in frozen["native_arms"]:
        uid = row["uid"]
        root = roots[uid]
        digest = row["task_only_actor_sha256"]
        card = archived[uid]["methods"]["TASK_ONLY"]
        if sha(v41.task_only_request(root)) != digest or drafts[digest]["answer"] != card["answer"]:
            raise ValueError("Task-only archive drift")
        originals = {source["memory_id"]: source["text"] for source in root["original_sources"]}
        sources = {target["id"]: originals[target["id"]] for target in row["target_jobs"]}
        for target in row["target_jobs"]:
            if sha(sources[target["id"]]) != target["text_sha256"]:
                raise ValueError("Candidate text drift")
            actor_wire(root, target["id"])
        cards[uid] = {"root": root, "base": card, "group": row["group"], "sources": sources}
        if not sources:
            continue
        template = row["target_jobs"][0]["requests"][CONTROL]
        for arm in ("ordinary", "incremental"):
            request = {**template, "messages": selector_messages(
                canonical(root["public_task"]), card["answer"], sources, incremental=arm == "incremental")}
            validate_public_request(request)
            if token_estimate(canonical(request["messages"])) > 32768:
                raise ValueError("Selector exceeds capacity")
            jobs[uid, arm] = request
        if jobs[uid, "ordinary"]["messages"][1] != jobs[uid, "incremental"]["messages"][1]:
            raise ValueError("Selector data differ across arms")
    return jobs, cards


if __name__ == "__main__":
    jobs, cards = prepare()
    print(f"{len(cards)} exposed tasks, {len(jobs)} matched selector requests")
