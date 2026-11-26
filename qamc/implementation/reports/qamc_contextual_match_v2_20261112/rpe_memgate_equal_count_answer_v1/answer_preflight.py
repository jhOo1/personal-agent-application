"""Build fixed, source-group-disjoint equal-count requests without scoring."""
import argparse
from collections import Counter
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
import torch

from extend import archived
from memgate_rpe_preflight import contract, inputs, narrow
from qamc.common import sha
from language_control import top_k

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = ROOT / "runs" / HERE.parent.name
RUN = RUNS / HERE.name
ARMS = ("ZH_GATE", "EN_GATE", "EN_COSINE")
FORMATS = ("explicit", "implicit")


def read(path):
    return json.loads(path.read_text())


def sets(row):
    return row["modes"]["ZH"]["matched_en_count"], row["modes"]["EN"]["threshold"]


def allocate(manifest, local):
    eligible = {
        fmt: sorted(
            (c for c in manifest if c["uid"] in local and local[c["uid"]]["status"] == "OK"
             and c["track"].split("/")[0] == fmt and sets(local[c["uid"]])[0] != sets(local[c["uid"]])[1]),
            key=lambda case: sha("rpe-equal-count-answer-v1/" + case["uid"]),
        )
        for fmt in FORMATS
    }
    chosen, groups = [], set()
    for _ in range(12):
        for fmt in FORMATS:
            c = next(c for c in eligible[fmt] if c["analysis_group_id"] not in groups)
            chosen.append(c)
            groups.add(c["analysis_group_id"])
    return chosen, {fmt: len(values) for fmt, values in eligible.items()}


def inventory(embedding):
    manifest, tasks, rp, ranks, _ = inputs()
    lab = RUNS / "rpe_memgate_language_wide_v1"
    local = read(lab / "RESULTS.json")
    freeze = read(lab / "FROZEN.json")
    original = read(RUNS / "rpe_memgate_matched_actor_v1/PREFLIGHT_PRIVATE.json")
    if (
        local.keys() != set(freeze["uids"]) or len(local) != 295
        or freeze["memgate_plan_sha256"] != sha(original["selection"])
        or sha((embedding / "model.safetensors").read_bytes())
        != original["pins"]["released_artifacts"]["model.safetensors"]
        or embedding.name != "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    ):
        raise ValueError("Representation or frozen selection changed")
    selected, counts = allocate(manifest, local)
    torch.set_num_threads(2)
    encoder = SentenceTransformer(str(embedding), device="cpu", local_files_only=True)
    requests, rows = {}, {}
    for case in selected:
        uid = case["uid"]
        record = local[uid]
        task = tasks[uid]
        wire, ids, evidence = contract(task, rp[uid], ranks[uid]["policies"]["PAPER_FUSION"])
        zh, en = sets(record)
        k = len(en)
        if not (0 < k < len(ids) and len(zh) == k and set(zh + en) <= set(ids)):
            raise ValueError("Invalid cardinality-matched sets")
        english = record["translations"]
        if len(english) != len(ids) + 1:
            raise ValueError("Translation lost source alignment")
        with torch.inference_mode():
            v = encoder.encode(english, normalize_embeddings=True, convert_to_tensor=True, show_progress_bar=False)
            cosine = [ids[i] for i in top_k((v[1:] @ v[0]).tolist(), k)]
        lengths = {item["memory_id"]: len(item["text"]) for item in evidence}
        rows[uid] = {"track": case["track"], "group_id": case["analysis_group_id"], "count": k, "arms": {}}
        for arm, sources in zip(ARMS, (zh, en, cosine), strict=True):
            new = narrow(wire, set(sources))
            key = sha(new)
            if requests.setdefault(key, new) != new:
                raise ValueError("Conflicting Actor wire identity")
            rows[uid]["arms"][arm] = {
                "request_sha256": key, "ids": sources, "original_characters": sum(lengths[s] for s in sources),
            }
    old_run = RUNS / "rpe_memgate_matched_actor_v1"
    old_results = {row["uid"]: row for row in read(old_run / "RESULTS.json")["rows"]}
    fixed = {}
    for uid in rows:
        entry = old_results[uid]["actor"]
        key = entry["request_sha256"]
        if key in requests:
            if key != original["selection"][uid]["request_sha256"] or requests[key] != original["requests"][key]:
                raise ValueError("Frozen direct Chinese request changed")
            fixed[key] = {
                **entry, "origin": "DIRECT_ZH_FIXED",
                "fixed_score": old_results[uid]["scores"]["MEMGATE_RP_ACTOR"],
                "fixed_status": old_results[uid]["status"], "fixed_uid": uid,
            }
    replay, n_journals = archived({key: v for key, v in requests.items() if key not in fixed}, ROOT)
    prefix = RUN.relative_to(ROOT).as_posix()
    replay = {key: row for key, row in replay.items() if not row["archive"].startswith(prefix + "/")}
    reused = {**replay, **fixed}
    return ({
        "rows": rows, "requests": requests, "reused_actors": reused,
        "pins": {
            "inputs_sha256": sha({u: tasks[u] for u in rows}),
            "local_selection_sha256": sha(local),
            "old_memgate_result_sha256": sha(read(old_run / "RESULTS.json")),
            "code_sha256": sha(Path(__file__).read_bytes()),
            "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
        },
    }, {"conditional_eligible_by_format": counts, "searched_journals": n_journals,
        "logical_actors": len(rows) * len(ARMS), "unique_actors": len(requests),
        "reused_exact_actors": dict(Counter(row["origin"] for row in reused.values())),
        "new_actor_cap": len(requests) - len(reused), "possible_grades_before_cache": len(requests) - len(fixed),
        "all_three_distinct": sum(len({a["request_sha256"] for a in r["arms"].values()}) == 3 for r in rows.values()),
        "planned_tasks": len(rows), "new_requests_dispatched": 0})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("embedding", type=Path)
    cli.add_argument("--freeze", action="store_true")
    args = cli.parse_args()
    plan, report = inventory(args.embedding)
    if args.freeze:
        with (RUN / "FROZEN.json").open("x") as file:
            json.dump(plan, file, ensure_ascii=False)
    print(json.dumps({**report, "private_plan_sha256": sha(plan)}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
