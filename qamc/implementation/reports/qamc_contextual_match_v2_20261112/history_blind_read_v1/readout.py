"""Summarize locked choices and the frozen archive without making requests."""
from collections import Counter
import json
import re
from pathlib import Path

RUN = Path(__file__).resolve().parents[3] / "runs/qamc_contextual_match_v2_20261112/history_blind_read_v1"
ARMS = ("BASE","FullRead","BlindRead")


def totals(domain, items):
    if domain=="RPEval":
        return {"matches":sum(s["match"]["matched"] for s in items),"positions":sum(s["match"]["positions"] for s in items),
                **{k:sum(s[k] for s in items) for k in ("OPB","UPB","FM")}}
    if domain=="BenchPreS":
        eligible=[d for s in items for d in s["decisions"] if d["appropriate"] and not re.search(r"\bbold\s+text\b",d["preference"],re.I)]
        return {"nonbold_follow":sum(d["label"]=="follow" for d in eligible),"nonbold_eligible":len(eligible)} | {k:sum(s[k] for s in items) for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness")}
    return {"strict_pass":sum(not s["failure_strict_utility"] for s in items)}


def main():
    read=lambda name:json.loads((RUN/name).read_bytes())
    choices=read("CHOICES.json")
    meta=read("ARCHIVE_SCORE_BINDING.json")
    ledger=read("LEDGER.json")
    result={"requests":len(ledger),"tokens_reported":sum((x.get("usage") or {}).get("total_tokens",0) for x in ledger),
            "usage_unknown":sum((x.get("usage") or {}).get("total_tokens") is None for x in ledger),
            "transport":dict(Counter(x["status"] for x in ledger)),"domains":{}}
    for domain in ("RPEval","BenchPreS","PersistBench"):
        cases=[u for u in choices if meta[u]["benchmark"]==domain]
        chosen={u:{"BASE":"BASE",**{a:v["selected"] for a,v in choices[u].items()}} for u in cases}
        common=[u for u in cases if all(meta[u]["scores"][m] for m in chosen[u].values())]
        valid=[u for u in common if all(v["status"]=="OK" for v in choices[u].values())]
        def report(rows):
            return {a:totals(domain,[meta[u]["scores"][chosen[u][a]] for u in rows]) for a in ARMS}
        result["domains"][domain]={"assigned":len(cases),"common":len(common),"both_valid":len(valid),
            "common_totals":report(common),"both_valid_totals":report(valid),
            "different_final_answers":sum(chosen[u]["FullRead"]!=chosen[u]["BlindRead"] for u in cases),
            "statuses":{a:dict(Counter(choices[u][a]["status"] for u in cases)) for a in ARMS[1:]}}
        if domain=="PersistBench":
            result["domains"][domain]["by_track"]={t:report([u for u in common if meta[u]["stratum"]==t]) for t in sorted({meta[u]["stratum"] for u in common})}
    return result


if __name__=="__main__":print(json.dumps(main(),indent=2,sort_keys=True))
