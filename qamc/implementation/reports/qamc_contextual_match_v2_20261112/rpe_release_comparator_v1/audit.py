"""Verify released Actor input construction and prior short-grader outcomes without dispatch."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
AUTHOR=HERE.parents[2]/"literature/qamc_pa_v1/RPEval"
REV="0f8bce80a03e6b86426485264b14ae7de49cc8f9"

def pinned(path):
    return subprocess.check_output(["git","-C",str(AUTHOR),"show",f"{REV}:{path}"]).decode()

def audit():
    src=pinned("generation_task/eval_multi.py")
    f=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=="evaluate_generated_response")
    persona=next(n.value for n in f.body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=="persona")
    assert ast.unparse(persona)=="item['persona']"
    code=next(n for n in ast.walk(f) if isinstance(n,ast.Call) and ast.unparse(n.func)=="RPA_multi_generation_template.format")
    assert {k.arg:ast.unparse(k.value) for k in code.keywords}=={"personas":"persona","question":"question","intent":"pred_policy"}
    bindings={n.targets[0].id:n.value for n in ast.parse(pinned("prompts_715.py")).body
              if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
    template=next(k.value.id for k in bindings["RPA_multi_generation_template"].keywords if k.arg=="template")
    fmt=ast.literal_eval(bindings[template])
    checks={}
    for track in ("explicit","implicit"):
        cases=json.loads(pinned(f"benchmark_dataset/{track}_preference/multi_testset.json"))
        counts=Counter()
        for row in cases:
            memory=row["persona"]
            kwargs=dict(personas=memory,question=row["question"])
            counts["rows"]+=1
            counts["actor_invariant_to_policy"]+=fmt.format(**kwargs,intent="A"*len(memory))==fmt.format(**kwargs,intent="C"*len(memory))
            if track=="implicit":
                counts["actor_uses_different_source_than_project"]+=memory!=row["implicit_persona"]
        checks[track]=dict(counts)
    old=json.loads((BASE/"rpeval_released_judge_bridge_v1/RESULTS.json").read_text())
    scores=[row["published"][m] for row in old["rows"] for m in ("RPR_PAPER_FULL","TASK_ONLY")]
    keys=("OPB","UPB","RII","FM","VG","Judge")
    return dict(release=REV,actor_template_sha256=hashlib.sha256(fmt.encode()).hexdigest(),
                input_checks=checks,old_judge_calls=old["calls"],old_reported_tokens=old["tokens"],
                complete_numeric_outputs=sum(all(type(s[k]) in (float,int) for k in keys) for s in scores),
                match_present=sum(s["unexpected_match"] is not None for s in scores),
                whole_match_present=sum(s["unexpected_full_match"] is not None for s in scores),
                totals={k:old["summary"][k]["totals"] for k in ("OPB","UPB","FM")})

if __name__=="__main__":print(json.dumps(audit(),indent=2))
