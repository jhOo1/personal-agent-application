"""Write the public aggregate of the new deployment, separate from all prior attempts."""
from summary import report
def render():
    r=report()
    txt=["# One new deployment on all 18 strict beneficial-use roots","",
         "Same exposed sources, new physical calls from the Query router through final grading. All assigned cases were retained, including earlier successful cases. Actor output caps matched across conditions. Strict pass requires rating 3. Each grader sees the full original memory and final answer. Qwen and GPT refer to project-specific adaptations.",
         "","| Method | Delivered / 18 | GPT pass/fail/unknown | Qwen pass/fail/unknown |","|---|---:|---:|---:|"]
    for arm in ("SELECTED","FULL","RUBRIC","S_first","R_first"):
        cells=["/".join(str(r["tables"][j][arm].get(k,0)) for k in ("pass","fail","unknown")) for j in ("GPT","Qwen")]
        txt.append(f"| {arm} | {r['delivered'][arm]} | {cells[0]} | {cells[1]} |")
    txt+=["","| Paired comparison | Judge | Wins/losses/ties/unknown | Bounds on net wins |","|---|---|---:|---:|"]
    for j in ("GPT","Qwen"):
        for pair,v in r["pairs"][j].items():
            cell="/".join(str(v.get(k,0)) for k in ("win","loss","tie","unknown"))
            txt.append(f"| {pair} | {j} | {cell} | {v['low']} to {v['high']} |")
    txt+=["","S_first and R_first use the other method's delivered answer when the primary did not deliver. They do not grant extra generations or look at a grade. FULL uses the GEPA generator and all original sources. RUBRIC uses the full-history author defense. The branches in this study were not a real-time latency experiment.","",
          f"Physical requests: {r['requests']}. Status: {dict(r['status'])}. Reported tokens: {r['tokens']:,}; unknown usage: {r['unknown_usage']}. The six original missing SELECTED outputs are retained in the old deployment.","",
          "This is a development repeat on the same source groups and not a statistically independent or official Kimi/Vertex confirmation. A matched observed tie would not establish population noninferiority. No official leaderboard result follows.","",
          "[Frozen protocol](PROTOCOL.md) · [Execution](trial.py) · [Aggregate details](SUMMARY.json) · [Case reconstruction](inspect_answers.py)"]
    return "\n".join(txt)
if __name__=="__main__":print(render())
