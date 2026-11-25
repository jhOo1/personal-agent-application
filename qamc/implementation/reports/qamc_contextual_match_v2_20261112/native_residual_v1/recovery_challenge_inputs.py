"""Verify task-only anchors and expose identical candidate inputs to both arms."""
from freeze_recovery_challenge import OUT, build
from incremental_panel import prior, read, sha, saved_drafts
from freeze_roster import RPE_ROUTES


def prepare():
    panel = read(OUT)
    if panel != build():
        raise ValueError("Frozen challenge drift")
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Challenge requires exposed development cases")
    roots = {row["uid"]: row for row in frozen["roots"]}
    controls = {row["uid"]: row for row in read(RPE_ROUTES)["rows"]}
    drafts = saved_drafts(frozen)
    inputs = {}
    for entry in panel:
        uid = entry["uid"]
        root, control = roots[uid], controls[uid]
        digest = sha(v41.task_only_request(root))
        anchor = control["no_history_state"]["answer"]
        grade = control["controls"]["TASK_ONLY"]
        sources = {row["memory_id"]: row["text"] for row in root["original_sources"]}
        if (digest != root["task_wire_sha256"] or anchor != drafts[digest]["answer"]
                or grade["answer_sha256"] != sha(anchor.strip())
                or grade["grade"] != control["ipe_c"]["grade"]
                or len(sources) != len(root["original_sources"])):
            raise ValueError("Challenge baseline or sources drifted")
        inputs[uid] = {"task": root["public_task"], "anchor": anchor, "sources": sources}
    return inputs


if __name__ == "__main__":
    cases = prepare()
    print(len(cases), "verified anchors;", sum(len(row["sources"]) for row in cases.values()), "sources")
