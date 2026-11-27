"""Historical context for observed induction failures. Never substitute old scores."""
from collections import Counter, defaultdict
import json
from competition import BU, HERE, OUT, RUN, author_module, author_wire, inputs, read, sha


def compare():
    _, cases, tasks = inputs()
    mod = author_module()
    base = HERE.parent / "native_residual_v1/persist_memadapter_alignment_v1"
    archived = {r["uid"]:r for r in read(base/"RESULTS.json")["rows"]}
    report = {}
    for draw in range(1,4):
        directory = RUN/f"D{draw}MA1"
        if not (OUT/f"D{draw}MA1_MANIFEST.json").exists():
            continue
        records = {r["request_sha256"]:r for r in
                   (read(p) for p in (directory/"visible").glob("*/record.json"))}
        counts = defaultdict(Counter)
        for uid, task in tasks.items():
            track=cases[uid]["category"]
            if draw>1 and track==BU:
                continue
            status=records.get(sha(author_wire(mod,task,1)),{}).get("status")
            if status!="KNOWN_LENGTH_FAILURE":
                continue
            old=archived[uid]
            assert old["category"]==track
            score=old["score"]
            group=counts[track]
            group["length_failures"]+=1
            group["archived_answers"]+=bool(old["answer"])
            if score is None:
                group["old_grade_missing"]+=1
            else:
                assert old["answer"]
                failed=score["failure_strict_utility" if track==BU else "failure_release"]
                group["archived_fail" if failed else "archived_pass"]+=1
        report[draw]=counts
    return report


if __name__=="__main__":
    print(json.dumps(compare(),indent=2))
