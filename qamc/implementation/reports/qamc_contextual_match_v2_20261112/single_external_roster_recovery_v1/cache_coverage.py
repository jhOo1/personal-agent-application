"""Count exact development cache hits across both workspaces, without dispatch."""
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import subprocess

from wires import ROOT, LEGACY, PublicTask, Memory, read, key, roster, sha, text_request, judge_prompt, load_rubrics
from qamc.contextual_match.memadapter_bridge import MemAdapterBridge


def archive_paths():
    paths = set()
    for root in (ROOT, LEGACY.parent):
        cmd = ["rg", "--files", "--no-ignore", "--hidden", "-g", "samples.sqlite", "-g", "ledger.sqlite"]
        for term in ("seal", "reserv", "holdout", "heldout", "confirm"):
            cmd.extend(["-g", "!**/*" + term + "*/**"])
        paths.update((root / n).resolve() for n in subprocess.check_output(
            cmd + ["runs", "reports"], cwd=root, text=True).splitlines())
    return sorted(paths)


def search(wires, paths):
    by_sha = {sha(w): w for w in wires.values()}
    hits = defaultdict(list)
    if not by_sha:
        return {}
    params = ",".join("?" for _ in by_sha)
    for p in paths:
        with closing(sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)) as db:
            if p.name == "samples.sqlite":
                if "request_sha" not in {r[1] for r in db.execute("pragma table_info(samples)")}:
                    continue
                for h, req, res, status in db.execute(
                        f"select request_sha,request_json,response_json,status from samples where request_sha in ({params})", tuple(by_sha)):
                    assert json.loads(req) == by_sha[h]
                    hits[h].append(json.loads(res).get("answer") if res and status == "COMPLETE" else None)
            else:
                if "payload_sha" not in {r[1] for r in db.execute("pragma table_info(requests)")}:
                    continue
                for h, raw in db.execute(f"select payload_sha,data from requests where payload_sha in ({params})", tuple(by_sha)):
                    r = json.loads(raw)
                    if r.get("status") != "ok" or not r.get("request_path") or not r.get("response_path"):
                        hits[h].append(None)
                        continue
                    req, res = (p.parent / r[k] for k in ("request_path", "response_path"))
                    assert read(req) == by_sha[h]
                    hits[h].append(read(res).get("answer"))
    return {k: hits[sha(w)] for k,w in wires.items() if sha(w) in hits}


def main():
    verified = roster()[-1]
    bridge = MemAdapterBridge(ROOT / "literature/qamc_contextual_match_20261111/MemAdapter")
    rubrics = load_rubrics(ROOT / "literature/qamc_pa_v1/RPEval/prompts/prompts_715.py")
    tasks, wires = {}, {}
    for row in read(LEGACY / "qamc_des2gen/ALL_NINE_CASE_DETAILS.json"):
        c = row["case"]
        if c["benchmark"] != "rpeval" or key(c) not in verified:
            continue
        v = row["original_public_input"]
        t = PublicTask(v["uid"], v["query"], tuple(Memory(m["memory_id"],m["text"],tuple(map(tuple,m["ranges"])))
                       for m in v["memories"]),v["current_context"],tuple(v["fixed_facts"]))
        tasks[t.uid] = t
        wires[t.uid,"Stage1"] = bridge.request(t,"Stage1")
        ref = read(LEGACY.parent / c["evaluation_path"])
        for m in ("RPR_PAPER_XBENCH","D2G_PAPER_ADAPT"):
            ans = row["methods"][m]["answer"]
            if ans:
                wires[t.uid,m] = text_request("Evaluate the completed answer using the supplied benchmark rubric. Return JSON.",
                                              judge_prompt(rubrics,ref,ans,False),"qwen3.8-flash",8192)
    paths = archive_paths()
    summary = {}
    for stage in ("Stage1","Stage2","Stage3"):
        hits = search(wires,paths)
        next_wires = {}
        for (uid,k), w in wires.items():
            stats = summary.setdefault(k,Counter())
            stats["requested"] += 1
            answers = {a for a in hits.get((uid,k),[]) if isinstance(a,str) and a.strip()}
            stats["any_receipt"] += (uid,k) in hits
            stats["unique_successful_answer"] += len(answers)==1
            if k == stage and len(answers)==1 and stage != "Stage3":
                try:
                    view = bridge.parse(tasks[uid],stage,answers.pop())
                except (ValueError,TypeError,KeyError):
                    stats["invalid_structure"] += 1
                    continue
                nxt = "Stage2" if stage=="Stage1" else "Stage3"
                next_wires[uid,nxt] = bridge.request(tasks[uid],nxt,view)
        wires = next_wires
    return {"databases":dict(Counter(p.name for p in paths)), "coverage":summary}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
