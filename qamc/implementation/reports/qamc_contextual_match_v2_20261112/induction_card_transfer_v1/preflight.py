"""Rebuild Stage 1 from public task inputs and match saved replies, offline only."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import qamc_rpeval_formal_multi_run as formal
from qamc.contextual_match.memadapter_bridge import AUTHOR_COMMIT, MemAdapterBridge, git_blob

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=HERE.parents[2]
REPO=ROOT/"literature/qamc_contextual_match_20261111/MemAdapter"
ABLATION="methods/memadapter/ablations/prompts/stage1_then_baseline_generation.txt"


def inspect():
    bridge=MemAdapterBridge(REPO)
    text=git_blob(REPO,ABLATION)
    system,template=text.decode().split("USER PROMPT TEMPLATE")
    assert system.strip().startswith("SYSTEM PROMPT") and all(
        "{{"+x+"}}" in template for x in ("CURRENT_QUERY","RETRIEVED_MEMORIES","MEMORY_BOUNDARY_CARDS"))
    frozen=json.loads((ROOT/"runs"/BASE.name/"shared_history_activation_v1/private/FROZEN.json").read_text())
    panel={u for u in frozen["assignments"] if u.startswith("rpeval/")}
    all_rows=json.loads((formal.OUT/"RESULT_ROWS.json").read_text())
    rows={r["uid"]:r for r in all_rows if r["method"]=="MEMADAPTER_FULL"}
    groups={"all_formal":Counter(),"shared_exposed_panel":Counter()}
    for u,r in rows.items():
        counts=[groups["all_formal"]]
        if u in panel:counts.append(groups["shared_exposed_panel"])
        for c in counts:c["archived_rows"]+=1
        task=formal.task_for({"uid":u})
        req=(r.get("reader_requests") or {}).get("MemInduction")
        if not req:continue
        assert req==bridge.request(task,"Stage1")
        for c in counts:c["original_stage1_wire_verified"]+=1
        raw=r["reader_responses"].get("MemInduction")
        if not raw:continue
        try: cards=bridge.parse(task,"Stage1",raw)
        except (ValueError,TypeError,KeyError):continue
        if cards!=r.get("memory_boundary_cards"):raise ValueError("Card mismatch")
        if r["reader_requests"].get("MemReflection"):
            assert r["reader_requests"]["MemReflection"]==bridge.request(task,"Stage2",cards)
        for c in counts:
            c["reusable_stage1"]+=1
            c["cards"]+=len(cards["memory_boundary_cards"])
            c["with_full_method_answer"]+=int(r["actor_status"]=="OK")
    assert len(panel)==18
    # A union of archives is not assumed; rows absent from the named archive stay missing.
    return {"source_commit":AUTHOR_COMMIT,"author_baseline_prompt_sha256":hashlib.sha256(text).hexdigest(),
            "panel_assigned":len(panel),"counts":groups}

if __name__=="__main__":print(json.dumps(inspect(),indent=2))
