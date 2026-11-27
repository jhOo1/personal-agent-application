"""Read the locked choices and recover the historical scores without new requests."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import sha
from run_reward import HERE, PEERS, RUN, assemble, probe, requests, totals
from run_bridge import prepare, read
from selection import METHODS, reward_choice


def verify_inputs():
    packets, binding = assemble()
    freeze = read(RUN / "FROZEN.json")
    if (sha(packets) != freeze["packets_sha256"] or sha(binding) != freeze["binding_sha256"]
            or sha(list(requests(packets).values())) != freeze["comparison_sha256"]
            or sha((HERE / "PROTOCOL.md").read_bytes()) != freeze["protocol_sha256"]):
        raise ValueError("Selection freeze cannot be verified")
    return packets, binding


def summarize(arms, blind, states, binding, archive, bridge):
    old = {r["uid"]: r for r in bridge["rows"]}
    all_keys = list(binding)
    common = [key for key in all_keys if old[binding[key]["uid"]]["scores"]["IPE_C"] is not None]
    strict = [key for key in common if all(blind[key].values())]
    endpoint_common = [key for key in common
                       if old[binding[key]["uid"]]["scores"]["TASK_ONLY"] is not None]
    if (len(all_keys), len(common), len(endpoint_common)) != (24, 22, 21):
        raise ValueError("Historical denominator changed")
    grades = {peer: {} for peer in (*PEERS, *arms)}
    selected = {arm: {} for arm in arms}
    for key, item in binding.items():
        scores = archive[item["uid"]]
        for peer, method in zip(PEERS, METHODS, strict=True):
            grades[peer][key] = scores[method]
        for arm, choice in blind[key].items():
            method = item["order"][choice] if choice is not None else METHODS[0]
            selected[arm][key] = PEERS[METHODS.index(method)]
            grades[arm][key] = scores[method]
    pair = {}
    for arm in arms:
        pair[arm] = {}
        for peer in PEERS:
            changes = [grades[arm][k]["matched"] - grades[peer][k]["matched"] for k in common]
            pair[arm][peer] = {"wins": changes.count(1), "losses": changes.count(-1),
                               "ties": changes.count(0)}

    def summary_for(keys):
        return {arm: totals(keys, rows) for arm, rows in grades.items()}

    categories = {label: summary_for([k for k in common if old[binding[k]["uid"]]["label"] == label])
                  for label in ("A", "B", "C")}
    statuses = {arm: Counter(states[k][arm] for k in all_keys) for arm in arms}
    for k in all_keys:
        cases = old[binding[k]["uid"]]
        if any(cases["scores"][method] != archive[cases["uid"]][method] for method in METHODS):
            raise ValueError("Parent endpoint score binding differs")
    result = {"assigned": len(all_keys), "historical_overlap": len(common),
              "historical_overlap_groups": len({old[binding[k]["uid"]]["source_group"] for k in common}),
              "strict": len(strict), "historical_overlap_scores": summary_for(common),
              "strict_scores": summary_for(strict), "all_available_scores": summary_for(all_keys),
              "both_archived_endpoints_scores": summary_for(endpoint_common),
              "oracle_match_only": sum(max(grades[peer][k]["matched"] for peer in PEERS) for k in common),
              "by_author_label": categories, "paired": pair, "selection_statuses": statuses,
              "selected_methods": {arm: Counter(methods.values()) for arm, methods in selected.items()}}
    rows = {binding[k]["uid"]: {"selected": {arm: selected[arm][k] for arm in arms},
                               "choice_status": states[k], "label": old[binding[k]["uid"]]["label"],
                               "scores": {arm: g[k] for arm, g in grades.items()},
                               "historical_overlap": k in common} for k in all_keys}
    return result, rows


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--direct-only", action="store_true")
    args = parser.parse_args()
    packets, binding = verify_inputs()
    direct = read(RUN / "DIRECT_CHOICES.json")
    rewards = {} if args.direct_only else read(RUN / "REWARDS.json")
    arms = ["Direct"] if args.direct_only else ["Direct", "Reward"]
    suffix = "_DIRECT" if args.direct_only else ""
    if set(packets) != set(direct) or (not args.direct_only and set(packets) != set(rewards)):
        raise ValueError("Choice inventory is not complete")
    blind, states = {}, {}
    direct_wires = requests(packets)
    for key, packet in packets.items():
        decision = direct[key]
        if decision["request_sha256"] != sha(direct_wires[key, "DIRECT"]):
            raise ValueError("Comparison request binding differs")
        blind[key] = {"Direct": decision["choice"]}
        states[key] = {"Direct": decision["status"]}
        if rewards:
            record = rewards[key]
            choice = reward_choice(record["scores"]) if record["status"] == "OK" else None
            blind[key]["Reward"] = choice
            states[key]["Reward"] = "TIE" if choice is None and record["status"] == "OK" else record["status"]
        for choice in blind[key].values():
            if choice is not None and sha(packet["candidates"][choice]) != binding[key]["answer_sha256"][choice]:
                raise ValueError("Chosen answer binding differs")
    probe.freeze(RUN / f"CHOICE_JOIN{suffix}.json",
                 {"blind": blind, "status": states, "settlement_sha256": sha(Path(__file__).read_bytes())})
    _, _, _, _, archive, _, _, _ = prepare()
    bridge = read(RUN.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")
    aggregate, rows = summarize(arms, blind, states, binding, archive, bridge)
    ledger = read(RUN / "DIRECT_LEDGER.json")
    usage = [(r.get("usage") or {}).get("total_tokens") for r in ledger]
    aggregate["cloud"] = {"requests": len(ledger), "status": Counter(r["status"] for r in ledger),
                          "tokens": sum(v or 0 for v in usage), "unknown_usage": usage.count(None),
                          "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger)}
    if rewards:
        seconds = [r["seconds"] for r in rewards.values()]
        aggregate["local"] = {"tasks": len(rewards), "attempted_candidates": 3 * len(rewards),
                              "batch_seconds": sum(seconds),
                              "input_tokens_reported": sum(sum(r.get("input_tokens", [])) for r in rewards.values())}
    probe.freeze(RUN / f"SCORED_ROWS{suffix}.json", rows)
    probe.freeze(RUN / f"SUMMARY{suffix}.json", aggregate)
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
