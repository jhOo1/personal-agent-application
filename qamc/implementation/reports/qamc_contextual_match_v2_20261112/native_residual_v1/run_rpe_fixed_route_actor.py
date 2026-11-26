"""Test a second Actor while retaining the original IPE-C decision and wire."""
from collections import Counter
import json
from pathlib import Path

from incremental_panel import HERE, prior, read, sha
from replay_ipe_c_des2gen import HISTORY, TASK_ONLY
from run_probe import engine, probe

OUT = HERE / "rpe_fixed_route_actor_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "FixedRouteActor"
METHOD = "IPE_C_GPT41_ACTOR"
MODEL = "gpt-4.1"
PANEL = HERE / "RPE_FIXED_ROUTE_ACTOR_PANEL.json"
QUOTAS = {"history_B": 6, "history_C": 8, "task_all_A": 6}


def prepare():
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Only exposed development data are allowed")
    roots = {r["uid"]: r for r in frozen["roots"]}
    archive = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
               if r["method"] == "RPR_PAPER_FULL"}
    previous = read(HERE.parent / "ipe_c_second_backbone_v1" / "FROZEN.json")
    prior_groups = {card["source_group"] for card in previous["cards"]}
    prior_uids = {card["uid"] for card in previous["cards"]}
    old = read(HERE.parent / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]
    task_only_hashes = {row["uid"]: row.get("task_only_request_sha256") for row in
                        read(HERE.parent / "ipe_c_full_exposed_panel_v1" / "RESULTS.json")["rows"]}
    candidates = {key: [] for key in QUOTAS}
    for row in old:
        uid, route, labels = row["uid"], row["old_route"], row["labels"]
        if not labels or uid in prior_uids or not row["ipe_c"].get("grade", {}).get("match"):
            continue
        if route == HISTORY and "C" in labels:
            key = "history_C"
        elif route == HISTORY and "B" in labels:
            key = "history_B"
        elif route in TASK_ONLY and set(labels) == {"A"}:
            key = "task_all_A"
        else:
            continue
        actual = archive.get(uid)
        if actual is None or actual["actor_status"] != "OK":
            continue
        wire = actual["actor_request"]
        if sha(wire) != actual["actor_request_sha256"]:
            raise ValueError(f"Archived RP wire differs: {uid}")
        if uid not in roots:
            packet = json.loads(wire["messages"][1]["content"])
            sources = packet.pop("source_evidence")
            policies = packet.pop("preference_use_policy")
            roots[uid] = {"archived_actor_request": wire, "archived_actor_sha256": sha(wire),
                          "public_task": packet, "original_sources": sources,
                          "archived_policy": policies, "archived": {}}
        if route == HISTORY:
            if sha(actual["answer"].strip()) != row["ipe_c"]["answer_sha256"]:
                raise ValueError(f"Archived RP endpoint differs: {uid}")
        else:
            wire = v41.task_only_request(roots[uid])
            if sha(wire) != task_only_hashes[uid]:
                continue
        if wire["model"] != "qwen3.8-flash":
            raise ValueError(f"Unexpected base Actor alias: {uid}")
        candidates[key].append((row, wire))

    panel, jobs, used = [], {}, set()
    for stratum, quota in QUOTAS.items():
        n = 0
        for row, wire in sorted(candidates[stratum], key=lambda item: (item[0]["source_group"] in prior_groups, sha(
                ["fixed-route-actor-v1", item[0]["source_group"], item[0]["uid"]]))):
            group, uid = row["source_group"], row["uid"]
            if group in used:
                continue
            used.add(group)
            panel.append({"uid": uid, "source_group": group, "stratum": stratum,
                          "old_route": row["old_route"], "prior_backbone_group": group in prior_groups,
                          "qwen_request_sha256": sha(wire),
                          "qwen_answer_sha256": row["ipe_c"]["answer_sha256"],
                          "base_grade": row["ipe_c"]["grade"]})
            jobs[uid, METHOD] = {**wire, "model": MODEL}
            n += 1
            if n == quota:
                break
    if len(panel) != sum(QUOTAS.values()):
        raise ValueError(f"Insufficient groups: {Counter(row['stratum'] for row in panel)}")
    return {"cases": panel, "quota": QUOTAS, "prior_panel_sha256": sha(previous)}, jobs, roots


def run():
    panel, jobs, roots = prepare()
    if panel != read(PANEL):
        raise ValueError("Frozen panel drift")
    caps = {STAGE: len(jobs), engine.RPE: len(jobs)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([panel, [[uid, sha(wire)] for (uid, _), wire in jobs.items()],
                                          caps, sha(Path(__file__).read_bytes())])}
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, identity, True, ledger, cache) if wires else {}

        actors = dispatch(STAGE, jobs)
        cards = {row["uid"]: row for row in panel["cases"]}
        rows = [{"uid": uid, "method": method, "actor_status": reply["status"],
                 "answer": reply.get("answer"), "score": None, "base_score": cards[uid]["base_grade"],
                 "stratum": cards[uid]["stratum"], "group": cards[uid]["source_group"]}
                for (uid, method), reply in actors.items()]
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    options = parser.parse_args()
    if options.action == "run":
        run()
    else:
        panel, jobs, _ = prepare()
        if options.action == "freeze":
            probe.freeze(PANEL, panel)
        elif panel != read(PANEL):
            raise ValueError("Frozen panel drift")
        print(json.dumps(Counter(row["stratum"] for row in panel["cases"]), sort_keys=True))
