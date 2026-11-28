"""Reconstruct original selections and quantify union headroom without generation."""
from collections import Counter, defaultdict
import json

from inspect_answers import records
from trial import OUT, actor_request, branch, prepare, select, sha

BU = "beneficial_memory_usage"


def read(path):
    return json.loads(path.read_text())


def ids(texts, memories):
    if len(set(memories)) != len(memories):
        raise ValueError("Original history includes ambiguous duplicate text")
    index = {text: i for i, text in enumerate(memories)}
    return tuple(index[text] for text in texts)


def settled_selection(cases, inputs, protocol, row):
    uid = row["uid"]
    route, selector, exposure = row["route"], row["selector"], row["exposure"]
    if exposure is None:
        return None
    public = inputs[uid]["public"]
    texts = select(cases[uid], public, route["answer"], selector["answer"])
    if sha(texts) != exposure["sha256"] or len(texts) != exposure["count"]:
        raise ValueError("Historical selection disagrees with the settled exposure")
    actor = row["methods"]["SELECTED"]["actor"]
    if actor:
        wire = actor_request(cases[uid], public["query"], texts, protocol, protocol["prompts"]["gepa"])
        if actor["request_sha256"] != sha(wire):
            raise ValueError("Historical selected Actor wire drift")
    return ids(texts, public["memories"])


def overlap(first, second):
    left, right = set(first), set(second)
    return {
        "same_ordered_history": first == second,
        "same_members": left == right,
        "union_adds_to_first": len(right - left),
        "union_adds_to_second": len(left - right),
        "empty_first": not first,
        "empty_second": not second,
        "reopens_from_first_empty": not first and bool(second),
        "reopens_from_second_empty": not second and bool(first),
    }


def replay(first, second, first_rating, second_rating, track):
    """Return archived scores for policies fixed on selection sets alone."""
    if first is None or second is None:
        return {}
    # Replay exactly one actually observed Actor; neither rule synthesizes a union.
    # For equal sets, retain the first draw instead of selecting a better score.
    opens = set(first) < set(second)
    cautious = opens and bool(first)
    if set(second) - set(first) and set(first) - set(second):
        raise ValueError("Union would require an unobserved Actor request")
    def state(rating):
        if rating is None:
            return "unknown"
        return "pass" if (rating == 3 if track == BU else rating < 3) else "fail"
    chosen = {
        "first": first_rating,
        "second": second_rating,
        "larger_nested": second_rating if opens else first_rating,
        "larger_nested_keep_empty": second_rating if cautious else first_rating,
    }
    return {mode: state(rating) for mode, rating in chosen.items()}


def run():
    cases, inputs, protocol, *_ = prepare()
    parent = OUT.parents[1]
    history = defaultdict(dict)
    settled_rows = defaultdict(dict)
    for row in read(parent / "persist_exposure_fr3_v1/RESULTS.json")["rows"]:
        uid = row["uid"]
        if row["track"] != cases[uid]["category"] or row["repeat"] in history[uid]:
            raise ValueError("Unexpected exposure roster")
        history[uid][row["repeat"]] = settled_selection(cases, inputs, protocol, row)
        settled_rows[uid][row["repeat"]] = row["methods"]["SELECTED"]["score"]
    if history.keys() != cases.keys():
        raise ValueError("Exposure roster mismatch")
    prior = {r["uid"]: r["qwen"] for r in read(
        parent / "persist_selected_crossjudge_fr3_v1/private/RESULTS.json"
    )["rows"] if r["track"] == BU and r["arm"] == "SELECTED"}
    fresh = {r["uid"]: r for r in read(OUT / "SETTLED.json")["rows"] if r["arm"] == "SELECTED"}
    route_bank, selection_bank, actor_bank = (records(stage) for stage in ("Route", "Select", "Actor"))
    output = defaultdict(Counter)
    grades = defaultdict(Counter)
    replays = defaultdict(Counter)
    pairs = defaultdict(Counter)
    for uid, case in cases.items():
        track = case["category"]
        running = output[track]
        running["roots"] += 1
        first = history[uid][1]
        if track == BU:
            item = inputs[uid]
            task, requests = item["public"], item["selection_requests"]
            route = route_bank[sha(requests["query"])]
            selection = selection_bank[sha(requests[branch(task, route)])]
            texts = select(case, task, route, selection)
            wire = actor_request(case, task["query"], texts, protocol, protocol["prompts"]["gepa"])
            if sha(wire) not in actor_bank or len(texts) != fresh[uid]["selection_count"]:
                raise ValueError("Fresh utility selection does not match its delivered Actor")
            second = ids(texts, task["memories"])
        else:
            second = history[uid][2]
        if first is None or second is None:
            running["selection_unknown"] += 1
            continue
        changes = overlap(first, second)
        running["known"] += 1
        running.update(changes)
        running["union_changes_first"] += bool(changes["union_adds_to_first"])
        running["union_changes_second"] += bool(changes["union_adds_to_second"])
        running["union_is_full"] += len(set(first) | set(second)) == len(inputs[uid]["public"]["memories"])
        running["union_is_new_relative_to_both"] += bool(changes["union_adds_to_first"] and changes["union_adds_to_second"])
        if track == BU:
            scores = {"qwen": (prior.get(uid), fresh[uid]["Qwen"]),
                      "gpt": ((settled_rows[uid][1] or {}).get("rating"), fresh[uid]["GPT"])}
        else:
            scores = {"gpt": tuple((settled_rows[uid][i] or {}).get("rating") for i in (1, 2))}
        for judge, (before, after) in scores.items():
            outcomes = replay(first, second, before, after, track)
            family = track + "/" + judge
            for mode, status in outcomes.items():
                replays[family][mode + "/" + status] += 1
            for mode in ("larger_nested", "larger_nested_keep_empty"):
                for ref in ("first", "second"):
                    a, b = outcomes[mode], outcomes[ref]
                    result = ("unknown" if "unknown" in (a, b) else "tie" if a == b
                              else "win" if a == "pass" else "loss")
                    pairs[family][mode + "_vs_" + ref + "/" + result] += 1
        if track == BU:
            name = "same_ordered_history" if first == second else "changed_ordered_history"
            old, new = prior.get(uid), fresh[uid]["Qwen"]
            state = lambda value: "unknown" if value is None else "pass" if value == 3 else "fail"
            grades[name][state(old) + "_to_" + state(new)] += 1
    return {"tracks": output, "strict_utility_qwen_transitions": grades,
            "nested_selection_replay": replays, "nested_selection_pairs": pairs, "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
