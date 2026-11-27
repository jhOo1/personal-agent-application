"""Census scored, actually executed source changes in explicit development manifests."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from residual_memory_delta import Entry, difference
from qamc.common import sha

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
NATIVE = REPORTS / "native_residual_v1"
RUNS = REPORTS.parents[1] / "runs" / REPORTS.name
OPEN, CLOSE = "<memories>\n", "\n</memories>"


def read(path):
    return json.loads(path.read_bytes())


def verified_manifests(*paths):
    wires = {}
    for path in paths:
        for row in read(path)["units"]:
            unit = row["unit"]
            key = (unit["root_id"], unit["method"])
            if wires.setdefault(key, row["request"]) != row["request"]:
                raise ValueError("One archive address has incompatible Actor requests")
    return wires


def state(wire, *, keep_policy=False):
    """Extract a structural state while retaining all other request fields."""
    fixed = deepcopy(wire)
    system, user = fixed["messages"]
    if (system["role"], user["role"]) != ("system", "user"):
        raise ValueError("Unexpected Actor roles")
    if OPEN in system["content"]:
        head, _, tail = system["content"].partition(OPEN)
        content, marker, rest = tail.partition(CLOSE)
        if not marker or OPEN in tail or CLOSE in rest:
            raise ValueError("Ambiguous memory block")
        lines = content.splitlines()
        if any(not line.startswith("- ") or len(line) == 2 for line in lines):
            raise ValueError("Memory items cannot be identified as original rows")
        ids = tuple(sha(line[2:]) for line in lines)
        system["content"] = head + OPEN + CLOSE + rest
        return fixed, tuple(Entry(i) for i in ids), dict(zip(ids, lines, strict=True))
    packet = json.loads(user["content"])
    raw_sources = packet.pop("source_evidence")
    sources = {r["memory_id"]: r for r in raw_sources}
    if len(raw_sources) != len(sources):
        raise ValueError("Ambiguous source IDs")
    raw_use = packet.get("preference_use_policy")
    use = {} if raw_use is None else {r["memory_id"]: r["policy"] for r in raw_use}
    if raw_use is not None and len(use) != len(raw_use):
        raise ValueError("Repeated usage policy")
    if raw_use is not None and not keep_policy:
        packet["preference_use_policy"] = [r for r in raw_use if r["memory_id"] not in sources]
    user["content"] = packet
    return fixed, tuple(Entry(key, use.get(key)) for key in sources), sources


def native(benchmark, score):
    if not score:
        return None
    if benchmark == "RPEval":
        match = score.get("match")
        if match and all(score.get(k) is not None for k in ("OPB", "UPB", "FM")):
            return (match["matched"], match["positions"], score["OPB"], score["UPB"], score["FM"])
    elif benchmark == "BenchPreS":
        keys = ("aar_numerator", "aar_denominator", "mr_numerator", "task_completeness", "mr_denominator")
        if all(score.get(k) is not None for k in keys):
            return tuple(score[k] for k in keys)
    elif score.get("failure_release") is not None and score.get("failure_strict_utility") is not None:
        return not score["failure_release"], not score["failure_strict_utility"]
    return None


def protected(benchmark, before, after):
    if benchmark == "RPEval":
        return after[1] == before[1] and all(a <= b for a, b in zip(after[2:], before[2:], strict=True))
    if benchmark == "BenchPreS":
        return (after[1] == before[1] and after[4] == before[4]
                and after[2] <= before[2] and after[3] >= before[3])
    return after[1] >= before[1]


def pairs(index, reference, alternatives):
    for uid in sorted(index):
        base = index[uid].get(reference)
        if base is None:
            continue
        for arm in alternatives:
            if arm in index[uid]:
                yield base, index[uid][arm]


def rows_for(path, manifest_paths, *, benchmark=None, wave=None):
    wires = verified_manifests(*manifest_paths)
    by_uid = defaultdict(dict)
    for r in read(path)["rows"]:
        if wave is not None and r["wave"] != wave:
            continue
        key = (r["uid"], r.get("method", r.get("arm")))
        wire = wires.get(key)
        if wire is None:
            continue
        if r.get("actor_request_sha256", r.get("actor_sha256", sha(wire))) != sha(wire):
            raise ValueError("Actor result does not match its manifest")
        b = benchmark or r["benchmark"]
        status = r.get("actor_status", r.get("status"))
        by_uid[key[0]][key[1]] = {"wire": wire, "benchmark": b, "row": r, "key": key,
                                 "score": native(b, r.get("score")) if status == "OK" else None}
    return by_uid


def rpe_original():
    valid_case = {r["uid"] for r in read(REPORTS / "rpeval_formal_multi_coverage_v1/PLAN.json")["cases"]
                  if r.get("independent_confirmation") is False}
    path = REPORTS / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"
    result = {}
    for r in read(path):
        if r["uid"] not in valid_case or r["method"] != "RPR_PAPER_FULL" or r["actor_status"] != "OK":
            continue
        wire = r["actor_request"]
        if sha(wire) != r["actor_request_sha256"]:
            raise ValueError("Archived RP wire changed")
        result[r["uid"]] = {"wire": wire, "benchmark": "RPEval", "key": (r["uid"], r["method"]),
                           "score": native("RPEval", r.get("native_fields")), "row": r}
    return result


def rpe_empty(original):
    from exposure_wires import rp_projection

    prior = read(REPORTS / "counterfactual_rpeval_v41_task_only/FROZEN.json")["ready"]
    empty = {}
    for row in read(REPORTS / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]:
        uid = row["uid"]
        endpoint = row["no_history_state"]
        if uid not in original or not endpoint.get("answer"):
            continue
        wire = rp_projection(original[uid]["wire"], [])
        expected = row["task_wire_sha256"] or prior.get(uid, {}).get("task_wire_sha256")
        if not expected or sha(wire) != expected:
            continue
        if not row["task_wire_sha256"] and sha(endpoint["answer"]) != prior[uid]["answer_sha256"]:
            raise ValueError("Archived empty answer changed")
        empty[uid] = {"wire": wire, "benchmark": "RPEval", "key": (uid, "TASK_ONLY"),
                      "score": native("RPEval", endpoint.get("score", endpoint.get("fields"))),
                      "row": {"score_flags": endpoint.get("flags"), "group": row["source_group"]}}
    return empty


def summarize_pairs(cohort, records, origin=None, *, diagnostic=False, keep_policy=False):
    outcome = defaultdict(Counter)
    protected_groups = defaultdict(set)
    for left, right in records:
        b = left["benchmark"]
        counter = outcome[b]
        counter["candidate_pairs"] += 1
        if left["score"] is None or right["score"] is None:
            counter["incomplete_score"] += 1
            continue
        try:
            before, a, a_sources = state(left["wire"], keep_policy=keep_policy)
            after, z, z_sources = state(right["wire"], keep_policy=keep_policy)
            common = a_sources.keys() & z_sources.keys()
            if before != after or any(a_sources[s] != z_sources[s] for s in common):
                counter["changed_context_or_source_text"] += 1
                continue
            domain = origin[left["key"][0]] if origin else (a if len(a) >= len(z) else z)
            if isinstance(domain, dict):
                domain = state(domain["wire"])[1]
            action = difference(tuple(s.source for s in domain), a, z)
        except (ValueError, TypeError, KeyError):
            counter["unverified_state"] += 1
            continue
        name = action.operation if action else "COMPOSITE"
        counter[name] += 1
        if name in ("KEEP", "COMPOSITE"):
            continue
        x, y = left["score"], right["score"]
        if y[0] > x[0]:
            counter[name + "/score_gain"] += 1
            if protected(b, x, y):
                counter[name + "/protected_gain"] += 1
                group = left["row"].get("group") or right["row"].get("group")
                if group:
                    protected_groups[b, name].add(group)
        elif y[0] < x[0]:
            counter[name + "/score_loss"] += 1
        else:
            counter[name + "/score_tie"] += 1
        if left["row"].get("score_flags") or right["row"].get("score_flags"):
            counter[name + "/known_score_flag"] += 1
    for (benchmark, action), groups in protected_groups.items():
        outcome[benchmark][action + "/protected_gain_groups_with_id"] = len(groups)
    return {"archive": cohort, "uses_author_guided_diagnostic_arm": diagnostic, "counts": dict(outcome)}


def main():
    ref = rpe_original()
    empty = rpe_empty(ref)
    provided = REPORTS / "execution_feedback_policy_v1"
    roles = rows_for(provided / "RESULTS.json", (provided / "InterventionActor_MANIFEST.json",))
    mix = NATIVE / "round2_rpe_exposure_v1"
    mixed = rows_for(mix / "RESULTS.json", (mix / "MixedHistoryActor_MANIFEST.json",), benchmark="RPEval")
    promote = NATIVE / "visible_c_promotion_v1"
    c = rows_for(promote / "RESULTS.json", (promote / "VisibleCActor_MANIFEST.json",), benchmark="RPEval")
    reentry = REPORTS / "source_local_reentry_v1/format_recovery"
    selected = rows_for(reentry / "RESULTS.json", (reentry / "ReentryActor_MANIFEST.json",), benchmark="RPEval")
    hidden = NATIVE / "hidden_b_oracle_v1"
    oracle = rows_for(hidden / "RESULTS.json", (hidden / "HiddenBActor_MANIFEST.json",), benchmark="RPEval")
    bu = RUNS / "persist_equal_cap_development_v1"
    utility = rows_for(bu / "RESULTS.json", (bu / "Actor_MANIFEST.json",), benchmark="PersistBench")
    safe = RUNS / "persist_equal_cap_safety_v1"
    risks = [rows_for(safe / "RESULTS.json", (safe / f"Wave{wave}_Actor_MANIFEST.json",),
                      benchmark="PersistBench", wave=wave) for wave in (1, 2)]
    out = [
        summarize_pairs("fixed_actor_exposure", pairs(roles, "EMPTY", ("COMPLETE",))),
        summarize_pairs("rpe_mixed_exposure", pairs(mixed, "WHOLE_HISTORY", ("PER_SOURCE",)), ref,
                        keep_policy=True),
        summarize_pairs("rpe_visible_C_diagnostic",
                        ((ref[uid], row["promote_c"]) for uid, row in c.items() if uid in ref), ref,
                        diagnostic=True),
        summarize_pairs("rpe_single_source_reentry",
                        ((empty[uid], arm) for uid, arms in selected.items() if uid in empty
                         for arm in arms.values()), ref),
        summarize_pairs("rpe_hidden_B_diagnostic",
                        ((empty[uid], arm) for uid, arms in oracle.items() if uid in empty
                         for arm in arms.values()), ref, diagnostic=True),
        summarize_pairs("persist_equal_cap_utility",
                        pairs(utility, "FULL", ("GROUNDING", "ROUTED", "EMPTY"))),
        *(summarize_pairs(f"persist_equal_cap_risk_wave{wave}",
                         pairs(risk, "FULL", ("GROUNDING", "ROUTED", "EMPTY")))
          for wave, risk in enumerate(risks, 1)),
    ]
    print(json.dumps({"reports": out, "added_model_calls": 0}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
