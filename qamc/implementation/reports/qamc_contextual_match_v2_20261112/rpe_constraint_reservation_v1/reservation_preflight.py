"""Build the conditional answer comparison from the past frozen one-slot plan."""
from collections import Counter
import json
from pathlib import Path

from extend import archived
from memgate_rpe_preflight import contract, inputs, narrow
from qamc.common import sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = ROOT / "runs" / HERE.parent.name
RUN = RUNS / HERE.name
ARMS = ("GATE_BASE", "RESERVED", "TOP_NEXT")


def read(path):
    return json.loads(path.read_text())


def prepare():
    manifest, tasks, rp, ranks, endpoints = inputs()
    plan = read(RUN / "SELECTION_PRIVATE.json")
    shape = read(RUNS / "rpe_memgate_matched_actor_v1/PREFLIGHT_PRIVATE.json")
    prior_equal = {
        r["uid"]: r["arms"]["EN_GATE"]
        for r in read(RUNS / "rpe_memgate_equal_count_answer_v1/RESULTS.json")["rows"]
    }
    prior_chinese = {
        r["uid"]: r for r in read(RUNS / "rpe_memgate_matched_actor_v1/RESULTS.json")["rows"]
    }
    if sha(plan["plans"]) != plan["pins"]["plan_sha256"] or len(plan["plans"]) != 286:
        raise ValueError("Reservation plans changed")
    requests, rows = {}, {}
    possible_reuses = []
    for ref in manifest:
        uid = ref["uid"]
        info = plan["plans"].get(uid)
        if not info or info["reserved_add"] is None:
            continue
        base = info["base"]
        wire, ids, evidence = contract(tasks[uid], rp[uid], ranks[uid]["policies"]["PAPER_FUSION"])
        if (not base or len(base) >= len(ids)
                or any(info[k] not in ids or info[k] in base for k in ("reserved_add", "top_add"))):
            raise ValueError("Expected a single addition to a proper nonempty source set")
        lengths = {s["memory_id"]: len(s["text"]) for s in evidence}
        arms = {}
        for arm in ARMS:
            requested = set(base if arm == "GATE_BASE" else base + [
                info["reserved_add"] if arm == "RESERVED" else info["top_add"]])
            new_wire = narrow(wire, requested)
            fp = sha(new_wire)
            if requests.setdefault(fp, new_wire) != new_wire:
                raise ValueError("Conflicting Actor input identity")
            arms[arm] = {"request_sha256": fp, "ids": [sid for sid in ids if sid in requested],
                         "original_characters": sum(lengths[sid] for sid in requested)}
        rows[uid] = {"track": ref["track"], "group_id": ref["analysis_group_id"],
                     "previous_trial": uid in prior_equal, "arms": arms}

        previous = prior_equal.get(uid)
        if previous:
            source = previous["request_sha256"]
            if source != arms["GATE_BASE"]["request_sha256"]:
                raise ValueError("The previous English gate base changed")
            possible_reuses.append((uid, source, previous["actor"], previous["score"], previous["status"],
                                    "FROZEN_EN_GATE"))
        old = prior_chinese[uid]
        source = old["actor"]["request_sha256"]
        if source in requests:
            if source != shape["selection"][uid]["request_sha256"] or requests[source] != shape["requests"][source]:
                raise ValueError("Chinese gate exact Actor changed")
            possible_reuses.append((uid, source, old["actor"], old["scores"]["MEMGATE_RP_ACTOR"], old["status"],
                                    "FROZEN_ZH_GATE"))
        source = sha(wire)
        if source in requests:
            old_score = endpoints[uid]["scores"]["RPR_PAPER_FULL"]
            answer = rp[uid]["answer"]
            if old_score["answer_sha256"] != sha(answer):
                raise ValueError("Archived RP score does not match old answer")
            possible_reuses.append((uid, source, {"status": "OK", "answer": answer, "request_sha256": source},
                                    old_score, "OK" if old_score["grade"].get("match") else "INVALID_MATCH",
                                    "FROZEN_FULL"))
    fixed = {}
    for uid, fp, actor, grade, status, origin in possible_reuses:
        if actor["request_sha256"] != fp:
            raise ValueError("Archived Actor mismatches the frozen request")
        fixed.setdefault(fp, {**actor, "origin": origin, "fixed_score": grade,
                              "fixed_status": status, "fixed_uid": uid})
    replay, dbs = archived({fp: wire for fp, wire in requests.items() if fp not in fixed}, ROOT)
    prefix = RUN.relative_to(ROOT).as_posix() + "/"
    replay = {fp: rec for fp, rec in replay.items() if not rec["archive"].startswith(prefix)}
    reused = {**replay, **fixed}
    result = {
        "rows": rows, "requests": requests, "reused_actors": reused,
        "pins": {"selection_sha256": sha(plan), "protocol_sha256": sha((HERE / "ANSWER_PROTOCOL.md").read_bytes()),
                 "preflight_code_sha256": sha(Path(__file__).read_bytes()), "endpoints_sha256": sha(endpoints)},
    }
    picture = {
        "triggered_tasks": len(rows), "old_equal_count_overlap": sum(r["previous_trial"] for r in rows.values()),
        "triggered_source_groups": len({r["group_id"] for r in rows.values()}),
        "different_expansion_wires": sum(r["arms"]["RESERVED"]["request_sha256"]
                                         != r["arms"]["TOP_NEXT"]["request_sha256"] for r in rows.values()),
        "unique_actors": len(requests), "actor_cache_origins": Counter(row["origin"] for row in reused.values()),
        "new_actor_cap": len(requests) - len(reused), "judge_cap": len(requests) - len(fixed),
        "searched_journals": dbs, "private_plan_sha256": sha(result), "cloud_requests": 0,
    }
    return result, picture


if __name__ == "__main__":
    plan, summary = prepare()
    with (RUN / "ANSWER_PRIVATE.json").open("x") as stream:
        json.dump(plan, stream, ensure_ascii=False)
    print(json.dumps(summary, indent=2, sort_keys=True))
