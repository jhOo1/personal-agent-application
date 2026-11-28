"""Task-paired direction and model-affinity sensitivity on fixed answers."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from random import Random
from runpy import run_path

HERE = Path(__file__).resolve().parent
setup = run_path(str(HERE / "trial.py"))
build, read = setup["build"], setup["read"]
NAMES, PRIVATE = setup["NAMES"], setup["PRIVATE"]


def direction(delta):
    return "win" if delta > 0 else "loss" if delta < 0 else "tie"


def match(cell):
    return cell["grade"].get("match", {}).get("matched")


def summarize(pairs):
    n = len(pairs)
    observed = sum(d for d, _ in pairs)
    positions = sum(k for _, k in pairs)
    rng = Random(8941053)
    draws = []
    for _ in range(10000):
        sample = rng.choices(pairs, k=n)
        draws.append(100 * sum(d for d, _ in sample) / sum(k for _, k in sample))
    draws.sort()
    return {"roots": n, "positions": positions, "net_positions": observed,
            "percentage_points": round(100 * observed / positions, 2),
            "wlt": Counter(direction(d) for d, _ in pairs),
            "exploratory_95_percentile": [round(draws[250], 2), round(draws[9749], 2)]}


def main():
    _, cards, _ = build()
    data = read(PRIVATE / "RESULTS.json")
    current = {(r["uid"], r["generator"], r["arm"]): r["rating"] for r in data["rows"]}
    scope = defaultdict(list)
    joint = defaultdict(Counter)
    total = Counter()
    for uid, card in cards.items():
        judge = {"GPT": card["saved"],
                 "QWEN": {model: {arm: current[uid, model, arm] for arm in NAMES[model]} for model in NAMES}}
        if any(match(cell) is None for by_actor in judge.values() for by_arm in by_actor.values() for cell in by_arm.values()):
            total["missing"] += 1
            continue
        total["common"] += 1
        n = len(card["labels"])
        for model, (the_task, the_memory) in NAMES.items():
            chosen = card["branch"][model]
            for label, competitor in (("always_task", the_task), ("always_memory", the_memory)):
                deltas = {}
                for grader, by_model in judge.items():
                    delta = match(by_model[model][chosen]) - match(by_model[model][competitor])
                    deltas[grader] = delta
                    scope[f"{model}/{label}/{grader}"].append((delta, n))
                joint[f"{model}/{label}"][f"GPT_{direction(deltas['GPT'])}/Qwen_{direction(deltas['QWEN'])}"] += 1
        family = {j: {m: match(a[card["branch"][m]]) for m, a in by_model.items()} for j, by_model in judge.items()}
        delta = (family["GPT"]["GPT"] - family["GPT"]["QWEN"]) - (family["QWEN"]["GPT"] - family["QWEN"]["QWEN"])
        scope["generator_gap_interaction"].append((delta, n))
    if not total["common"]:
        raise ValueError("No jointly valid crossed records")
    print(json.dumps({"roster": total, "pairs": {k: summarize(v) for k, v in scope.items()},
                      "judge_agreement_on_paired_direction": joint}, indent=2))


if __name__ == "__main__":
    main()
