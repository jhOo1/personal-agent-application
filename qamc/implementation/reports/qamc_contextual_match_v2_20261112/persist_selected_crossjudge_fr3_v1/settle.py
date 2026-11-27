"""Compare failure-at-three and strict beneficial use without filling missing grades."""
import json
from pathlib import Path
from collections import defaultdict, Counter

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/"runs"/HERE.parent.name/HERE.name
def outcome(rows, track, field):
    values=[r[field] for r in rows]
    if track=="beneficial_memory_usage":
        assert len(values)==1
        return None if values[0] is None else values[0]!=3
    assert len(values)==3
    if any(x is not None and x>=3 for x in values):return True
    return None if None in values else False

def compare():
    data=json.loads((RUN/"private/RESULTS.json").read_text())
    tracks=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for r in data["rows"]:tracks[r["track"]][r["uid"]][r["arm"]].append(r)
    tables={}
    for track,roots in tracks.items():
        assigned=defaultdict(Counter); paired=defaultdict(Counter); both=Counter()
        for arms in roots.values():
            deltas={}
            intervals=[]
            for field in ("old","qwen"):
                fail={m:outcome(v,track,field) for m,v in arms.items()}
                for arm,f in fail.items():
                    assigned[field+"/"+arm]["unknown" if f is None else "fail" if f else "pass"]+=1
                s,b=fail["SELECTED"],fail["RUBRIC"]
                possibilities=[int(right)-int(left) for left in ((True,False) if s is None else (s,))
                               for right in ((True,False) if b is None else (b,))]
                intervals.append((min(possibilities),max(possibilities)))
                if s is None or b is None:
                    paired[field]["unknown"]+=1
                else:
                    delta=int(b)-int(s)
                    deltas[field]=delta
                    paired[field]["win" if delta>0 else "loss" if delta<0 else "tie"]+=1
            both["conservative_low"]+=min(lo for lo,hi in intervals)
            both["conservative_high"]+=max(hi for lo,hi in intervals)
            if len(deltas)==2:
                both["paired"]+=1
                for field,n in deltas.items():both[field+"_net"]+=n
                if deltas["old"]==deltas["qwen"]:
                    n=deltas["old"];both["same_win" if n>0 else "same_loss" if n<0 else "same_tie"]+=1
                else:both["different_direction_or_tie"]+=1
        tables[track]=dict(assigned=assigned,paired=paired,both_judges=both)
    ledger=data["ledger"]
    return dict(tables=tables,calls=len(ledger),status=Counter(x["status"] for x in ledger),
                tokens=sum((x["usage"] or {}).get("total_tokens",0) for x in ledger),
                unknown_usage=sum((x["usage"] or {}).get("total_tokens") is None for x in ledger))
if __name__=="__main__":print(json.dumps(compare(),indent=2))
