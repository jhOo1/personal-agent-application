"""Reuse the frozen score/answer alignment and examine profile concentration."""
from collections import defaultdict
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
import runpy
from statistics import mean

here=Path(__file__).resolve().parent
prior=here.parent/"bench_external_joint_v1"
with redirect_stdout(StringIO()) as captured:
    data=runpy.run_path(str(prior/"compare.py"))
assert json.loads(captured.getvalue())==json.loads((prior/"RESULTS.json").read_text())
cells,panel,gate,passed,aligned=(data[k] for k in ("cells","panel","gate","passed","aligned"))
methods=[gate,*sorted(data["results"])]
groups={u:r["group"] for u,r in panel.items()}
assert len(methods)==5 and len(set(groups.values()))==10

def comparable(u, names):
    c=cells[u]
    if any(n not in c for n in names): return False
    attrs={tuple(tuple(x) for x in c[n][1]) for n in names}
    if len(attrs)!=1 or not aligned({n:c[n][0] for n in names},names): return False
    return all(c[a][2]!=c[b][2] or c[a][0]==c[b][0] for a in names for b in names)

def profile_summary(ids,method):
    by_group=defaultdict(list)
    for uid in ids:
        a,b=cells[uid][gate][0],cells[uid][method][0]
        by_group[groups[uid]].append(int(passed(a,False))-int(passed(b,False)))
    rates=[mean(v) for v in by_group.values()]
    net=[sum(v) for v in by_group.values()]
    leave=[mean(rates[:i]+rates[i+1:]) for i in range(len(rates))]
    return [len(ids),len(net),sum(n>0 for n in net),sum(n==0 for n in net),sum(n<0 for n in net),
            f"{100*mean(rates):+.1f}",f"{100*min(leave):+.1f} to {100*max(leave):+.1f}"]

common=[u for u in panel if comparable(u,methods)]
print("# BenchPreS profile-level external comparison\n")
print(f"Common complete panel: {len(common)}/{len(panel)} tasks, {len(set(groups[u] for u in common))} profiles. Existing adapted Qwen scores.\n")
print("|Method|AAR|MR|Completeness sum / tasks|Joint passes / tasks|\n|---|---:|---:|---:|---:|")
for name in methods:
    v=[cells[u][name][0] for u in common]
    def ratio(a,b):return f"{sum(x[a] for x in v)}/{sum(x[b] for x in v)}"
    print(f"|{name}|{ratio('primary','positions')}|{ratio('MR','MR_denominator')}|{sum(x['completeness'] for x in v)}/{len(v)}|{sum(passed(x,False) for x in v)}/{len(v)}|")
for scope in ("Pairwise eligible","Common five-method panel"):
    print(f"\n## {scope}\n")
    print("|Gate minus comparator|Tasks|Profiles|Positive|Zero|Negative|Profile-equal gap (pp)|Omit-one-profile range (pp)|\n|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in methods[1:]:
        ids=[u for u in panel if comparable(u,(gate,m))] if scope.startswith("Pairwise") else common
        if scope.startswith("Pairwise"):assert len(ids)==data["results"][m]["counts"]["paired"]
        print("|"+"|".join(map(str,[m,*profile_summary(ids,m)]))+"|")

print("\n## All 48 assigned tasks, worst-case missing outcomes\n")
print("|Comparator|Net joint passes, min to max|Profile-equal gap, min to max (pp)|\n|---|---:|---:|")
for m in methods[1:]:
    by_profile=defaultdict(list)
    for uid in panel:
        c=cells[uid]
        if gate in c and m in c and not comparable(uid,(gate,m)):
            bounds=(-1,1)
        else:
            a=[int(passed(c[gate][0],False))] if gate in c else [0,1]
            b=[int(passed(c[m][0],False))] if m in c else [0,1]
            bounds=(min(a)-max(b),max(a)-min(b))
        by_profile[groups[uid]].append(bounds)
    net=[sum(v[i] for values in by_profile.values() for v in values) for i in (0,1)]
    macro=[100*mean(mean(v[i] for v in values) for values in by_profile.values()) for i in (0,1)]
    print(f"|{m}|{net[0]:+d} to {net[1]:+d}|{macro[0]:+.1f} to {macro[1]:+.1f}|")
