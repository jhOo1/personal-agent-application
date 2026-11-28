"""Cross the scorer backbone over the fixed RPEval generation backbone pairs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "ipe_c_second_backbone_v1"))
import cross_backbone as old

RUN = old.engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
STAGE = "CrossedJudge"
MODEL = "qwen3.8-flash"
NAMES = {"QWEN": ("TASK_ONLY", "RPR_PAPER_FULL"), "GPT": ("TASK_ONLY", "RP_FULL")}


def read(path):
    return json.loads(path.read_text())


def build():
    gpt = read(old.HERE / "format_recovery/RESULTS.json")
    qwen = read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")
    qrows = {r["uid"]: r for r in qwen["rows"]}
    formal = old.v41.formal.OUT
    parent = read(formal / "PLAN.json")
    cases = old.v41.author_cases(parent)
    fullq = {r["uid"]: r for r in read(formal / "RESULT_ROWS.json")
             if r["method"] == old.v41.RP and r["actor_status"] == "OK"}
    cards, jobs, missing, by_hash = {}, {}, [], {}
    for g in gpt["rows"]:
        uid = g["uid"]
        q = qrows[uid]
        assert g["labels"] == q["labels"] and g["source_group"] == q["source_group"]
        saved = {actor: {arm: r["scores"].get(arm, {}) for arm in NAMES[actor]}
                 for actor, r in (("GPT", g), ("QWEN", q))}
        if not all(cell.get("grade", {}).get("match") for by_arm in saved.values() for cell in by_arm.values()):
            missing.append(uid)
            continue
        cases_for_uid = {}
        for actor, answers in (("GPT", [g["actor"][arm]["answer"] for arm in NAMES["GPT"]]),
                               ("QWEN", [q["no_history_state"]["answer"], fullq[uid]["answer"]])):
            for arm, answer in zip(NAMES[actor], answers, strict=True):
                if not answer:
                    raise ValueError("Missing verified original answer")
                exact = old.engine.rpe_wire(parent, cases[uid], {"uid": uid, "actor_status": "OK", "answer": answer})
                if actor == "GPT" and old.sha(exact) != g["judge"][arm]["request_sha256"]:
                    raise ValueError("Historic GPT Actor scorer wire changed")
                if actor == "QWEN":
                    if old.sha(answer) != saved[actor][arm]["answer_sha256"]:
                        raise ValueError("Qwen archived answer hash drift")
                    receipt = q["no_history_state"].get("judge_receipt")
                    if arm == "TASK_ONLY" and receipt and old.sha(exact) != receipt["request_sha256"]:
                        raise ValueError("Historic Qwen no-history scorer wire changed")
                alternate = dict(exact, model=MODEL)
                if alternate == exact or exact["model"] != "gpt-4.1":
                    raise ValueError("Control scorer needs the frozen GPT-4.1 alias")
                job = by_hash.setdefault(old.sha(alternate), (uid, actor + "/" + arm))
                jobs[job] = alternate
                cases_for_uid[actor, arm] = (answer, job)
        cards[uid] = {"cells": cases_for_uid, "saved": saved, "labels": q["labels"], "stratum": g["stratum"],
                      "branch": {"GPT": g["branch"], "QWEN": g["qwen_path"]}}
    if len(cards) != 22 or len(missing) != 2 or len(jobs) > 88:
        raise ValueError("Unexpected crossed comparison roster")
    pin = {"requests": [[*key, old.sha(wire)] for key, wire in jobs.items()], "old_missing": missing,
           "code": old.sha(Path(__file__).read_bytes()), "protocol": old.sha((HERE / "PROTOCOL.md").read_bytes()),
           "service": old.probe.read_reference()[1]}
    return pin, cards, jobs


def run(pin, cards, jobs):
    probe, engine = old.probe, old.engine
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {STAGE: 88}
    ledger = []
    identity = {"experiment_sha256": old.sha(pin), "service_reference_sha256": pin["service"]}
    with probe.runner_lock(RUN / "runner.lock"):
        rated = engine.stage(STAGE, jobs, identity, True, ledger)
        scores = []
        for uid, card in cards.items():
            for (actor, arm), (answer, key) in card["cells"].items():
                reply = rated[key]
                scores.append({"uid": uid, "generator": actor, "arm": arm,
                               "answer_sha256": old.sha(answer),
                               "rating": old.score_of(uid, arm, reply, {"answer": answer}, card["labels"])})
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": scores, "ledger": ledger})


def report(pin, cards):
    data = read(PRIVATE / "RESULTS.json")
    rated = {(r["uid"], r["generator"], r["arm"]): r["rating"] for r in data["rows"]}
    aggregate = defaultdict(Counter)
    subsets = Counter()
    contracts = Counter()
    for uid, card in cards.items():
        judging = {
            "GPT": card["saved"],
            "QWEN": {actor: {arm: rated[uid, actor, arm] for arm in NAMES[actor]} for actor in NAMES},
        }
        cells = [cell for actors in judging.values() for by_arm in actors.values() for cell in by_arm.values()]
        for matched in (rated[uid, actor, arm] for actor in NAMES for arm in NAMES[actor]):
            contracts["valid_match" if matched["grade"].get("match") else "missing_match"] += 1
        if not all(c["grade"].get("match") for c in cells):
            subsets["missing_crossed"] += 1
            continue
        scopes = ["common", card["stratum"]]
        if all(c.get("flags") == [] for c in cells):
            scopes.append("all_scored_answers_unflagged")
        for scope in scopes:
            subsets[scope] += 1
            for judge, by_generator in judging.items():
                for actor, by_arm in by_generator.items():
                    methods = {"IPE_C": card["branch"][actor], "Always_Task": NAMES[actor][0],
                               "Always_Memory": NAMES[actor][1]}
                    for method, arm in methods.items():
                        grade = by_arm[arm]["grade"]
                        m = grade["match"]
                        if m["positions"] != len(card["labels"]):
                            raise ValueError("Preference denominator drift")
                        c = aggregate[f"{scope}/{judge}/{actor}/{method}"]
                        c.update(tasks=1, positions=m["positions"], match=m["matched"],
                                 exact=int(m["matched"] == m["positions"]))
                        for metric in ("OPB", "UPB", "FM"):
                            if metric in grade:
                                c[metric] += grade[metric]
                                c[metric + "_valid"] += 1
    ledger = data["ledger"]
    receipts = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return (row["unit"]["stage"], row["request_sha256"], row["status"])
    if Counter(map(key, ledger)) != Counter(map(key, receipts)):
        raise ValueError("Physical receipts diverged")
    print(json.dumps({"prior_missing": len(pin["old_missing"]), "assigned": len(cards), "subsets": subsets,
                      "contracts": contracts, "metrics": aggregate,
                      "statuses": Counter(r["status"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("freeze", "run", "report"))
    action = ap.parse_args().action
    pin, cards, requests = build()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    mark = PRIVATE / "FREEZE.json"
    if action == "freeze":
        old.probe.freeze(mark, pin)
        print("Crossed scope", len(cards), "unique alternate judge requests", len(requests))
    elif read(mark) != pin:
        raise ValueError("Frozen request identity drift")
    elif action == "run":
        run(pin, cards, requests)
    else:
        report(pin, cards)
