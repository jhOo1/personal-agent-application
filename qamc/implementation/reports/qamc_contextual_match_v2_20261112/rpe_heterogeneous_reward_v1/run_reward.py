"""Freeze blind choices before joining verified historical scores."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from qamc.common import sha
from qamc.contextual_match.development import text_request
from qamc.pa.core import digest
from run_bridge import OLD, MODEL, ROOT, frozen_manifest, prepare, read, probe, engine
from extend import archived, merge_stage
from selection import IDS, METHODS, REPO, REVISION, SYSTEM, blind_order, parse_compare, reward_choice, serialize_task

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
STAGE = "BlindCompare"
PEERS = ("RP", "Des2Gen", "MemAdapter")


def assemble():
    cases = frozen_manifest()
    public = read(OLD / "PUBLIC_TASKS.json")
    rows = {(r["uid"], r["method"]): r for r in read(OLD / "RESULT_ROWS.json")
            if r["uid"] in cases and r["method"] in METHODS}
    packets, binding = {}, {}
    for uid, case in cases.items():
        task = public[uid]
        if digest(task) != case["public_hash"]:
            raise ValueError("Public task hash changed")
        context = serialize_task(task)
        order = blind_order(uid)
        candidates = {}
        for cid, method in order.items():
            row = rows[uid, method]
            if (row["actor_status"] != "OK" or not row["answer"].strip()
                    or sha(row["actor_request"]) != row["actor_request_sha256"]):
                raise ValueError("Candidate provenance cannot be verified")
            candidates[cid] = row["answer"]
        key = sha({"public_sha256": case["public_hash"], "order": list(order.items())})
        packets[key] = {"context": context, "candidates": candidates}
        binding[key] = {"uid": uid, "order": order, "answer_sha256": {k: sha(v) for k, v in candidates.items()}}
    return packets, binding


def requests(packets):
    return {(key, "DIRECT"): text_request(SYSTEM, packet, MODEL, 8192)
            for key, packet in packets.items()}


def compare(packets, pin):
    jobs = requests(packets)
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(packets)}
    with probe.runner_lock(RUN / "runner.lock"):
        identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
        probe.freeze(RUN / "EXECUTION.json", identity)
        # Search an exact prior request without treating absent or failed work as a score.
        cache, _ = archived(jobs, ROOT)
        cache = {key: data for key, data in cache.items() if RUN.name not in Path(data["archive"]).parts}
        ledger = []
        receipts = merge_stage(STAGE, jobs, cache, identity, ledger)
        choices = {}
        for (key, _), row in receipts.items():
            status, choice = row["status"], None
            if status == "OK":
                try:
                    choice = parse_compare(row["answer"])
                except (ValueError, TypeError):
                    status = "INVALID_CHOICE"
            choices[key] = {"choice": choice, "status": status, "request_sha256": row["request_sha256"]}
        probe.freeze(RUN / "DIRECT_CHOICES.json", choices)
        probe.freeze(RUN / "DIRECT_LEDGER.json", ledger)
        print(f"direct: {len(choices)} tasks, {len(ledger)} physical calls", flush=True)


def totals(keys, rows):
    metrics = ("OPB", "UPB", "FM")
    return {"tasks": len(keys), "Match": sum(rows[k]["matched"] for k in keys),
            **{m: sum(rows[k]["severity"][m] for k in keys) for m in metrics}}


def settle(packets, binding):
    direct = read(RUN / "DIRECT_CHOICES.json")
    rewards = read(RUN / "REWARDS.json")
    if set(packets) != set(direct) or set(packets) != set(rewards):
        raise ValueError("Blind choices incomplete")
    blind = {}
    for key in packets:
        record = rewards[key]
        choice = reward_choice(record["scores"]) if record["status"] == "OK" else None
        blind[key] = {"Reward": choice, "Direct": direct[key]["choice"]}
    probe.freeze(RUN / "LOCKED_CHOICES.json", blind)

    _, _, refs, _, archive, _, _, _ = prepare()
    scores = {p: {} for p in (*PEERS, "Reward", "Direct")}
    entered = {p: Counter() for p in ("Reward", "Direct")}
    statuses = {p: Counter() for p in entered}
    for key, item in binding.items():
        uid, order = item["uid"], item["order"]
        grades = archive[uid]
        for name, method in zip(PEERS, METHODS, strict=True):
            scores[name][key] = grades[method]
        for arm, choice in blind[key].items():
            status = rewards[key]["status"] if arm == "Reward" else direct[key]["status"]
            if choice is None and status == "OK":
                status = "TIE"
            method = order[choice] if choice else METHODS[0]
            if choice and sha(packets[key]["candidates"][choice]) != item["answer_sha256"][choice]:
                raise ValueError("Chosen answer changed since the input freeze")
            scores[arm][key] = grades[method]
            statuses[arm][status] += 1
            entered[arm][PEERS[METHODS.index(method)]] += 1
    bridge = read(RUN.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")
    valid_old_uids = {r["uid"] for r in bridge["rows"] if r["scores"].get("TASK_ONLY") is not None}
    old_common = [k for k in packets if binding[k]["uid"] in valid_old_uids]
    if len(old_common) != 22:
        raise ValueError(f"Unexpected common comparison size: {len(old_common)}")
    strict = [k for k in old_common if all(blind[k].values())]
    per_label = {}
    for label in sorted({refs[item["uid"]]["intent_type"] for item in binding.values()}):
        subset = [k for k in old_common if refs[binding[k]["uid"]]["intent_type"] == label]
        per_label[label] = {arm: totals(subset, rows) for arm, rows in scores.items()}
    pairs = {}
    for trial in ("Reward", "Direct"):
        pairs[trial] = {}
        for base in PEERS:
            diffs = [scores[trial][k]["matched"] - scores[base][k]["matched"] for k in old_common]
            pairs[trial][base] = {"wins": diffs.count(1), "losses": diffs.count(-1), "ties": diffs.count(0)}
    abstract = {"assigned": len(packets), "old_common": len(old_common), "strict": len(strict),
                "complete_roster": {arm: totals(list(packets), rows) for arm, rows in scores.items()},
                "old_common_scores": {arm: totals(old_common, rows) for arm, rows in scores.items()},
                "strict_scores": {arm: totals(strict, rows) for arm, rows in scores.items()},
                "oracle_match_only": sum(max(scores[method][k]["matched"] for method in PEERS) for k in old_common),
                "by_author_label": per_label, "paired": pairs, "selected_methods": entered,
                "selection_statuses": statuses}
    probe.freeze(RUN / "SCORED_ROWS.json", scores)
    probe.freeze(RUN / "SUMMARY.json", abstract)
    print(abstract)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "compare", "settle"))
    args = parser.parse_args()
    packets, binding = assemble()
    pin = {"packets_sha256": sha(packets), "binding_sha256": sha(binding),
           "comparison_sha256": sha(list(requests(packets).values())),
           "reward_repository": REPO, "reward_revision": REVISION,
           "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
           "source_sha256": {f.name: sha(f.read_bytes()) for f in (*HERE.glob("*.py"), *HERE.glob("*.sh"))}}
    if args.action == "freeze":
        probe.freeze(RUN / "BLIND_PACKETS.json", packets)
        probe.freeze(RUN / "BINDING.json", binding)
        probe.freeze(RUN / "FROZEN.json", pin)
    elif pin != read(RUN / "FROZEN.json") or packets != read(RUN / "BLIND_PACKETS.json"):
        raise ValueError("Frozen blind inputs or code changed")
    elif args.action == "compare":
        compare(packets, pin)
    else:
        settle(packets, binding)


if __name__ == "__main__":
    main()
