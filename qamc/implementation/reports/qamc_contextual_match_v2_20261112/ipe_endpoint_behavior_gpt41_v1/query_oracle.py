"""Replay archived scores with one hindsight endpoint per identical task request."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ipe_c_rate_matched_controls_v1"))
from audit_rate import FULL, ZERO, blocks, load, score

rows, _ = load()
print("# Same-request endpoint oracle on exposed RPEval answers\n")
print("|Panel|Tasks|Positions|Request groups|Reversals|Task only|Full history|IPE-C|Query-only oracle|Per-task oracle|IPE-C groups above/equal/below query oracle|")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
for clean in (False, True):
    panel = [r for r in rows if r["clean"] or not clean]
    groups = blocks(panel, lambda r:r["wire"])
    above = equal = below = oracle = flips = task = full = route = perfect = 0
    for inds in groups:
        pair = [(score(panel[i], ZERO, "Match"), score(panel[i], FULL, "Match")) for i in inds]
        t, f = map(sum, zip(*pair))
        actual = sum(score(panel[i], panel[i]["base"], "Match") for i in inds)
        best = max(t,f)
        task += t
        full += f
        route += actual
        oracle += best
        perfect += sum(max(x) for x in pair)
        above += actual > best
        equal += actual == best
        below += actual < best
        flips += any(a>b for a,b in pair) and any(a<b for a,b in pair)
    print(f"|{'Both endpoints unflagged' if clean else 'All'}|{len(panel)}|{sum(r['positions'] for r in panel)}|{len(groups)}|{flips}|{task}|{full}|{route}|{oracle}|{perfect}|{above}/{equal}/{below}|")
print("\nGroups use the archived task-only request hash. Reversals require strict score advantages for opposite endpoints within one group. Both oracles read final scores, giving retrospective ceilings on these saved answers. Singletons are included; their group oracle always wins or ties. Differences mix endpoint behavior, generation variability and grader sensitivity. These are project-adapted Match scores, not an independent confirmation or evidence of behavioral causality.")
