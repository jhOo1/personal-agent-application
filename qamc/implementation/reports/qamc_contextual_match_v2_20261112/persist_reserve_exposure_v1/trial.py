"""Separate reserve source identity from sample variation and history length."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "persist_utility_fresh_deployment_v1"))

from inspect_answers import records
from check_exposure_fr3 import prepare, judge_wire
from complete import actor_request, engine, probe, select, sha
from repeat_receipts import branch
from transfer_replay import persist

RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("PRIMARY", "RESERVE", "EQUAL_COUNT")
LIMIT = 24
SEED = "persist-reserve-exposure-v1"


def read(path):
    return json.loads(path.read_text())


def arms(original, primary, reserve):
    """Keep the baseline prefix. Match added count using unselected sources."""
    if not primary or not reserve or not set(primary) < set(reserve):
        return None
    if len(original) != len(set(original)) or not set(reserve) <= set(original):
        raise ValueError("Cannot align candidate identities")
    extra = [text for text in original if text in reserve and text not in primary]
    alternatives = [text for text in original if text not in reserve]
    if not alternatives:
        return None
    alternatives.sort(key=lambda text: sha([SEED, str(original.index(text))]))
    num_swap = min(len(extra), len(alternatives))
    matched = set(extra[num_swap:] + alternatives[:num_swap])
    control = [text for text in original if text in matched]
    assert len(control) == len(extra) and set(control) != set(extra)
    return {"PRIMARY": primary, "RESERVE": primary + extra, "EQUAL_COUNT": primary + control}


def build():
    cases, inputs, protocol, judge, bounds = prepare()
    risk = read(RUN.parent / "persist_exposure_fr3_v1/RESULTS.json")["rows"]
    previous = {(r["uid"], r["repeat"]): r for r in risk}
    route, selector, old_actor = (records(stage) for stage in ("Route", "Select", "Actor"))
    prior_utility = {r["uid"]: r for r in read(RUN.parent / "persist_utility_fresh_deployment_v1/private/SETTLED.json")["rows"]
                     if r["arm"] == "RUBRIC"}
    card, considered, jobs = {}, {}, {}
    for uid in sorted(cases):
        case, item = cases[uid], inputs[uid]
        task = item["public"]

        def reconstruct(rep):
            row = previous[uid, rep]
            if row["exposure"] is None:
                return None
            history = select(case, task, row["route"]["answer"], row["selector"]["answer"])
            if sha(history) != row["exposure"]["sha256"]:
                raise ValueError("Reserve source digest changed")
            return history

        reserve = reconstruct(1)
        utility = case["category"] == "beneficial_memory_usage"
        if utility:
            requests = item["selection_requests"]
            routed = route[sha(requests["query"])]
            primary = select(case, task, routed, selector[sha(requests[branch(task, routed)])])
            q = actor_request(case, task["query"], primary, protocol, protocol["prompts"]["gepa"])
            if sha(q) not in old_actor:
                raise ValueError("Primary was not actually delivered")
        else:
            primary = reconstruct(2)
        if not primary or not reserve or not set(primary) < set(reserve):
            continue
        histories = arms(task["memories"], primary, reserve)
        considered[uid] = histories is not None
        if histories is None:
            continue
        for arm, history in histories.items():
            jobs[uid, arm] = actor_request(case, task["query"], history, protocol, protocol["prompts"]["gepa"])
        control = prior_utility[uid]["GPT"] if utility else previous[uid, 2]["methods"]["RUBRIC"]["score"]
        card[uid] = {"track": case["category"], "group": case["group_id"], "histories": histories,
                     "source_chars": {arm: sum(map(len, h)) for arm, h in histories.items()},
                     "archived_rubric": control, "memory_count": len(task["memories"])}
    if len(considered) != 8 or not 2 <= len(card) <= 8 or len(jobs) > LIMIT:
        raise ValueError("Exposure qualification outside the frozen roster")
    if len({sha(w) for w in jobs.values()}) != len(jobs):
        raise ValueError("Candidate requests are not distinct")
    frozen = {"eligible_without_control": sorted(set(considered) - card.keys()),
              "request_hashes": [[uid, arm, sha(w)] for (uid, arm), w in jobs.items()],
              "scorer_envelopes": {uid: sha(bounds[uid]) for uid in card},
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
              "service": probe.read_reference()[1]}
    return frozen, card, jobs, judge_wire(cases, inputs, judge, bounds)


def run(frozen, cards, jobs, grade):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {stage: LIMIT for stage in ("ReserveActor", "ReserveGPT", "ReserveQwen")}
    identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": frozen["service"]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        def call(stage, pending):
            return engine.stage(stage, pending, identity, True, ledger) if pending else {}

        generated = call("ReserveActor", jobs)
        eligible = {k: grade(k[0], row["answer"]) for k, row in generated.items()
                    if row["status"] == "OK" and row.get("answer")}
        judged = {"GPT": call("ReserveGPT", eligible),
                  "Qwen": call("ReserveQwen", {k: dict(w, model="qwen3.8-flash", max_tokens=8192)
                                              for k, w in eligible.items()})}
        result = []
        scorer = persist.author.ext.parent.persist
        for (uid, arm), rec in generated.items():
            row = {"uid": uid, "arm": arm, "track": cards[uid]["track"], "delivery": rec["status"],
                   "answer_hash": sha(rec["answer"]) if rec.get("answer") else None}
            for judge, replies in judged.items():
                item = replies.get((uid, arm), {})
                row[judge] = None
                row[judge + "_status"] = item.get("status", "NOT_DISPATCHED")
                if item.get("status") == "OK":
                    try:
                        row[judge] = scorer.score(row["track"], item["answer"])["rating"]
                    except (ValueError, KeyError, TypeError):
                        row[judge + "_status"] = "INVALID_SCORE"
            result.append(row)
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": result, "ledger": ledger})


def report(frozen, cards):
    data = read(PRIVATE / "SETTLED.json")
    rows = {(r["uid"], r["arm"]): r for r in data["rows"]}
    assert len(rows) == len(cards) * len(ARMS)
    table, pairs, archived = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for uid, card in cards.items():
        track = card["track"]
        utility = track == "beneficial_memory_usage"
        def outcome(rating):
            return None if rating is None else rating == 3 if utility else rating < 3

        for judge in ("GPT", "Qwen"):
            vals = {arm: outcome(rows[uid, arm][judge]) for arm in ARMS}
            k = f"{track}/{judge}"
            for arm, val in vals.items():
                table[k][f"{arm}/" + ("unknown" if val is None else "pass" if val else "fail")] += 1
            for control in ("PRIMARY", "EQUAL_COUNT"):
                a, b = vals["RESERVE"], vals[control]
                pairs[f"{k}/{control}"]["unknown" if None in (a,b) else "tie" if a == b else "win" if a else "loss"] += 1
        val = card["archived_rubric"]
        if isinstance(val, dict):
            val = val.get("rating")
        val = outcome(val)
        archived[track]["unknown" if val is None else "pass" if val else "fail"] += 1
    ledger = data["ledger"]
    physical = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def key(r):
        return r["unit"]["stage"], r["request_sha256"], r["status"]
    if Counter(map(key, physical)) != Counter(map(key, ledger)):
        raise ValueError("Ledger and receipts differ")
    print(json.dumps({"tracks": Counter(c["track"] for c in cards.values()),
                      "without_equal_count": len(frozen["eligible_without_control"]),
                      "tables": table, "reserve_pairs": pairs, "archived_rubric_gpt": archived,
                      "status": Counter(r["status"] for r in ledger),
                      "stages": Counter(r["unit"]["stage"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    frozen, cards, jobs, grade = build()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    pin = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(pin, frozen)
        print("Eligible", Counter(c["track"] for c in cards.values()), "Actor calls", len(jobs))
        print("No distinct equal-count counterfactual", len(frozen["eligible_without_control"]))
    elif read(pin) != frozen:
        raise ValueError("Frozen identity changed")
    elif action == "run":
        run(frozen, cards, jobs, grade)
    else:
        report(frozen, cards)
