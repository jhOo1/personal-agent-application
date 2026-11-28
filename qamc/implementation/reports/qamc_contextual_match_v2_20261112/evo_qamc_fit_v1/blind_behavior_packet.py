"""Freeze a local, no-call behavior review from the two exposed archives."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import secrets

from qamc.common import sha

BASE = Path(__file__).resolve().parents[1]
RUNS = BASE.parents[1] / "runs" / BASE.name
OUTPUT = RUNS / "blind_behavior_packet_v1" / "private"
SEED = "qamc-blind-behavior-v1"
RP = "RPR_PAPER_FULL"
PB_ARMS = ("FULL", "GROUP", "SELECTED", "EMPTY")
RPE_STRATA = ("all_A", "only_B", "contains_C")
PB_TRACKS = ("cross_domain", "sycophancy", "beneficial_memory_usage")


def read(path):
    return json.loads(path.read_text())


def rpe_pool():
    directory = BASE / "rpeval_formal_multi_coverage_v1"
    plan = read(directory / "PLAN.json")
    cases = {c["uid"]: c for c in plan["cases"]}
    if len(cases) != 300 or any(c["independent_confirmation"] is not False for c in cases.values()):
        raise ValueError("Only the frozen exposed RPEval archive is supported")
    tasks = read(directory / "PUBLIC_TASKS.json")
    rp_rows = {r["uid"]: r for r in read(directory / "RESULT_ROWS.json") if r["method"] == RP}
    rows = read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]
    if len(rows) != len(cases) or {r["uid"] for r in rows} != cases.keys():
        raise ValueError("RPEval endpoint roster drifted")
    for row in rows:
        scores = row["scores"]
        if not all(s["grade"].get("match") for s in scores.values()):
            continue
        uid = row["uid"]
        group = cases[uid]["analysis_group_id"]
        if group != row["source_group"]:
            raise ValueError("RPEval group lineage differs")
        labels = row["labels"]
        if not labels or set(labels) - {"A", "B", "C"}:
            raise ValueError("Unexpected reference labels")
        stratum = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        endpoints = {"TASK_ONLY": row["no_history_state"]["answer"], RP: rp_rows[uid]["answer"]}
        for method, answer in endpoints.items():
            if not answer or sha(answer) != scores[method]["answer_sha256"]:
                raise ValueError("RPEval answer hash does not match the settled score")
        chosen = RP if row["old_route"] == "REUSE_RP" else "TASK_ONLY"
        if sha(endpoints[chosen]) != scores["IPE_C"]["answer_sha256"]:
            raise ValueError("IPE-C answer does not match the frozen route")
        wire = rp_rows[uid]["actor_request"]
        if sha(wire) != rp_rows[uid]["actor_request_sha256"]:
            raise ValueError("RPEval Actor request drifted")
        payload = json.loads(wire["messages"][1]["content"])
        task = tasks[uid]
        if (payload["query"], payload["current_context"], payload["facts"]) != (
            task["query"], task["current_context"], task["fixed_facts"]
        ):
            raise ValueError("RPEval current task mismatch")
        memory = [{"memory_id": m["memory_id"], "text": m["text"]} for m in task["memories"]]
        if payload["source_evidence"] != memory:
            raise ValueError("RPEval history differs from its full-history Actor")
        visible = {"query": task["query"], "context": task["current_context"],
                   "facts": task["fixed_facts"], "history": memory}
        cells = [(1, method, answer, "OK") for method, answer in endpoints.items()]
        cells.append((1, "IPE_C", endpoints[chosen], "EXACT_ROUTE_REPLAY"))
        yield uid, group, stratum, visible, cells


def persist_pool():
    from audit_settlement import audit
    from check_exposure_fr3 import prepare

    directory = RUNS / "persist_exposure_fr3_v1"
    audit(directory)
    cases, inputs, *_ = prepare()
    by_uid = defaultdict(list)
    for row in read(directory / "RESULTS.json")["rows"]:
        by_uid[row["uid"]].append(row)
    if by_uid.keys() != cases.keys():
        raise ValueError("PersistBench settlement and exposed roster differ")
    for uid, case in cases.items():
        task = inputs[uid]["public"]
        cells = []
        for row in sorted(by_uid[uid], key=lambda r: r["repeat"]):
            repeat = row["repeat"]
            full = row["methods"]["FULL"]["actor"]
            if full and sha(inputs[uid]["FULL"]) != full["request_sha256"]:
                raise ValueError("Full-history wire differs from the fixed source")
            for arm in PB_ARMS:
                cell = row["methods"][arm]
                actor = cell["actor"] or {}
                if arm in ("FULL", "EMPTY") and actor and sha(inputs[uid][arm]) != actor["request_sha256"]:
                    raise ValueError("Archived PersistBench exposure has changed")
                answer = actor.get("answer") if actor.get("status") == "OK" else None
                cells.append((repeat, arm, answer, actor.get("status", cell["status"])))
        visible = {"query": task["query"], "history": task["memories"]}
        yield uid, case["group_id"], case["category"], visible, cells


def pick(pool, strata):
    used = set()
    rows = []
    for stratum in strata:
        queue = sorted((r for r in pool if r[2] == stratum), key=lambda r: sha([SEED, r[1], r[0]]))
        picked = 0
        for row in queue:
            if row[1] in used:
                continue
            used.add(row[1])
            rows.append(row)
            picked += 1
            if picked == 4:
                break
    return rows


def export(rpe, persist, nonce):
    cards = {}
    sealed_answers = {}
    key = {}
    census = Counter()
    for benchmark, rows in (("RPEval", rpe), ("PersistBench", persist)):
        for uid, group, stratum, task, cells in rows:
            packet = sha([nonce, benchmark, uid])[:14]
            if packet in cards:
                raise ValueError("Duplicate packet identifier")
            cards[packet] = {"benchmark": benchmark, **task}
            unique = {}
            allocation = []
            for repeat, arm, answer, status in cells:
                answer_id = sha([nonce, packet, answer])[:14] if answer else None
                if answer_id:
                    unique[answer_id] = answer
                allocation.append({"repeat": repeat, "arm": arm, "answer_id": answer_id,
                                   "status": status, "answer_sha256": sha(answer) if answer else None})
            sealed_answers[packet] = unique
            key[packet] = {"uid": uid, "group": group, "stratum": stratum, "positions": allocation}
            census[benchmark, stratum, "sources"] += 1
            census[benchmark, stratum, "allocated"] += len(allocation)
            census[benchmark, stratum, "unavailable"] += sum(p["answer_id"] is None for p in allocation)
            census[benchmark, stratum, "unique_answers"] += len(unique)
    ordinal = sorted(cards)
    return ({k: cards[k] for k in ordinal},
            {k: dict(sorted(sealed_answers[k].items())) for k in ordinal}, key,
            {"/".join(k): v for k, v in sorted(census.items())})


def write_private(name, value, *, output=OUTPUT):
    path = output / name
    blob = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text() != blob:
            raise ValueError(f"Preserved packet {name} differs")
        return
    with path.open("x", encoding="utf-8") as sink:
        path.chmod(0o600)
        sink.write(blob)


def main():
    rpe = list(rpe_pool())
    persist = list(persist_pool())
    if len(rpe) != 274 or len(persist) != 49:
        raise ValueError("The expected exposed source inventories changed")
    OUTPUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    nonce_path = OUTPUT / "NONCE.json"
    nonce = read(nonce_path) if nonce_path.exists() else secrets.token_hex(32)
    cards, answers, key, counts = export(pick(rpe, RPE_STRATA), pick(persist, PB_TRACKS), nonce)
    write_private("NONCE.json", nonce)
    write_private("01_TASK_CARDS.json", cards)
    write_private("02_ANONYMOUS_ANSWERS.json", answers)
    write_private("UNBLIND_KEY.json", key)
    print(json.dumps({"counts": counts, "packets": len(cards), "model_calls": 0,
                      "cards_sha256": sha(cards), "answers_sha256": sha(answers)}, indent=2))


if __name__ == "__main__":
    main()
