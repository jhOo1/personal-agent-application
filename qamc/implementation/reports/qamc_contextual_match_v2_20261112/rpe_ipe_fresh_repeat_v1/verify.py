"""Check physical repetition and compute symmetric grader-flag sensitivity."""
from collections import Counter
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[2] / "runs" / here.parent.name / here.name


def read(path):
    return json.loads(path.read_text())


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


ids = set()
output = []
by_repeat = []
for rep in (1, 2):
    folder = out / f"deployment{rep}"
    settled = read(folder / "RESULTS.json")
    roots = {r["uid"]:r for r in settled["rows"]}
    by_repeat.append(roots)
    expected = Counter((r["unit"]["stage"], r["request_sha256"], r["status"]) for r in settled["ledger"])
    found = Counter()
    missing_id = 0
    stage_times = {}
    for stage in ("Estimate", "Actor", "Judge"):
        manifest = read(folder / "private" / f"{stage}_MANIFEST.json")
        intended = {digest(row["request"]) for row in manifest["units"]}
        observed = set()
        times = []
        for p in (folder / stage / "visible").glob("*/record.json"):
            record = read(p)
            assert record["automatic_retries"] == 0
            h = record["request_sha256"]
            assert h == digest(read(p.with_name("request.json")))
            observed.add(h)
            found[stage,h,record["status"]] += 1
            times.append(record["started_unix"])
            if record["status"] == "OK":
                rid = read(p.with_name("response.json")).get("id")
                if rid:
                    assert rid not in ids, "Physical response identifier reused"
                    ids.add(rid)
                else:
                    missing_id += 1
        assert intended == observed
        stage_times[stage] = min(times)
    assert found == expected
    assert stage_times["Estimate"] < stage_times["Actor"] < stage_times["Judge"]
    output.append(dict(deployment=rep, receipts=sum(found.values()), missing_response_ids=missing_id))
assert set(by_repeat[0]) == set(by_repeat[1])
for row,roots in zip(output, by_repeat):
    for name, predicate in (("all_complete",lambda s: True),("both_flag_free",lambda s: s["flags"] == [])):
        cells=[r for r in roots.values() if r["branch"] and all(s["grade"].get("match") and predicate(s) for s in r["scores"].values())]
        table={}
        for method in ("RP_FULL","TASK_ONLY","IPE_C"):
            scores=[r["scores"][r["branch"] if method=="IPE_C" else method]["grade"]["match"] for r in cells]
            table[method]=dict(match=sum(m["matched"] for m in scores),positions=sum(m["positions"] for m in scores),
                               whole=sum(m["matched"]==m["positions"] for m in scores))
        row[name]=dict(roots=len(cells),methods=table)
(here / "VERIFICATION.json").write_text(json.dumps(dict(unique_nonempty_response_ids=len(ids),deployments=output),indent=2)+"\n")
