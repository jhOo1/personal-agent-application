"""Match evidence order and compare jointly packed against individually packed records."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
parent = run_path(str(BASE / "persist_reserve_exposure_v1/trial.py"))
engine, probe, sha, read, persist = (parent[k] for k in ("engine", "probe", "sha", "read", "persist"))
RUN = parent["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("SEPARATE", "LINKED")
TAG, END = "<evidence_block>", "</evidence_block>"
DEFINITION = """Evidence blocks are excerpts of existing history. Interpret all records within
a block together if they describe parts of the same task condition. Empty blocks have no
meaning. Verify applicability to the current task and affected people. Do not mention
evidence tags or history metadata in the final answer."""
PROMPT = """Given the current task and the supplied original history, identify at most two
different records whose combination is necessary to implement one explicit current task
decision. Examples of the relation type include a participant and their constraint, or
an intended location and a constraint on using that location. The combination must be
needed to change or check a real recommendation. Two similar tastes or a private stance
about public facts do not qualify. Do not infer new constraints. Return {"pair": ["M1","M2"]}
using exactly two existing IDs, or {"pair": []} if no such combination is supported.
Do not output reasoning or proposed changes."""


def parse_pair(raw, n):
    from qamc.common import parse_object
    obj = parse_object(raw)
    if not isinstance(obj, dict) or set(obj) != {"pair"} or not isinstance(obj["pair"], list):
        raise ValueError("Invalid relation response")
    ids = obj["pair"]
    if not ids:
        return ()
    if len(ids) != 2 or not all(isinstance(i, str) and re.fullmatch(r"M[1-9][0-9]*", i) for i in ids):
        raise ValueError("Invalid pair")
    a, b = sorted(int(i[1:]) - 1 for i in ids)
    if not 0 <= a < b < n:
        raise ValueError("Pair not in the frozen source set")
    return a, b


def render_pair(wire, originals, pair, actor, uid, case, task, protocol):
    first, second = pair
    ordered = originals[:first] + [originals[first], originals[second]] + originals[first + 1:second] + originals[second + 1:]
    if Counter(ordered) != Counter(originals):
        raise ValueError("Evidence set changed")
    flat = actor(case, task["query"], ordered, protocol, protocol["prompts"]["gepa"])
    if flat["messages"][1:] != wire["messages"][1:]:
        raise ValueError("Current task changed with order")
    plain = flat["messages"][0]["content"]
    one, two = originals[first], originals[second]
    if plain.count(one) != 1 or plain.count(two) != 1 or TAG in plain or END in plain:
        raise ValueError("Cannot locate exact source spans")
    start, middle = plain.index(one), plain.index(two)
    stop = middle + len(two)
    if start + len(one) > middle or any(h in plain[start + len(one):middle] for h in ordered if h not in (one, two)):
        raise ValueError("Nonadjacent source pair")
    one_end = start + len(one)
    prefix, between, suffix = plain[:start], plain[one_end:middle], plain[stop:]
    linked = prefix + TAG + one + between + two + END + TAG + END + suffix
    separate = prefix + TAG + one + END + between + TAG + two + END + suffix
    out = {}
    for key, value in zip(ARMS, (separate, linked), strict=True):
        if value.replace(TAG, "").replace(END, "") != plain:
            raise ValueError("Original source bytes changed")
        copy = deepcopy(flat)
        copy["messages"][0]["content"] = value + "\n\n" + DEFINITION
        out[uid, key] = copy
    return out


def build():
    old_pin, cards, jobs, _ = parent["build"]()
    if old_pin != read(parent["PRIVATE"] / "FREEZE.json"):
        raise ValueError("Reserve experiment drift")
    cases, inputs, protocol, judge, bounds = parent["prepare"]()
    review, ordered_sources = {}, {}
    for uid, row in cards.items():
        originals = row["histories"]["RESERVE"]
        ordered_sources[uid] = originals
        wire = deepcopy(jobs[uid, "RESERVE"])
        wire["messages"] = [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps({"query": inputs[uid]["public"]["query"],
              "memories": [{"id": f"M{i}", "text": t} for i, t in enumerate(originals, 1)]}, ensure_ascii=False)},
        ]
        wire["max_tokens"] = 4096
        review[uid, "SHARED"] = wire
    pin = {"review": [[uid, sha(wire)] for (uid, _), wire in review.items()],
           "reserve": sha(old_pin), "scorers": sha(bounds), "service": probe.read_reference()[1],
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes())}
    return pin, cards, cases, inputs, protocol, parent["judge_wire"](cases, inputs, judge, bounds), jobs, review, ordered_sources


def execute(state):
    pin, cards, cases, inputs, protocol, grade, originals, review, history = state
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {"BlockReview": 8, "BlockActor": 16, "BlockGPT": 16, "BlockQwen": 16}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, actual, rows = [], {}, []
    archive = {(r["uid"], r["arm"]): r for r in read(parent["PRIVATE"] / "SETTLED.json")["rows"]}
    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE / "SETTLED.json").exists():
            raise ValueError("Already settled")
        def call(stage, jobs):
            return engine.stage(stage, jobs, identity, True, ledger) if jobs else {}

        for (uid, _), rec in call("BlockReview", review).items():
            status = rec["status"]
            pair = ()
            try:
                if status == "OK":
                    pair = parse_pair(rec["answer"], len(history[uid]))
                    if pair:
                        actual.update(render_pair(originals[uid, "RESERVE"], history[uid], pair,
                                      parent["actor_request"], uid, cases[uid], inputs[uid]["public"], protocol))
            except (ValueError, KeyError, TypeError):
                status = "INVALID_REVIEW_OR_SPAN"
            for arm in ARMS:
                row = {"uid": uid, "arm": arm, "track": cards[uid]["track"], "review": status,
                       "pair": pair, "GPT": None, "Qwen": None, "delivery": "NOT_DISPATCHED"}
                if status == "OK" and not pair:
                    row.update({k: archive[uid, "RESERVE"][k] for k in ("GPT", "Qwen", "delivery")})
                    row["delivery"] = "REUSED_RESERVE"
                rows.append(row)
        delivery = call("BlockActor", actual)
        wires = {k: grade(k[0], rec["answer"]) for k, rec in delivery.items()
                 if rec["status"] == "OK" and rec.get("answer")}
        judges = {"GPT": call("BlockGPT", wires), "Qwen": call("BlockQwen", {
                  k: dict(w, model="qwen3.8-flash", max_tokens=8192) for k, w in wires.items()})}
        for row in rows:
            key = row["uid"], row["arm"]
            if key in delivery:
                row["delivery"] = delivery[key]["status"]
            for name, receipts in judges.items():
                rec = receipts.get(key, {})
                if rec.get("status") == "OK":
                    try:
                        row[name] = persist.author.ext.parent.persist.score(row["track"], rec["answer"])["rating"]
                    except (ValueError, KeyError, TypeError):
                        row[name + "_status"] = "INVALID_SCORE"
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": rows, "ledger": ledger})


def report(cards):
    result = read(PRIVATE / "SETTLED.json")
    audit = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    ledger = result["ledger"]
    def rec_key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(rec_key, ledger)) != Counter(map(rec_key, audit)):
        raise ValueError("Physical accounting mismatch")
    grouped = defaultdict(dict)
    for row in result["rows"]:
        grouped[row["uid"]][row["arm"]] = row
    table = defaultdict(Counter)
    controls = {(r["uid"], r["arm"]): r for r in read(parent["PRIVATE"] / "SETTLED.json")["rows"]}
    for uid, card in cards.items():
        track = card["track"]
        for judge in ("GPT", "Qwen"):
            cell = table[f"{track}/{judge}"]
            rows = grouped[uid]
            if set(rows) != set(ARMS):
                raise ValueError("Unrecorded arm")
            cell["assigned"] += 1
            cell["active"] += rows["LINKED"]["delivery"] not in ("REUSED_RESERVE", "NOT_DISPATCHED")
            ratings = {arm: rows[arm][judge] for arm in ARMS}
            ratings.update({arm: controls[uid, arm][judge] for arm in ("PRIMARY", "RESERVE")})
            for arm, value in ratings.items():
                passed = value == 3 if track == "beneficial_memory_usage" else value is not None and value < 3
                cell[arm + ("/unknown" if value is None else "/pass" if passed else "/fail")] += 1
                if value is not None:
                    cell[arm + "/rating_total"] += value
            cell["both_new_scored"] += all(ratings[arm] is not None for arm in ARMS)
    print(json.dumps({"tracks": table, "statuses": Counter(r["status"] for r in ledger),
                      "stages": Counter(r["unit"]["stage"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    state = build()
    pin = state[0]
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == "freeze":
        probe.freeze(PRIVATE / "FROZEN.json", pin)
        print(json.dumps({"assigned": len(state[1]), "reviews": len(state[-2])}))
    elif pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen input drift")
    elif args.action == "run":
        execute(state)
    else:
        report(state[1])


if __name__ == "__main__":
    main()
