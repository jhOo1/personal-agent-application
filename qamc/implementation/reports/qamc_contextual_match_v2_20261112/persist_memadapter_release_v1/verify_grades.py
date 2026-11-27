"""Join each actual answer to both registered Judge messages; never dispatch."""
import json
from collections import Counter
from case_answers import assemble, PREFIXES
from competition import BU, OUT, inputs, persist, read, sha
from exposure_audit import receipts, stage_manifest


def verify(draw):
    roster,cases,tasks=inputs()
    ids={u.split("/")[-1][:8]:u for u,c in cases.items() if draw==1 or c["category"]!=BU}
    assert len(ids)==(29 if draw==1 else 9)
    entries=assemble(draw,cases,tasks,set(ids))
    scorer=persist.author.ext.parent.persist
    _,rubrics,formatter=scorer.upstream()
    j=roster["protocols"]["gpt41"]
    jobs=(("GPT",j["model"],j["stages"][persist.STAGE]["max_tokens"]),("Qwen","qwen3.8-flash",8192))
    summary={}
    drawfile=OUT/f"DRAW_{draw}.json"
    settled={(r["uid"],r["arm"]):r for r in read(drawfile)["rows"]} if drawfile.exists() else {}
    for label,model,cap in jobs:
        stage=f"D{draw}{label}"
        if not (OUT/(stage+"_MANIFEST.json")).exists():
            continue
        manifest=stage_manifest(stage)
        bank=receipts(stage)
        seen=set()
        status=Counter()
        casescores={}
        for prefix,entry in entries.items():
            uid=ids[prefix]
            track=cases[uid]["category"]
            for arm,cell in entry["arms"].items():
                rating=None
                if cell["status"]=="OK" and cell["answer"]:
                    payload=formatter["build_judge_prompt"](entry["memories"],entry["query"],cell["answer"])
                    wire=persist.author.ext.text_request(rubrics[track],payload,model,cap)
                    key=sha(wire)
                    if manifest.get(key)!=wire:
                        raise ValueError("Physical Judge request does not match original data and delivered answer")
                    seen.add(key)
                    result,raw=bank.get(key,("awaiting",None))
                    if result=="OK":
                        try:
                            rating=scorer.score(track,raw)["rating"]
                        except (TypeError,ValueError,KeyError):
                            result="INVALID_GRADE"
                    status[result]+=1
                else:
                    status["NO_ANSWER"]+=1
                if settled:
                    assert settled[uid,arm][label]==rating
                if prefix in PREFIXES or track=="cross_domain":
                    casescores.setdefault(prefix,{})[arm]=rating
        assert seen==set(manifest)
        summary[label]=dict(distinct_grading_wires=len(seen),logical=status,case_ratings=casescores)
    return dict(settled=bool(settled),judges=summary)


if __name__=="__main__":
    print(json.dumps({d:verify(d) for d in (1,2,3) if (OUT/f"D{d}GPT_MANIFEST.json").exists()},indent=2))
