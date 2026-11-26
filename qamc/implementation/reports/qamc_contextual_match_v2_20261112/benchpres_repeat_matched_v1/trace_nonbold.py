"""Join discordant BenchPreS attributes to frozen Actor and Qwen judgment wires."""
import argparse
from collections import Counter, defaultdict
import json
import re

import run_qamc_benchpres_three_draw as run
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import parse_object, sha


WORD = re.compile(r"\b\w+\b")
BOLD = re.compile(r"\bbold\s+text\b", re.I)
CATEGORY_GUIDANCE = {
    "conciseness": ("concise responses", r"concise|brief"),
    "objective information role": ("objective information provider", r"factual|objective"),
}


def response(area, kind, job):
    key = sampling_key(job["unit"])
    r = run.read(area / kind / "outputs" / (key + ".json"))
    if r["unit"] != job["unit"] or sha(job["request"]) != r["request_sha256"] or r["status"] != "OK":
        raise ValueError("Saved answer or judgment does not match the frozen wire")
    return r["answer"] if kind == "generation" else r["response"]["answer"]


def trace(area, expected):
    rows = run.read(area / "RESULTS.json")
    paired = defaultdict(dict)
    refs = {(r["uid"], r["method"], r["replicate"]): r for r in rows if r["score"]}
    for (uid, method, rep), r in refs.items():
        if (uid, method, rep) not in expected:
            raise ValueError("Unallocated response")
        paired[uid, rep][method] = r["score"]["decisions"]
    manifests = {}
    for kind, name in (("generation", "ACTOR"), ("grading", "JUDGE")):
        manifest = run.read(area / f"{name}_MANIFEST.json")
        manifests[kind] = {(j["unit"]["root_id"], j["unit"]["method"],
                            j["unit"]["replicate"], j["unit"]["stage"]): j for j in manifest["units"]}
    actors, judges = manifests["generation"], manifests["grading"]
    counts, out = Counter(), []
    for (uid, rep), pair in sorted(paired.items()):
        if set(pair) != set(run.METHODS):
            continue
        counts["common_task_draw_pairs"] += 1
        left, right = (pair[arm] for arm in run.METHODS)
        for i, (one, two) in enumerate(zip(left, right, strict=True)):
            pref = one["preference"]
            if pref != two["preference"] or one["appropriate"] != two["appropriate"]:
                raise ValueError("Paired evaluation attributes changed")
            if not one["appropriate"] or BOLD.search(pref):
                continue
            counts["common_nonbold_appropriate_positions"] += 1
            if one["label"] == two["label"]:
                continue
            direction = "GATE_ONLY" if one["label"] == "follow" else "SELECTIVITY_ONLY"
            counts[direction] += 1
            category, signal = next(((k, pat) for k, (phrase, pat) in CATEGORY_GUIDANCE.items()
                                     if phrase in pref.casefold()), ("other", None))
            case = {"category": category, "draw": rep, "direction": direction}
            for arm, decision in zip(run.METHODS, (one, two), strict=True):
                actor = actors[uid, arm, rep, "Actor"]
                answer = response(area, "generation", actor)
                judge = judges[uid, arm, rep, f"BenchAttr{i}"]
                packet = json.loads(judge["request"]["messages"][-1]["content"])
                if (packet["preference"] != pref or packet["response"] != answer
                        or parse_object(response(area, "grading", judge))["label"] != decision["label"]):
                    raise ValueError("Actor, Judge input, and result are not aligned")
                idx = "gate" if arm == run.GATE else "selectivity"
                case[idx + "_word_count"] = len(WORD.findall(answer))
                case[idx + "_label"] = decision["label"]
                if arm == run.GATE and signal:
                    inputs = json.loads(actor["request"]["messages"][-1]["content"])
                    case["gate_guidance_mentions_attribute"] = any(
                        re.search(signal, r["use_instruction"], re.I) is not None
                        for r in inputs["selected_memory_use_guidance"])
            out.append(case)
    return {"counts": counts, "discordant": out}


def readout(wave=0):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")
    expected = {(uid, m, i) for uid in plan["waves"][wave] for m in run.METHODS for i in run.REPEATS}
    return trace(run.RUN / f"wave-{wave}", expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, choices=range(6), default=0)
    args = parser.parse_args()
    print(json.dumps(readout(args.wave), indent=2, sort_keys=True))
