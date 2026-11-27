"""Endpoint-only diagnostic on the existing 216-case common archive."""
from collections import Counter
import json
from score import BASE, read


def summarize(rows, stratum, exclude_flags):
    counts=Counter()
    roots=set()
    for row in rows:
        if row["stratum"]!=stratum:continue
        cells=row["cells"]
        ends=[cells[k] for k in ("RPR_PAPER_FULL","TASK_ONLY")]
        if exclude_flags and any(e["flags"] for e in ends):continue
        assert row["base"] in ("RPR_PAPER_FULL","TASK_ONLY")
        base=cells[row["base"]]["matched"]
        gain=max(e["matched"] for e in ends)-base
        counts.update(tasks=1,positions=row["positions"],ipe_c=base,possible_extra_match=gain,
                      tasks_with_any_headroom=int(gain>0))
        if gain:roots.add(row["source_group"])
    return {**counts,"groups_with_any_headroom":len(roots)}


if __name__=="__main__":
    rows=read(BASE/"selective_path_frontier_v1/RESULTS.json")["rows"]
    assert len({r["uid"] for r in rows})==len(rows)==216
    print(json.dumps({s:{k:summarize(rows,s,clean) for k,clean in (("all",False),("neither_endpoint_flagged",True))}
                      for s in ("all_A","B_only","contains_C")},indent=2))
