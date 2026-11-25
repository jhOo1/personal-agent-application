"""Freeze optional blinded diagnostics for consequential V41 disagreements."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
import sys

from qamc.common import canonical, sha
from audit_completed import audited_rows
from run_v41 import ARMS, OUT, RP, RUN, probe, read
from qamc_rpeval_terminal_judge_sensitivity import inspect

sys.path.insert(0, str(OUT.parent / "decision_scoped_policy_v40"))
from behavior_audit import PROMPT, QUALITIES, validate

DELTA, REVIEW = ARMS
METHODS = (RP, REVIEW, DELTA)
HOME = OUT / "behavior_diagnostic"
RUN_HOME = RUN / "behavior_diagnostic"
ORDER_RULE = "v41-blind-order-20261118"
BLIND_PROMPT = PROMPT + (
    "\nThere are three anonymized answers to the same task. Include all three. "
    "Assess each actual recommendation or constraint and the people it applies to. "
    "Record UNCERTAIN if the answer and source do not support a clear judgment. "
    "A similar task-supported recommendation alone is not sufficient evidence of history use."
)


def candidates(plan):
    roots = {root["uid"]: root for root in plan["roots"]}
    collected = []
    finished_count = 0
    for rows, _ in audited_rows(plan):
        finished_count += len(rows)
        for row in rows:
            uid, labels = row["uid"], row["labels"]
            root = roots[uid]
            answers = {RP: root["archived"][RP]["answer"],
                       **{arm: row["answers"][arm]["answer"] for arm in ARMS}}
            if not all(answers.values()) or len(set(answers.values())) != len(METHODS):
                continue
            scores = {arm: row["native"][arm]["fields"] for arm in METHODS}
            if any("match" not in score for score in scores.values()):
                continue
            diagnostics = {arm: inspect({"uid": uid, "method": arm, "answer": answers[arm],
                                         "native_fields": scores[arm],
                                         "raw_scores": {"RPEvalJudge": row["native"][arm]["raw"]}}, labels)
                           for arm in METHODS}
            collected.append({
                "uid": uid, "group": root["group"], "labels": labels,
                "task": root["public_task"], "memories": root["original_sources"], "answers": answers,
                "delta_review": scores[DELTA]["match"]["matched"] - scores[REVIEW]["match"]["matched"],
                "rp_delta": scores[RP]["match"]["matched"] - scores[DELTA]["match"]["matched"],
                "upb_delta_review": scores[DELTA].get("UPB", 0) - scores[REVIEW].get("UPB", 0)
                    if all("UPB" in scores[arm] for arm in ARMS) else None,
                "flags": {arm: value["flags"] for arm, value in diagnostics.items()},
            })
    return collected, finished_count


def select(items):
    def all_a(row):
        return set(row["labels"]) == {"A"}

    def mixed(row):
        return not all_a(row)

    rules = (
        ("all_A_delta_win", lambda r: all_a(r) and r["delta_review"] > 0, lambda r: -r["delta_review"]),
        ("all_A_RP_win", lambda r: all_a(r) and r["rp_delta"] > 0, lambda r: -r["rp_delta"]),
        ("all_A_conflicting_judge", lambda r: all_a(r) and any(r["flags"].values()),
         lambda r: -sum(bool(flags) for flags in r["flags"].values())),
        ("B_possible_omission", lambda r: "B" in r["labels"] and (r["upb_delta_review"] or 0) > 0,
         lambda r: -r["upb_delta_review"]),
        ("C_possible_weakening", lambda r: "C" in r["labels"] and r["delta_review"] < 0,
         lambda r: r["delta_review"]),
        ("BC_delta_win", lambda r: mixed(r) and r["delta_review"] > 0, lambda r: -r["delta_review"]),
    )
    selected, groups = {}, set()
    for tag, keep, ranking in rules:
        eligible = [row for row in items if row["group"] not in groups and keep(row)]
        if eligible:
            row = min(eligible, key=lambda r: (ranking(r), sha([ORDER_RULE, tag, r["uid"]])))
            groups.add(row["group"])
            selected[tag] = row
    return selected


def prepare(preflight=False):
    plan = read(OUT / "FROZEN.json")
    pool, count = candidates(plan)
    if count != len(plan["roots"]) and not preflight:
        raise ValueError("Wait for all primary waves before freezing the behavior sample")
    picked = select(pool)
    packets, keys = {}, {}
    for tag, row in picked.items():
        shift = int(sha([ORDER_RULE, row["uid"]])[-2:], 16) % len(METHODS)
        order = METHODS[shift:] + METHODS[:shift]
        endpoints = (order, order[::-1])
        for i, endpoint in enumerate(endpoints, 1):
            name = f"{tag}/order{i}"
            alias = {f"V{j}": arm for j, arm in enumerate(endpoint, 1)}
            public = {"task": row["task"], "memories": row["memories"],
                      "answers": {key: row["answers"][arm] for key, arm in alias.items()}}
            wire = {"model": "gpt-6.1-sol", "stream": True, "messages": [
                {"role": "system", "content": BLIND_PROMPT}, {"role": "user", "content": canonical({"C1": public})}]}
            packets[name] = wire
            keys[name] = {"uid": row["uid"], "group": row["group"], "arm": alias,
                          "labels": dict(zip((item["memory_id"] for item in row["memories"]), row["labels"], strict=True)),
                          "request_sha256": sha(wire)}
    return {"complete_primary_panel": count == len(plan["roots"]), "completed_roots": count,
            "eligible_cases": len(pool), "picked": {tag: row["uid"] for tag, row in picked.items()},
            "packets": packets, "keys": keys,
            "service_reference_sha256": plan["service_reference_sha256"]}


def collect(plan, observations):
    cases = defaultdict(lambda: defaultdict(list))
    for name, vote in observations.items():
        key, wire = plan["keys"][name], plan["packets"][name]
        if sha(wire) != key["request_sha256"]:
            raise ValueError("Blind packet changed")
        validate(vote, wire)
        for alias, arm in key["arm"].items():
            cases[key["uid"]][arm].append(vote["C1"][alias])
    labels = {key["uid"]: key["labels"] for key in plan["keys"].values()}
    rows, counters = {}, {arm: Counter() for arm in METHODS}
    for uid, arms in cases.items():
        if set(arms) != set(METHODS) or any(len(votes) != 2 for votes in arms.values()):
            continue
        individual = rows[uid] = {}
        for arm, votes in arms.items():
            value = individual[arm] = {"qualities": {}, "positions": {}}
            for name in QUALITIES:
                first, second = (vote[name] for vote in votes)
                grade = first if first == second else "UNCERTAIN"
                value["qualities"][name] = grade
                counters[arm][f"{name}/{grade}"] += 1
            for memory_id, label in labels[uid].items():
                a, b = (vote["sources"][memory_id] for vote in votes)
                use = a["use"] if a["use"] == b["use"] else "UNCERTAIN"
                bound = a["bound"] if a["bound"] == b["bound"] else "UNCERTAIN"
                value["positions"][memory_id] = {"label": label, "use": use, "bound": bound}
                counters[arm][f"author_{label}/use_{use}"] += 1
                counters[arm][f"author_{label}/bound_{bound}"] += 1
    return {"paired_order_complete_roots": len(rows), "rows": rows, "counts": counters,
            "raw_native_scores_changed": 0, "evidence_type": "targeted blinded automated interpretation"}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "freeze", "run", "report"))
    phase = parser.parse_args().phase
    path = HOME / "FROZEN.json"
    if phase == "preflight":
        output = prepare(preflight=True)
        print(json.dumps({k: v for k, v in output.items() if k not in ("keys", "packets", "service_reference_sha256")}))
        return
    with probe.runner_lock(RUN_HOME / "audit.lock"):
        if phase == "freeze":
            output = prepare()
            probe.freeze(path, output)
            print(json.dumps({"picked": output["picked"], "requests": len(output["packets"])}))
            return
        plan = read(path)
        if phase == "run":
            if plan != prepare() or not plan["complete_primary_panel"]:
                raise ValueError("Blind freeze changed or primary panel incomplete")
            probe.OUT, probe.RUN = HOME, RUN_HOME
            probe.CAP = {"Blind": 12}
            probe.answer_grid = lambda roots: {name: {"ready": True} for name in plan["packets"]}
            probe.blind_wire = lambda root, _: plan["packets"][root["uid"]]
            probe.validate_blind = validate
            probe.blind({"roots": [{"uid": name} for name in plan["packets"]],
                         "service_reference_sha256": plan["service_reference_sha256"]})
        elif phase == "report":
            votes, receipts = {}, {}
            for name, packet in plan["packets"].items():
                folder = RUN_HOME / "Blind" / sha(name)
                if (folder / "record.json").is_file():
                    record = read(folder / "record.json")
                    if record["request_sha256"] != sha(packet):
                        raise ValueError("Blind receipt changed")
                    receipts[name] = record
                    if record["status"] == "OK":
                        votes[name] = read(folder / "vote.json")
            print(json.dumps({**collect(plan, votes), "receipts": receipts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
