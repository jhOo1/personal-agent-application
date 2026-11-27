"""Post-run sensitivity over every assigned group; no calls and no score imputation."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs/qamc_contextual_match_v2_20261112"
PARENT = RUNS / "single_external_memadapter_v1"
RUN = RUNS / "single_external_veto_comparison_v1"
RP, D2G, MA = "RPR_PAPER_FULL", "DES2GEN_FULL", "MEMADAPTER_FULL"


def read(path):
    return json.loads(path.read_bytes())


def value(score):
    if score is None:
        return (0,1)
    if score["total"] != 1 or score["matched"] not in (0,1):
        raise ValueError("Single-preference scoring contract changed")
    return (score["matched"],)*2


def compare(rows, choices, other):
    outcomes = Counter()
    lower = upper = 0
    for uid, row in rows.items():
        selected = choices.get(uid,{})
        a = selected.get("V1",{}).get("method", RP)
        b = selected.get("Default",{}).get("method", RP) if other=="Default" else other
        assert row["V1"] == row[a] and row[other] == row[b]
        if a == b:
            outcomes["same_candidate"] += 1
            continue
        if b == MA and uid not in choices:
            outcomes["comparator_candidate_missing"] += 1
        alo,ahi = value(row[a])
        blo,bhi = value(row[b])
        lower += alo - bhi
        upper += ahi - blo
        if alo==ahi and blo==bhi:
            outcomes[{1:"different_win",0:"different_tie",-1:"different_loss"}[alo-blo]] += 1
        else:
            outcomes["different_score_unknown"] += 1
    return {"assigned":len(rows),"observations":dict(outcomes),"possible_net_match":[lower,upper]}


def main():
    rows = read(RUN/"SCORES.json")
    choices = read(RUN/"LOCKED_CHOICES.json")
    assert set(rows)==set(read(PARENT/"FROZEN.json")["inputs"])
    assert set(choices)==set(read(PARENT/"Stage3_OUTPUT.json"))
    return {"scope":"all allocated development sources, frozen fallback when unavailable",
            "v1_against":{name:compare(rows,choices,name) for name in (RP,D2G,MA,"Default")}}


if __name__=="__main__":
    print(json.dumps(main(),indent=2,sort_keys=True))
