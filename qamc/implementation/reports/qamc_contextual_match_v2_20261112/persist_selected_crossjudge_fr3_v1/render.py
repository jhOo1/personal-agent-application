"""Present the frozen analysis without dropping incomplete source groups."""
from settle import compare
def render():
    r=compare()
    lines=["# SELECTED versus author RUBRIC under two fixed-answer graders","",
           "49 exposed source groups; 206 available original answers, 222 assigned method/deployment positions. Risk tasks have three deployments; a single observed failing grade makes the root fail. Strict beneficial use requires one grade of 3. Missing generations and grades remain unknown. Both scoring models use adaptations of the author rubric.","",
           "| Track | Judge | SELECTED pass/fail/unknown | RUBRIC pass/fail/unknown | Paired wins/losses/ties/unknown |",
           "|---|---|---:|---:|---:|"]
    for track,t in r["tables"].items():
        for f,name in (("old","GPT-4.1"),("qwen","Qwen")):
            def counts(x,keys):return "/".join(str(x.get(k,0)) for k in keys)
            arms=[counts(t["assigned"][f+"/"+arm],("pass","fail","unknown")) for arm in ("SELECTED","RUBRIC")]
            pair=counts(t["paired"][f],("win","loss","tie","unknown"))
            lines.append(f"| {track} | {name} | {arms[0]} | {arms[1]} | {pair} |")
    lines+=["","| Track, complete for both methods and judges | Roots | Net wins, GPT-4.1 | Net wins, Qwen | Both judges favor SELECTED | Both favor RUBRIC |","|---|---:|---:|---:|---:|---:|"]
    for track,t in r["tables"].items():
        b=t["both_judges"]
        lines.append(f"| {track} | {b['paired']} | {b['old_net']} | {b['qwen_net']} | {b['same_win']} | {b['same_loss']} |")
    lines+=["","Sensitivity bounds on net root wins, allowing either grader independently by root (same grader for both methods) and every assignment for missing outcomes:"]
    for track,t in r["tables"].items():
        b=t["both_judges"]
        lines.append(f"- {track}: {b['conservative_low']} to {b['conservative_high']}.")
    lines+=["","These are worst-case bounds rather than confidence intervals.","",f"New Judge dispatches: {r['calls']}. Status counts: {dict(r['status'])}. Reported tokens: {r['tokens']:,}; unknown usage: {r['unknown_usage']}. No new Actor generations.","",
            "Neither judge establishes an official Inspect Kimi/Vertex score. A second grader evaluates the same answers and does not provide a second set of independent generations. These exposed roots do not establish generalization or a leaderboard ranking.","","[Protocol](PROTOCOL.md) · [Wire reconstruction and dispatch](trial.py) · [Aggregation](settle.py) · [Detailed counts](SUMMARY.json)"]
    return "\n".join(lines)
if __name__=="__main__":print(render())
