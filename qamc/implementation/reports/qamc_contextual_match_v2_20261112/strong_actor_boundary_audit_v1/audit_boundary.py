"""Run a blind semantic audit on verified exposed source/answer pairs."""
import json
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from qamc.common import canonical, parse_object, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request

from census import actor_row, normalized, prior, read, transfer

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
engine, probe = prior.engine, prior.probe
STAGE = "BoundaryReview"


def rpe_rows(census):
    arch = prior.R["archived"].v41
    roots = {row["uid"]: row for row in read(arch.OUT / "FROZEN.json")["roots"]}
    official = read(arch.formal.OUT / "RESULT_ROWS.json")
    orig = {(r["uid"], r["method"]): r for r in official if r["actor_status"] == "OK" and r.get("answer")}
    selected, used = [], set()
    for tag in ("B", "C"):
        n = 0
        candidates = [r for r in census["roots"] if r["route"] == "RPR_PAPER_FULL" and
                      any(t["author_label"] == tag and t["state"] in ("VISIBLE_B","VISIBLE_C")
                          for t in r["positions"])]
        for card in sorted(candidates, key=lambda r: (
                tag == "B" and r["stratum"] != "B_only", sha([HERE.name,tag,r["uid"]]))):
            uid, group = card["uid"], card["group"]
            if group in used:
                continue
            base = actor_row(orig[uid,"RPR_PAPER_FULL"])
            other = orig.get((uid,"GEPA_SELECTED_BOUNDS"))
            if not other:
                continue
            actor_row(other)
            target = next(t for t in card["positions"] if t["author_label"] == tag
                          and t["state"] in ("VISIBLE_B","VISIBLE_C"))
            decoy = next((t for t in card["positions"] if t["author_label"] == "A"
                          and t["state"].startswith("VISIBLE")), None)
            source_map = {s["memory_id"]: s["text"] for s in roots[uid]["original_sources"]}
            targets = [{"id":f"T{k+1}","text":source_map[t["id"]],"role": "FOCAL" if t == target else "DECOY",
                        "author_type": t["author_label"], "source_status": t["state"]}
                       for k,t in enumerate(sorted([t for t in (target,decoy) if t],
                                                   key=lambda p: sha([uid,p["id"]])))]
            selected.append({"uid":uid,"group":group,"benchmark":"RPEval","task":roots[uid]["public_task"],
                             "targets":targets,"answers":{"BASE":base["answer"],"OTHER":other["answer"]}})
            used.add(group)
            n += 1
            if n == 8:
                break
    return selected


def bench_rows(census):
    cases, _, _ = transfer.context("BenchPreS")
    index = {(r["uid"],r["method"]):r for r in transfer.archived_answers("BenchPreS",cases)
             if r["actor_status"] == "OK" and r.get("answer")}
    by_uid = defaultdict(list)
    for item in census["attributes"]:
        if item["base_follow"] != "follow" and item["expression"] == "SELECTED_EXACT":
            by_uid[item["uid"]].append(item)
    rows = []
    for uid, selected in sorted(by_uid.items()):
        base = actor_row(index[uid,"GEPA_SELECTED_BOUNDS"])
        second = index.get((uid,"PAPER_SELECTIVITY"))
        wire = json.loads(base["actor_request"]["messages"][1]["content"])
        targets = []
        for k,n in enumerate(selected):
            original = next(s for s in base["input_audit"]["compiled_original_texts_in_author_order"]
                            if normalized(n["preference"]) in normalized(s))
            targets.append({"id":f"T{k+1}","text":original,"role":"FOCAL",
                            "source_status": n["expression"], "native_fields": n["comparators"]})
        answers = {"BASE":base["answer"]}
        if second and second.get("actor_request"):
            answers["OTHER"] = actor_row(second)["answer"]
        rows.append({"uid":uid,"group":selected[0]["profile_group"],"benchmark":"BenchPreS",
                     "task":{k:wire[k] for k in ("query","current_context","fixed_facts")},
                     "targets":targets,"answers":answers})
    return rows


def prepare():
    sources = read(HERE / "CENSUS.json")
    rows = rpe_rows(sources["RPEval"]) + bench_rows(sources["BenchPreS"])
    jobs = {}
    for r in rows:
        uid = r["uid"]
        methods = sorted(r["answers"],key=lambda m:sha(["order",uid,m]))
        r["blind"] = dict(zip("XY",methods))
        data = {"task":r["task"],"targets":[{k:t[k] for k in ("id","text")} for t in r["targets"]],
                "answers":{s:r["answers"][m] for s,m in r["blind"].items()}}
        wire = {"model":"gpt-4.1","temperature":0,"max_tokens":4096,"stream":True,
                "stream_options":{"include_usage":True},"messages":[
                    {"role":"system","content":(HERE/"JUDGE.txt").read_text()},
                    {"role":"user","content":canonical(data)}]}
        validate_public_request(wire)
        jobs[uid,"BLIND"] = wire
    pin = {"sources":sha(sources),"rows":rows,"jobs":{u:sha(j) for (u,_),j in jobs.items()},
           "code":{name:sha((HERE/name).read_bytes()) for name in
                   ("audit_boundary.py","census.py","JUDGE.txt","PROTOCOL.md")}}
    return pin, jobs


def parse(raw, case):
    obj = parse_object(raw)
    if set(obj) != {"targets"} or not isinstance(obj["targets"], list):
        raise ValueError("Bad review envelope")
    targets, seen = {t["id"] for t in case["targets"]}, set()
    for row in obj["targets"]:
        if set(row) != {"id","applicability","decision","answers"} or row["id"] not in targets - seen:
            raise ValueError("Bad target identity")
        seen.add(row["id"])
        if row["applicability"] not in ("APPLIES","NOT_APPLICABLE","UNCERTAIN") or not row["decision"]:
            raise ValueError("Bad scope judgment")
        if set(row["answers"]) != case["blind"].keys():
            raise ValueError("Wrong review slots")
        for slot, value in row["answers"].items():
            if set(value) != {"status","quote"} or value["status"] not in (
                    "REALIZED","OMITTED","OVERAPPLIED","NOT_NEEDED","UNCERTAIN"):
                raise ValueError("Bad answer state")
            q = value["quote"]
            if not isinstance(q,str) or (q and q not in case["answers"][case["blind"][slot]]):
                raise ValueError("Nonverbatim evidence")
            if value["status"] in ("REALIZED","OVERAPPLIED") and not q:
                raise ValueError("Missing positive evidence")
    if targets != seen:
        raise ValueError("Incomplete target coverage")
    return obj["targets"]


def run(action):
    pin, requests = prepare()
    out = HERE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(out,pin)
        print(Counter(r["benchmark"] for r in pin["rows"]),flush=True)
        return
    if read(out) != pin:
        raise ValueError("Blind review freeze drift")
    probe.OUT = engine.OUT = HERE
    probe.RUN = engine.RUN.with_name(HERE.name)
    engine.CAP = {STAGE:len(requests)}
    live, ledger = action == "run", []
    identity = {"experiment_sha256":sha(pin),"service_reference_sha256":probe.read_reference()[1]}
    observed = []
    with probe.runner_lock(probe.RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",identity)
        receipts = engine.stage(STAGE,requests,identity,live,ledger)
        for case in pin["rows"]:
            uid = case["uid"]
            reply = receipts[uid,"BLIND"]
            row = {"uid":uid,"benchmark":case["benchmark"],"receipt":reply,"review":None}
            observed.append(row)
            if reply["status"] != "OK":
                continue
            try:
                row["review"] = parse(reply["answer"],case)
            except (ValueError,TypeError,KeyError) as e:
                row["error"] = str(e)
    result = {"rows":observed,"ledger":ledger,"requests":len(ledger),
              "statuses":Counter(r["status"] for r in ledger),
              "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
              "unknown_usage":sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
    if live:
        probe.freeze(HERE/"RESULTS.json",result)
    elif read(HERE/"RESULTS.json") != result:
        raise ValueError("Blind review replay drift")
    print({k:result[k] for k in ("requests","tokens","statuses")},flush=True)


if __name__ == "__main__":
    cli = ArgumentParser()
    cli.add_argument("action",choices=("freeze","run","replay"))
    run(cli.parse_args().action)
