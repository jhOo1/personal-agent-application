"""Freeze and grade two already-exposed IPE-C endpoints using the shared blind runner."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from qamc.common import canonical, sha

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
sys.path[:0] = [str(REPORTS / p) for p in ("archive_answer_frontier_v1/blind",
                                             "all_a_visibility_score_probe_v1")]
import review

RUN = review.formal.ROOT / "runs" / REPORTS.name / HERE.name
RP, TASK = "RPR_PAPER_FULL", "TASK_ONLY"
OFF = {"REUSE_ORIGINAL_TASK_ONLY_STATE", "REUSE_DRAFT", "NEW_DRAFT"}
PROMPT = review.PROMPT.replace('No holistic rank.', '''No holistic rank.
Also add a "requirements" field and a "facts" field to each answer.
Requirements checks concrete conflicts with directly applicable explicit requirements in
the task or history. Facts checks material unsupported specifics asserted as true.
Each field is {"status":"CLEAR|VIOLATION|UNKNOWN","quote":""}. Quote an exact answer
span for a violation and use an empty quote otherwise. A proposal or explicit
conditional is not an assertion. Use UNKNOWN when applicability or the real task
state cannot be established. The example below omits these two additional fields.''')
BASE = REPORTS / "rpeval_formal_multi_coverage_v1"
FILES = (REPORTS / "ipe_c_two_endpoint_completion_v1/RESULTS.json",
         BASE / "RESULT_ROWS.json", BASE / "PLAN.json")


def prepare(fingerprint):
    data, archive, plan = map(review.read, FILES)
    cases = {r["uid"]: r for r in plan["cases"]}
    if len(cases) != 300 or any(c["independent_confirmation"] is not False for c in cases.values()):
        raise ValueError("Expected only the original exposed development plan")
    rows = [r for r in data["rows"] if all(x["grade"].get("match") for x in r["scores"].values())]
    if len(rows) != 274 or len({r["uid"] for r in rows}) != 274:
        raise ValueError("Unexpected three-endpoint coverage")
    buckets = defaultdict(list)
    for row in rows:
        route = row["old_route"]
        if route != "REUSE_RP" and route not in OFF:
            raise ValueError("Unknown route in scored panel")
        uid, labels = row["uid"], row["labels"]
        if cases[uid]["analysis_group_id"] != row["source_group"] or not labels or set(labels) - set("ABC"):
            raise ValueError("Invalid source/label binding")
        s = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        buckets[s, route == "REUSE_RP"].append(row)

    archived = {r["uid"]: r for r in archive if r["method"] == RP}
    packets, used = {}, set()
    bucket_size = lambda key: len({r["source_group"] for r in buckets[key]})
    for stratum, on in sorted(buckets, key=lambda key: (bucket_size(key), key)):
        selected = 0
        for row in sorted(buckets[stratum, on], key=lambda r: sha(["endpoint-blind-v1", r["uid"]])):
            uid, group = row["uid"], row["source_group"]
            if group in used:
                continue
            original = archived[uid]
            actor = original["actor_request"]
            if original["actor_status"] != "OK" or sha(actor) != original["actor_request_sha256"]:
                raise ValueError("History Actor identity mismatch")
            answers = {RP: original["answer"], TASK: row["no_history_state"]["answer"]}
            for method, answer in answers.items():
                if not answer or sha(answer) != row["controls"][method]["answer_sha256"]:
                    raise ValueError(f"Archived answer identity mismatch: {uid}/{method}")
            selected_method = RP if on else TASK
            if sha(answers[selected_method]) != row["ipe_c"]["answer_sha256"]:
                raise ValueError("Archived IPE-C route changed")
            source = json.loads(actor["messages"][1]["content"])
            memories = [{"id": m["memory_id"], "text": m["text"]} for m in source["source_evidence"]]
            labels = dict(zip((m["id"] for m in memories), row["labels"], strict=True))
            if len(labels) != len(memories):
                raise ValueError("Duplicate memory ID")
            order = sorted(answers, key=lambda method: sha(["side-v1", uid, method]))
            sides = dict(zip(("V1", "V2"), order, strict=True))
            inputs = {k: source[k] for k in ("query", "current_context", "facts")}
            inputs.update(memories=memories, answers={k: answers[m] for k, m in sides.items()})
            wire = {"model": "gpt-6.1-sol", "stream": True, "messages": [
                {"role": "system", "content": PROMPT}, {"role": "user", "content": canonical(inputs)}]}
            packets[sha(["endpoint-review", uid])] = {
                "uid": uid, "group": group, "stratum": stratum, "ipe": selected_method,
                "sides": sides, "labels": labels, "original": TASK, "alternative": RP,
                "wire": wire, "wire_sha256": sha(wire),
            }
            used.add(group)
            selected += 1
            if selected == 4:
                break
    if len(packets) != review.CAP or len({p["wire_sha256"] for p in packets.values()}) != review.CAP:
        raise ValueError("Frozen sample size or uniqueness changed")
    return {"packets": packets, "source_pins": {p.parent.name + "/" + p.name: sha(p.read_bytes())
                                                  for p in (*FILES, Path(__file__), HERE / "PROTOCOL.md")},
            "service_reference_sha256": fingerprint, "max_physical_requests": review.CAP,
            "automatic_retries": 0}


def validator(base):
    def check(vote, wire):
        base({k: {n: x for n, x in v.items() if n not in ("requirements", "facts")}
              for k, v in vote.items()}, wire)
        answers = json.loads(wire["messages"][1]["content"])["answers"]
        for side, value in vote.items():
            for field in ("requirements", "facts"):
                item = value[field]
                if (item.keys() != {"status", "quote"} or item["status"] not in {"CLEAR", "VIOLATION", "UNKNOWN"}
                        or not isinstance(item["quote"], str)
                        or (item["status"] == "VIOLATION" and
                            (not item["quote"].strip() or item["quote"] not in answers[side]))
                        or (item["status"] != "VIOLATION" and item["quote"])):
                    raise ValueError("Invalid protection assessment")
    return check


def match(label, behavior):
    if behavior == "UNKNOWN" or (label in "BC" and behavior == "TASK_JUSTIFIED"):
        return None
    return behavior == {"A": "NONE", "B": "SOFT", "C": "REQUIRED"}[label] or (
        label == "A" and behavior == "TASK_JUSTIFIED")


def summarize(results):
    cards = defaultdict(Counter)
    pairs = defaultdict(Counter)
    for row in results["reviews"]:
        for key in ("all", row["stratum"], row["ipe"]):
            cards[key]["allocated_tasks"] += 1
            answers = row["assessment"]
            if not answers:
                continue
            cards[key]["valid_tasks"] += 1
            local = Counter()
            for mid, label in row["labels"].items():
                values = {m: answers[m]["uses"][mid]["effect"] for m in (TASK, RP)}
                a, b = (match(label, values[m]) for m in (TASK, RP))
                if a is None or b is None:
                    local[f"unknown_{label}"] += 1
                    continue
                local[f"paired_{label}"] += 1
                hits = {TASK: a, RP: b}
                for name, arm in ((TASK, TASK), (RP, RP), ("IPE_C", row["ipe"])):
                    local[f"{name}_match_{label}"] += hits[arm]
                    if label == "A":
                        local[f"{name}_applied_A"] += values[arm] in {"SOFT", "REQUIRED"}
            for name, arm in ((TASK, TASK), (RP, RP), ("IPE_C", row["ipe"])):
                for f in ("completion", "requirements", "facts"):
                    value = answers[arm][f]
                    local[f"{name}_{f}_{value if isinstance(value,str) else value['status']}"] += 1
            cards[key].update(local)
            if any(local[f"paired_{label}"] for label in "ABC"):
                ipe = sum(local[f"IPE_C_match_{label}"] for label in "ABC")
                for m in (TASK, RP):
                    delta = ipe - sum(local[f"{m}_match_{label}"] for label in "ABC")
                    pairs[key][f"{m}_{'win' if delta > 0 else 'loss' if delta < 0 else 'tie'}"] += 1
    return {"cards": cards, "paired_task_outcomes": pairs,
            "accounting": {k: v for k, v in results.items() if k != "reviews"}}


if __name__ == "__main__":
    review.OUT = review.RUN = RUN
    review.CAP = 22
    review.prepare = prepare
    review.check_vote = validator(review.check_vote)
    if sys.argv[1:] == ["summarize"]:
        print(json.dumps(summarize(review.read(RUN / "RESULTS.json")), indent=2))
    else:
        review.main()
