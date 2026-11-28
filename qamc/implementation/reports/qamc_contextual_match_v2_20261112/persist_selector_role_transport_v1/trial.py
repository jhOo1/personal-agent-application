"""Isolate selector history role, then dispatch only novel downstream wires."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
parent = run_path(str(HERE.parent / "persist_matched_reminder_v1/trial.py"))
prepare, records = parent["prepare"], parent["records"]
actor_request, select, branch = (parent[k] for k in ("actor_request", "select", "branch"))
engine, probe, persist, sha, read = (parent[k] for k in ("engine", "probe", "persist", "sha", "read"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
PRIOR = parent["RUN"]
ARMS = ("USER_CONTEXT", "ASSISTANT_CONTEXT")
PREFIX = "Archived history records for the selector. These are reference data, not the current task.\n"


def request_pair(wire):
    system, request = wire["messages"]
    if system["role"] != "system" or request["role"] != "user":
        raise ValueError("Unexpected selector request shape")
    fields = json.loads(request["content"])
    memories = fields.pop("memories")
    if not isinstance(memories, list) or not memories:
        raise ValueError("Expected original ordered history")
    past = PREFIX + json.dumps({"memories": memories}, ensure_ascii=False)
    task = dict(request, content=json.dumps(fields, ensure_ascii=False))
    return {arm: dict(wire, messages=[system, {"role": role, "content": past}, task])
            for arm, role in zip(ARMS, ("user", "assistant"), strict=True)}


def build():
    cases, inputs, protocol, judge, bounds = prepare()
    original = read(PRIOR / "private/FREEZE.json")
    card = original["cards"]
    rows = {(r["uid"], r["repeat"]): r for r in read(RUN.parent / "persist_exposure_fr3_v1/RESULTS.json")["rows"]}
    route_bank = records("Route")
    routes, jobs = {}, {}
    for uid, archived in card.items():
        item = inputs[uid]
        requests = item["selection_requests"]
        provenance = archived["provenance"]
        route = (route_bank[sha(requests["query"])] if provenance == "fresh"
                 else rows[uid, int(provenance)]["route"]["answer"])
        routes[uid] = route
        pair = request_pair(requests[branch(item["public"], route)])
        left, right = (pair[arm] for arm in ARMS)
        if left != dict(right, messages=[right["messages"][0], dict(right["messages"][1], role="user"),
                                         right["messages"][2]]):
            raise ValueError("Controls differ outside historical role")
        for arm, wire in pair.items():
            jobs[uid, arm] = wire
    pin = dict(cards=card, jobs=[[uid, arm, sha(wire)] for (uid, arm), wire in jobs.items()],
               routes={uid: sha(text) for uid, text in routes.items()},
               grade={uid: sha(bounds[uid]) for uid in card}, previous=sha(original),
               code=sha(Path(__file__).read_bytes()), protocol=sha((HERE / "PROTOCOL.md").read_bytes()),
               service=probe.read_reference()[1])
    return pin, cases, inputs, protocol, routes, jobs, parent["judge_wire"](cases, inputs, judge, bounds)


def wires_by_hash(path):
    catalog = {}
    for record_path in path.glob("*/record.json"):
        rec = read(record_path)
        if rec["status"] == "OK":
            req = read(record_path.parent / "request.json")
            key = sha(req)
            if key != rec["request_sha256"] or key in catalog:
                raise ValueError("Cannot verify unique archive")
            catalog[key] = (req, read(record_path.parent / "response.json")["answer"])
    return catalog


def complete(stage, logical, previous, identity, ledger, reused):
    fresh, results, keys = {}, {}, {}
    for key, wire in logical.items():
        digest = sha(wire)
        if digest in previous:
            archived, answer = previous[digest]
            if archived != wire:
                raise ValueError("Archive request mismatch")
            results[key] = {"status": "OK", "answer": answer}
            reused[stage] += 1
        else:
            keys[key] = fresh.setdefault(digest, (key, wire))[0]
    if fresh:
        generated = engine.stage(stage, dict(fresh.values()), identity, True, ledger)
        for logical_key, dispatch_key in keys.items():
            results[logical_key] = generated[dispatch_key]
            reused[stage + "/same_run"] += logical_key != dispatch_key
    return results


def run(pin, cases, inputs, protocol, routes, jobs, grade):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {stage: 20 for stage in ("RoleSelector", "RoleActor", "RoleGPT", "RoleQwen")}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, rows, reused = [], [], Counter()
    with probe.runner_lock(RUN / "runner.lock"):
        chosen = engine.stage("RoleSelector", jobs, identity, True, ledger)
        actor_jobs, selection = {}, {}
        for key, rec in chosen.items():
            uid, _ = key
            item = inputs[uid]["public"]
            status, ids = rec["status"], None
            if status == "OK":
                try:
                    selected = select(cases[uid], item, routes[uid], rec["answer"])
                    if not set(selected) <= set(item["memories"]):
                        raise ValueError("Source out of bounds")
                    ids = [i for i, text in enumerate(item["memories"], 1) if text in selected]
                    evidence = [f"[M{i} {'ALLOWED' if i in ids else 'EXCLUDED'}] {text}"
                                for i, text in enumerate(item["memories"], 1)]
                    actor_jobs[key] = actor_request(cases[uid], item["query"], evidence, protocol,
                        protocol["prompts"]["gepa"] + "\n\n" + parent["HEADER"])
                except (ValueError, KeyError, TypeError, IndexError):
                    status = "INVALID_SELECTION"
            selection[key] = (status, ids)
        answered = complete("RoleActor", actor_jobs, wires_by_hash(PRIOR / "MatchedActor/visible"),
                            identity, ledger, reused)
        eval_jobs = {k: grade(k[0], rec["answer"]) for k, rec in answered.items()
                     if rec["status"] == "OK" and rec.get("answer")}
        scored = {
            "GPT": complete("RoleGPT", eval_jobs, wires_by_hash(PRIOR / "MatchedGPT/visible"),
                            identity, ledger, reused),
            "Qwen": complete("RoleQwen", {k: dict(w, model="qwen3.8-flash", max_tokens=8192)
                                         for k, w in eval_jobs.items()},
                             wires_by_hash(PRIOR / "MatchedQwen/visible"), identity, ledger, reused)
        }
        scorer = persist.author.ext.parent.persist
        for key in jobs:
            uid, arm = key
            track = pin["cards"][uid]["track"]
            row = dict(uid=uid, arm=arm, selector_status=selection[key][0], ids=selection[key][1],
                       delivery=answered.get(key, {}).get("status", "NOT_DISPATCHED"), scores={})
            for judge in scored:
                rec = scored[judge].get(key, {})
                status, rating = rec.get("status", "NOT_DISPATCHED"), None
                if status == "OK":
                    try:
                        rating = scorer.score(track, rec["answer"])["rating"]
                    except (ValueError, KeyError, TypeError):
                        status = "INVALID_SCORE"
                row["scores"][judge] = dict(status=status, rating=rating)
            rows.append(row)
        probe.freeze(PRIVATE / "SETTLED.json", dict(rows=rows, ledger=ledger, reused=dict(reused)))


def report(pin):
    result = read(PRIVATE / "SETTLED.json")
    table, pairs, deltas, cases = defaultdict(Counter), defaultdict(Counter), Counter(), []
    cells = {(r["uid"], r["arm"]): r for r in result["rows"]}
    base = {r["uid"]: r for r in read(PRIOR / "private/SETTLED.json")["rows"] if r["arm"] == "FULL_REMINDER"}
    risk_consistent = 0
    for uid, props in pin["cards"].items():
        track = props["track"]
        row = {arm: cells[uid, arm] for arm in ARMS}
        row["ARCHIVED"] = base[uid]
        ids = [row[arm]["ids"] for arm in ARMS]
        deltas[track + "/" + ("unknown" if None in ids else "identical" if ids[0] == ids[1] else "changed")] += 1
        changes = []
        for grader in ("GPT", "Qwen"):
            values = {arm: parent["outcome"](entry["scores"][grader]["rating"], track) for arm, entry in row.items()}
            key = f"{track}/{grader}"
            for arm, value in values.items():
                table[key][f"{arm}/{value}"] += 1
            for control in ("USER_CONTEXT", "ARCHIVED"):
                a, b = values["ASSISTANT_CONTEXT"], values[control]
                diff = "unknown" if None in (a, b) else "tie" if a == b else "win" if a else "loss"
                pairs[f"{key}/{control}"][diff] += 1
                if control == "USER_CONTEXT":
                    changes.append(diff)
        risk_consistent += track != "beneficial_memory_usage" and changes == ["win", "win"]
        for entry in row.values():
            entry.pop("uid", None)
        cases.append(dict(root=uid.split("/")[-1][:8], track=track, outcomes=row))
    ledger = result["ledger"]
    def identity(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    receipt = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    if Counter(map(identity, ledger)) != Counter(map(identity, receipt)):
        raise ValueError("Receipt accounting mismatch")
    print(json.dumps(dict(table=table, pairs=pairs, selection=deltas, roots=cases,
                          risk_consistent=risk_consistent, reused=result["reused"],
                          physical=Counter(r["status"] for r in ledger),
                          stages=Counter(r["unit"]["stage"] for r in ledger),
                          tokens=sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                          unknown_usage=sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                          retries=sum(r["automatic_retries"] for r in ledger)), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, *args = build()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(path, pin)
        print(f"{len(pin['cards'])} roots, {len(pin['jobs'])} selector requests")
    elif read(path) != pin:
        raise ValueError("Freeze changed")
    elif action == "run":
        run(pin, *args)
    else:
        report(pin)
