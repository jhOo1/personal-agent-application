"""Compose already completed parallel answers by delivery status; never route on scores."""
import json
from collections import Counter, defaultdict
from pathlib import Path

base = Path(__file__).resolve().parents[3] / "runs/qamc_contextual_match_v2_20261112"
def rows(name):
    return json.loads((base/name).read_text())["rows"]

def delivered(cell):
    actor = cell["actor"] or {}
    return actor.get("status") == "OK" and bool(actor.get("answer"))

def endpoint(grades, track):
    if any(g is not None and (g != 3 if track=="beneficial_memory_usage" else g>=3) for g in grades):
        return "fail"
    return "unknown" if None in grades else "pass"

panel=rows("persist_exposure_fr3_v1/RESULTS.json")
extra=rows("persist_selected_crossjudge_fr3_v1/private/RESULTS.json")
lookup={(r["uid"],r["repeat"],r["arm"]):r for r in extra}
assert len(panel)==111 and len(lookup)==len(extra)==222
groups=defaultdict(list)
fallbacks=Counter()
for r in panel:
    arms=r["methods"]
    choice="SELECTED" if delivered(arms["SELECTED"]) else "RUBRIC"
    if choice=="RUBRIC":
        upstream=(r["route"] or {}).get("status")!="OK"
        fallbacks[r["track"],"route" if upstream else "actor",delivered(arms[choice])]+=1
    groups[r["track"],r["uid"]].append((r,choice))

print("# Existing-answer fallback on infrastructure failure\n")
print("One common policy across tracks: take the selected-evidence Actor response if delivered, otherwise serve the archived parallel RUBRIC response when available. Never switch on the judge, numeric rating, track, UID, or perceived answer quality. This offline policy assumes both responses are available at serving time. An unknown original delivery remains recorded.\n")
print("|Track|Judge|Roots|Selected pass/fail/unknown|Fallback pass/fail/unknown|Rubric pass/fail/unknown|Rubric-first backup pass/fail/unknown|Selected-first vs rubric-first wins/losses/ties/unknown|")
print("|---|---|---:|---|---|---|---|---|")
for judge in ("old","qwen"):
    stats=defaultdict(Counter)
    for (track,uid),items in groups.items():
        assert sorted(r["repeat"] for r,_ in items)==([1] if track=="beneficial_memory_usage" else [1,2,3])
        grades=defaultdict(list)
        for r,choice in items:
            for arm in ("SELECTED","RUBRIC"):
                cell=r["methods"][arm]
                check=lookup[uid,r["repeat"],arm]
                assert check["old"]==(cell["score"]["rating"] if cell["score"] else None)
                assert bool(check["wire"]) == delivered(cell) and check["track"] == track
                assert delivered(cell) or check[judge] is None
                grades[arm].append(check[judge])
                reverse = "RUBRIC" if delivered(r["methods"]["RUBRIC"]) else "SELECTED"
                if arm==reverse:
                    grades["REVERSE"].append(check[judge])
                if arm==choice:
                    grades["BACKUP"].append(check[judge])
        states={a:endpoint(v,track) for a,v in grades.items()}
        for a,state in states.items():
            stats[track][a,state]+=1
        b,s=states["REVERSE"],states["BACKUP"]
        result="unknown" if "unknown" in (s,b) else ("tie" if s==b else ("win" if s=="pass" else "loss"))
        stats[track]["pair",result]+=1
    for t,c in sorted(stats.items()):
        cols=["/".join(str(c[a,s]) for s in ("pass","fail","unknown")) for a in ("SELECTED","BACKUP","RUBRIC","REVERSE")]
        pair="/".join(str(c["pair",v]) for v in ("win","loss","tie","unknown"))
        print("|"+"|".join([t,judge,str(sum(c["pair",v] for v in ("win","loss","tie","unknown"))),*cols,pair])+"|")
print("\nFallback activations (track, failed stage, archived backup delivered, deployments):\n")
for (track,stage,ok),n in sorted(fallbacks.items()):
    print(f"- {track}, {stage}, {ok}: {n}")
print("\nNo new calls. This simulation uses a second previously generated response, whose inference cost remains part of the system. It does not measure sequential retry success, latency, intrinsic beneficial-use performance of SELECTED on missing responses, or official Kimi grades.")
