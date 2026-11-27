"""Compare complete author prompts with the previous deployment without new calls."""
from collections import Counter
import json

from competition import HERE, author_module, inputs, read, sha
from qamc.contextual_match.memadapter_bridge import AUTHOR_COMMIT, PROMPT_FILES


def audit():
    mod=author_module()
    _,cases,tasks=inputs()
    source=read(HERE.parent/"paper_baseline_validation_156_v1/RESULT_ROWS.json")
    archive={r["uid"]:r for r in source if r["method"]=="MEMADAPTER_FULL" and r["benchmark"]=="persistbench"}
    assert len(archive)==60 and set(cases)<=set(archive)
    counts=Counter()
    for uid in cases:
        row=archive[uid]
        wire=row.get("actor_request")
        counts["allocated"]+=1
        if not wire:
            counts["missing_archived_actor_wire"]+=1
            continue
        assert sha(wire)==row["actor_request_sha256"]
        prev=row["memory_use_instructions"]
        ids=[x["memory_id"] for x in prev["memory_use_instructions"]]
        task=tasks[uid]
        assert len(ids)==len(task["memories"])
        memories=[dict(memory_id=i,memory_text=t) for i,t in zip(ids,task["memories"])]
        system,template=mod.load_prompt_parts(PROMPT_FILES["Stage3"])
        body=mod.render_prompt(template,mod.build_stage3_input(current_query=task["query"],memories=memories,use_instructions=prev))
        counts["system_matches"]+=system==wire["messages"][0]["content"]
        counts["user_matches_with_old_ids_and_instructions"]+=body==wire["messages"][1]["content"]
        counts["same_source_id_scheme"]+=ids==[f"memory_{i:02d}" for i in range(1,len(ids)+1)]
        counts["old_cap_4096"]+=wire["max_tokens"]==4096
        counts["delivered_archived_answer"]+=bool(row.get("answer"))
    return {"archived_author_commit":AUTHOR_COMMIT,"counts":dict(counts)}

if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
