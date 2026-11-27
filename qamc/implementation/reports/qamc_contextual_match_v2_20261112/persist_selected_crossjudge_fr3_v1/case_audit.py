"""Private root-level pairing for checking concrete behaviors in saved final answers."""
from collections import defaultdict
import json
from settle import RUN,outcome

def examples():
    rows=json.loads((RUN/"private/RESULTS.json").read_text())["rows"]
    roots=defaultdict(lambda:defaultdict(list))
    for r in rows:roots[(r["track"],r["uid"])][r["arm"]].append(r)
    for (track,uid),arms in sorted(roots.items()):
        contrasts=[]
        for judge in ("old","qwen"):
            s,b=(outcome(arms[a],track,judge) for a in ("SELECTED","RUBRIC"))
            contrasts.append(None if s is None or b is None else int(b)-int(s))
        if len(set(contrasts))>1 or contrasts==[1,1] or contrasts==[-1,-1]:
            ratings={a:{f:[r[f] for r in sorted(v,key=lambda x:x["repeat"])] for f in ("old","qwen")} for a,v in arms.items()}
            print(uid,track,contrasts,json.dumps(ratings))
if __name__=="__main__":examples()
