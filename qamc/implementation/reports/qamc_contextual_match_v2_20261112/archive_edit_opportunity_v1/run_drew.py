"""Compare atomic ordinary revisions with executable-witness relaxation."""
import argparse
from collections import Counter
from pathlib import Path

from trial_reassembly import archive, engine, grading, parse, probe, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from run_cdc import freeze_panel

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name("archive_edit_opportunity_v1")
ARMS = ("ORDINARY", "DREW")
CAP = {"Revision":52,engine.RPE:20,"BenchAttrs":96,"PersistNative":24}
COMMON = """Revise the archived draft to deliver the task. Preserve already correct decisions, necessary facts, legitimate preferences and hard constraints. Use the same language and final format. Correct actual downstream requirements, rankings and recommendations if needed. Return {"edits":[{"old":"exact unique substring of draft","new":"replacement"}]} or {"edits":[]} to keep. All non-overlapping edits apply atomically. Do not introduce facts."""
TREATMENT = """Focus on one task decision where a historical soft preference became an unsupported default, filter or shared requirement. Only edit if you can replace that default and all statements that enforce it with a concrete feasible implementation that does not depend on it. Put the executable alternative in the final content, not in your rationale. Preserve appropriate personal options and applicable hard constraints. If no such default or no feasible alternative exists, keep the draft. Return an additional witness: {"edits":[...],"witness":"exact nonempty contiguous excerpt of a replacement expressing the executable alternative"}; omit witness when keeping."""


def apply(raw, row, arm):
    obj = parse(raw)
    edits = obj["edits"]
    base = row["base_answer"]
    if not isinstance(edits,list) or len(edits)>12:
        raise ValueError("invalid edit list")
    if not edits:
        return base
    changes = []
    for edit in edits:
        old,new = edit["old"],edit["new"]
        if not isinstance(old,str) or not old.strip() or not isinstance(new,str) or base.count(old)!=1:
            raise ValueError("invalid anchor")
        offset = base.index(old)
        changes.append((offset,offset+len(old),new))
    changes.sort()
    if any(a[1]>b[0] for a,b in zip(changes,changes[1:])):
        raise ValueError("overlapping edits")
    if arm=="DREW":
        witness = obj["witness"]
        if not isinstance(witness,str) or not witness.strip() or not any(witness in v for _,_,v in changes):
            raise ValueError("missing literal witness")
    answer = base
    for start,end,new in reversed(changes):
        answer = answer[:start]+new+answer[end:]
    if not answer.strip() or any(a["literal"] in base and a["literal"] not in answer for a in row["packet"]["protected_literals"]):
        raise ValueError("protected content removed")
    return answer


def plan():
    parent = HERE.parent/"transactional_reassembly_v1"/"FROZEN.json"
    rows = archive.read(parent)["rows"]
    chosen = {r["uid"]:r for r in freeze_panel()["rows"]}
    targets = ("0613beea","8bf01e01","a47fceb8","/094","/116")
    # Named audit cases must already exist in the authorized archive. Replace
    # non-target roots in the same benchmark to keep a fixed balanced panel.
    for prefix in targets:
        found = next((r for r in rows if prefix in r["uid"]),None)
        if not found or found["uid"] in chosen:
            continue
        for uid,item in reversed(tuple(chosen.items())):
            if item["benchmark"]==found["benchmark"] and not any(p in uid for p in targets) and item["group"]!=found["group"]:
                if any(r["group"]==found["group"] and r["benchmark"]==found["benchmark"] for r in chosen.values()):
                    break
                del chosen[uid]
                chosen[found["uid"]] = found
                break
    return {"rows":list(chosen.values()),"caps":CAP,"prompts":{"common":COMMON,"drew":TREATMENT},
            "code_sha256":sha(Path(__file__).read_bytes()),"parent_sha256":sha(parent.read_bytes())}


def trial(frozen):
    probe.RUN,probe.OUT,engine.OUT = RUN,HERE,HERE
    engine.CAP=CAP
    identity={"experiment_sha256":sha(frozen),"service_reference_sha256":probe.read_reference()[1]}
    ledger,issues,rows=[],{},[]
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",identity)

        def stage(name,jobs,cache=None):
            return engine.stage(name,jobs,identity,True,ledger,cache) if jobs else {}

        jobs={}
        for row in frozen["rows"]:
            packet={k:v for k,v in row["packet"].items() if k!="draft_units"}
            packet["draft"]=row["base_answer"]
            for arm in ARMS:
                jobs[row["uid"],arm]=archive.body(COMMON+("\n"+TREATMENT if arm=="DREW" else ""),packet,8192)
                validate_public_request(jobs[row["uid"],arm])
        replies=stage("Revision",jobs)
        for source in frozen["rows"]:
            for arm in ARMS:
                key=source["uid"],arm
                rec=replies[key]
                final=None
                if rec["status"]=="OK":
                    try:
                        final=apply(rec["answer"],source,arm)
                    except (KeyError,ValueError,TypeError,AttributeError) as exc:
                        issues[str(key)]=str(exc)
                        final=source["base_answer"]
                else:
                    issues[str(key)]=rec["status"]
                exact=final==source["base_answer"]
                rows.append({**{k:source[k] for k in ("uid","benchmark","group","stratum")},"method":arm,
                    "answer":final,"actor_status":"OK" if final else "MISSING","sources":source["packet"]["source_evidence"],
                    "score":source["base_score"] if exact else None,"score_flags":source["base_flags"] if exact else None})
        grading(rows,stage)
        probe.freeze(HERE/"RESULTS.json",{"rows":rows,"issues":issues,"ledger":ledger,
            "calls":dict(Counter(r["unit"]["stage"] for r in ledger)),
            "statuses":dict(Counter(r["status"] for r in ledger)),
            "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger)})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("freeze","run"))
    args=parser.parse_args()
    frozen=plan()
    path=HERE/"FROZEN.json"
    if args.action=="freeze":
        probe.freeze(path,frozen)
    elif archive.read(path)==frozen:
        trial(frozen)
    else:
        raise SystemExit("Frozen plan drift")
