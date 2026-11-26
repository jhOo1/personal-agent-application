"""Compare final regeneration with and without the original task-only draft."""
import argparse
import json

from freeze_draft_conditioning_panel import CONTROLS, HERE, build, read
from persist_grounding_gepa_wires import smoke
from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from trial_reassembly import engine, grading, probe

OUT = HERE / "persist_draft_visibility_v1"
RUN = engine.RUN.with_name(OUT.name)
PANEL = HERE / "DRAFT_CONDITIONING_PANEL.json"
ARMS = ("REVISE", "RESOLVE")
PROPOSE = (
    "Use the current task and the original memories to propose one concrete change to the draft "
    "that improves the actual deliverable. Consider necessary facts, applicable constraints, and "
    "helpful preferences. Respect who is affected and keep the requested goal. Name the replacement "
    "action and any decisions that must change with it. Do not copy the draft or restate it as a fact. "
    "Return JSON with action (a concrete proposal, or null if no justified improvement exists) "
    "and source_ids (the supporting original IDs, empty only if action is null)."
)
FINAL = (
    "Complete the current task in full. Treat the proposal as provisional. Check its assumptions "
    "against the original evidence and the current task. Do not output analysis, internal IDs or "
    "a patch. Return the complete deliverable."
)


def packet(wire, payload, system):
    return {**wire, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]}


def prepare():
    panel = read(PANEL)
    if panel != build():
        raise ValueError("Frozen panel drift")
    cases = {row["uid"]: row for row in read(CONTROLS / "PLAN.json")["cases"]}
    roster = {row["uid"]: row for row in panel["rows"]}
    actor = {}
    for wave in sorted((CONTROLS / "waves").glob("[0-9][0-9].json")):
        for row in read(wave)["rows"]:
            if row["uid"] in roster and row["method"] == "PB_RUBRIC" and row["actor_status"] == "OK":
                if row["uid"] in actor:
                    raise ValueError("Duplicate archived rubric endpoint")
                actor[row["uid"]] = row
    bridge = PersistAuthorBridge(smoke.UP)
    rubric = bridge.blobs["RUBRIC"].decode()
    samples = smoke.source()
    items = {}
    for uid, row in roster.items():
        public = smoke.public(samples[cases[uid]["line"] - 1])
        saved = actor[uid]
        wire = saved["actor_request"]
        if sha(public) != row["public_sha256"] or sha(wire) != row["actor_sha256"]["PB_RUBRIC"]:
            raise ValueError(f"Frozen input drift: {uid}")
        full = bridge.render(public["memories"], wire["model"], rubric)
        if wire["messages"] != [
            {"role": "system", "content": full},
            {"role": "user", "content": public["query"]},
        ]:
            raise ValueError(f"Saved rubric rendering drift: {uid}")
        draft = {**wire, "messages": [
            {"role": "system", "content": bridge.render([], wire["model"], rubric)},
            wire["messages"][1],
        ]}
        history = {f"M{i}": text for i, text in enumerate(public["memories"], 1)}
        items[uid] = (row, saved["score"], wire, draft, history)
    return items


def decode(answer, history):
    obj = json.loads(answer)
    action, ids = obj["action"], obj["source_ids"]
    if (not isinstance(ids, list) or not all(isinstance(x, str) and x in history for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Invalid source references")
    if action is None and not ids:
        return {"action": None, "source_ids": []}
    if not isinstance(action, str) or not action.strip() or not ids:
        raise ValueError("Expected a concrete sourced proposal or explicit abstention")
    return {"action": action, "source_ids": ids}


def run():
    items = prepare()
    n = len(items)
    caps = {"TaskDraft": n, "SharedAction": n, "FinalActor": 2*n, "PersistNative": 2*n}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([items, caps, source_sha256()])}
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        drafts = dispatch("TaskDraft", {(uid, "shared"): item[3] for uid, item in items.items()})
        failures, preparation = {}, {}
        for (uid, arm), reply in drafts.items():
            if reply["status"] != "OK":
                failures[uid] = reply["status"]
                continue
            _, _, wire, _, history = items[uid]
            preparation[uid, arm] = packet(wire, {
                "task": wire["messages"][1]["content"], "draft": reply["answer"], "history": history,
            }, PROPOSE)
        proposals = dispatch("SharedAction", preparation)
        final, actions = {}, {}
        for (uid, arm), reply in proposals.items():
            _, _, wire, _, history = items[uid]
            if reply["status"] != "OK":
                failures[uid] = reply["status"]
                continue
            try:
                actions[uid] = decode(reply["answer"], history)
            except (ValueError, KeyError, TypeError):
                failures[uid] = "INVALID_ACTION"
                continue
            payload = {"task": wire["messages"][1]["content"], "proposal": actions[uid]}
            system = wire["messages"][0]["content"] + "\n\n" + FINAL
            final[uid, "REVISE"] = packet(wire, {**payload, "draft": drafts[uid, arm]["answer"]}, system)
            final[uid, "RESOLVE"] = packet(wire, payload, system)
        answers = dispatch("FinalActor", final)
        rows = []
        for uid, (case, score, _, _, _) in items.items():
            for arm in ARMS:
                reply = answers.get((uid, arm), {})
                rows.append({"uid": uid, "method": arm, "benchmark": "PersistBench",
                             "category": case["category"], "group": case["group"],
                             "stratum": case["stratum"], "base_score": score, "score": None,
                             "answer": reply.get("answer"),
                             "actor_status": reply.get("status", failures.get(uid, "UNISSUED"))})
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger, "proposals": actions})


def source_sha256():
    return sha((HERE / "run_persist_draft_visibility.py").read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    if parser.parse_args().action == "check":
        print(f"Verified {len(prepare())} matched task-only draft inputs")
    else:
        run()
