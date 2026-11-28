"""Inspect the benchmark headroom of an already verified good action."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
crossed = run_path(str(BASE / "ipe_c_crossed_judge_v1/trial.py"))
old = crossed["old"]
probe, engine, read, sha = old.probe, old.engine, crossed["read"], old.sha
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("SOURCE_SPECIFIC", "GENERIC_SPECIFIC")
SCORES = {"GPT": "gpt-4.1", "QWEN": "qwen3.8-flash"}

# Hand-specified diagnostic edits. They never participate in the deployed method.
EDIT = {
    "12a39042622bc3e41711": {
        "GPT": ("选择温暖的色调和舒适的材质",
                "选择温暖、舒适的底色，再用暖橘抱枕或鹅黄地毯作一处小面积亮色点缀",
                "选择温暖、舒适的底色，再用燕麦色抱枕或米白地毯作一处小面积材质点缀"),
        "QWEN": ("加一块床边地毯",
                 "加一块带暖橘或鹅黄点缀的床边地毯",
                 "加一块燕麦色或米白色的床边地毯"),
    },
    "implicit/020": {
        "GPT": ("有表演和互动活动，园区宽敞，适合家庭游。",
                "有表演和互动活动，园区宽敞，适合家庭游；如当天有合适场次，可选一项当地民俗表演或皮影体验。",
                "有表演和互动活动，园区宽敞，适合家庭游；如当天有合适场次，可选一项园林导览或亲子游园体验。"),
        "QWEN": ("看灯光、散步、吃小吃即可，不建议安排太满。",
                 "看灯光、散步即可；若当天有合适的民俗活动，可以选糖画、捏面人或皮影的一项体验，不建议安排太满。",
                 "看灯光、散步即可；若当天有合适的游览活动，可以选步行导览、拍夜景或看水景的一项体验，不建议安排太满。"),
    },
    "implicit/043": {
        "GPT": ("放松音乐（钢琴曲、轻音乐等）",
                "放松音乐（例如 Yiruma《River Flows in You》、德彪西《月光》或押尾桑《黄昏》）",
                "放松音乐（例如舒曼《梦幻曲》、萨蒂《第一号吉诺佩迪》或巴赫《G弦上的咏叹调》）"),
        "QWEN": ("睡前播客、慢读、安静电台、治愈系电台",
                 "睡前播客、慢读、安静电台；想听轻柔器乐时，可选 Yiruma《River Flows in You》、德彪西《月光》或押尾桑《黄昏》",
                 "睡前播客、慢读、安静电台；想听轻柔器乐时，可选舒曼《梦幻曲》、萨蒂《第一号吉诺佩迪》或巴赫《G弦上的咏叹调》"),
    },
}


def prepare():
    _, cards, original = crossed["build"]()
    parent = read(old.v41.formal.OUT / "PLAN.json")
    cases = old.v41.author_cases(parent)
    roster, jobs = {}, {}
    for uid, c in cards.items():
        matched = [key for key in EDIT if uid.endswith("/" + key)]
        if not matched:
            continue
        key, = matched
        if any(c["branch"][model] != "TASK_ONLY" for model in EDIT[key]):
            raise ValueError("Candidate no longer matches the observed IPE-C task-only path")
        roster[uid] = c
        for model, edits in EDIT[key].items():
            draft, ref_key = c["cells"][model, "TASK_ONLY"]
            anchor, *replacements = edits
            if draft.count(anchor) != 1:
                raise ValueError("Expected one exact original substring")
            wire = old.engine.rpe_wire(parent, cases[uid], {"uid": uid, "actor_status": "OK", "answer": draft})
            if dict(wire, model="qwen3.8-flash") != original[ref_key]:
                raise ValueError("The reference grading request changed")
            for arm, text in zip(ARMS, replacements, strict=True):
                answer = draft.replace(anchor, text, 1)
                edited = old.engine.rpe_wire(parent, cases[uid], {"uid": uid, "actor_status": "OK", "answer": answer})
                if {k: v for k, v in edited.items() if k != "messages"} != {k: v for k, v in wire.items() if k != "messages"}:
                    raise ValueError("Grading configuration differs")
                for grader, alias in SCORES.items():
                    jobs[uid, f"{grader}/{model}/{arm}"] = {"wire": dict(edited, model=alias), "answer": answer}
    assert len(roster) == 3 and len(jobs) == 24
    frozen = {"wires": [[*key, sha(item["wire"])] for key, item in jobs.items()],
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
              "service": probe.read_reference()[1]}
    return frozen, roster, jobs


def run(pin, roster, jobs):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {f"Oracle{grader}": 12 for grader in SCORES}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, rows = [], []
    with probe.runner_lock(RUN / "runner.lock"):
        for grader in SCORES:
            requested = {k: v["wire"] for k, v in jobs.items() if k[1].startswith(grader + "/")}
            scored = engine.stage(f"Oracle{grader}", requested, identity, True, ledger)
            for (uid, tag), rec in scored.items():
                _, model, arm = tag.split("/")
                answer = jobs[uid, tag]["answer"]
                score = old.score_of(uid, arm, rec, {"answer": answer}, roster[uid]["labels"])
                rows.append({"uid": uid, "grader": grader, "generator": model, "arm": arm, "score": score})
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "ledger": ledger})


def report(roster):
    data = read(PRIVATE / "RESULTS.json")
    base_q = read(crossed["PRIVATE"] / "RESULTS.json")
    previous = {(r["uid"], r["generator"], r["arm"]): r["rating"] for r in base_q["rows"]}
    scores = {(r["uid"], r["grader"], r["generator"], r["arm"]): r["score"] for r in data["rows"]}
    table, outcomes = defaultdict(Counter), []
    for uid, card in roster.items():
        for grader in SCORES:
            for model in EDIT[next(key for key in EDIT if uid.endswith("/" + key))]:
                if grader == "GPT":
                    base = card["saved"][model]["TASK_ONLY"]
                else:
                    base = previous[uid, model, "TASK_ONLY"]
                cells = {"BASE": base, **{a: scores[uid, grader, model, a] for a in ARMS}}
                outcome = {"root": "/".join(uid.split("/")[-2:]), "grader": grader, "generator": model, "metrics": {}}
                if not all(cell["grade"].get("match") for cell in cells.values()):
                    table[f"{grader}/{model}/missing"]["tasks"] += 1
                    outcome["status"] = "INCOMPLETE"
                else:
                    for arm, cell in cells.items():
                        g = cell["grade"]
                        m = g["match"]
                        if m["positions"] != len(card["labels"]):
                            raise ValueError("Position mismatch")
                        c = table[f"{grader}/{model}/{arm}"]
                        c.update(tasks=1, positions=m["positions"], Match=m["matched"])
                        observed = {"match": m["matched"], "positions": m["positions"], "flags": cell["flags"]}
                        for name in ("OPB", "UPB", "FM"):
                            if name in g:
                                c[name] += g[name]
                                observed[name] = g[name]
                        outcome["metrics"][arm] = observed
                outcomes.append(outcome)
    ledger = data["ledger"]
    records = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def identity(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(identity, records)) != Counter(map(identity, ledger)):
        raise ValueError("Physical receipts differ")
    print(json.dumps({"metrics": table, "per_case": outcomes, "physical": Counter(r["status"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    frozen, roster, jobs = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(marker, frozen)
        print("Fixed action roots", len(roster), "new scorer requests", len(jobs))
    elif read(marker) != frozen:
        raise ValueError("Frozen identity changed")
    elif action == "run":
        run(frozen, roster, jobs)
    else:
        report(roster)
