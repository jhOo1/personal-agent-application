"""Post-hoc same-task routing diagnostics using only already scored paired draws."""
from collections import Counter
from itertools import product
from panel import HERE, read

MODELS = ("qwen3.8-flash", "deepseek-v4.1-flash")


def measures(score, index):
    return Counter(indexed=int(score["decisions"][index]["label"] == "follow"),
                   aar=score["aar_numerator"], mr=score["mr_numerator"],
                   completeness=score["task_completeness"], pairs=1)


def routing_summary():
    rows = read(HERE / "private/DRAW2.json")["rows"]
    scores = {(r["uid"], r["rep"], r["model"]): r["score"] for r in rows}
    if len(scores) != len(rows):
        raise ValueError("Duplicate final draw row")
    lines = ["# How much could choosing the Actor recover?", "",
             "Post-hoc diagnostic on the frozen BenchPreS panel. Every comparison uses the same complete draw pairs. "
             "Selection optimizes the indexed preference only. Ties keep Qwen. "
             "The task oracle uses all scored draws for the task, including the evaluated draw. "
             "The other-draw rule uses only earlier or later scored draws of that identical task and excludes the evaluated draw. "
             "Neither rule is available for a new task at inference.", "",
             "| Cohort | Policy | DeepSeek uses / pairs | Indexed follows | AAR numerator | MR numerator | Completeness total |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for cohort, cards in read(HERE / "PANEL.json").items():
        totals = {k: Counter() for k in ("Qwen", "DeepSeek", "Task oracle", "Other draws")}
        task_totals = []
        for card in cards:
            uid = card["uid"]
            pairs = []
            for rep in range(3):
                pair = [scores[uid, rep, model] for model in MODELS]
                if all(s is not None for s in pair):
                    pairs.append([measures(s, card["position"]) for s in pair])
            task_totals.append([sum((pair[i] for pair in pairs), Counter()) for i in range(2)])
            delta = sum(d["indexed"] - q["indexed"] for q, d in pairs)
            for q, d in pairs:
                choices = [False, True, delta > 0, delta - (d["indexed"] - q["indexed"]) > 0]
                for total, use_deepseek in zip(totals.values(), choices):
                    total.update(d if use_deepseek else q)
                    total["deepseek"] += int(use_deepseek)
        for policy, t in totals.items():
            lines.append(f"| {cohort} | {policy} | {t['deepseek']}/{t['pairs']} | "
                         f"{t['indexed']} | {t['aar']} | {t['mr']} | {t['completeness']} |")
        if cohort == "targets":
            assignments = [sum((task[i] for task, i in zip(task_totals, choices)), Counter())
                           for choices in product(range(2), repeat=len(cards))]
            best = max(x["indexed"] for x in assignments)
            completion = [x["completeness"] for x in assignments if x["indexed"] == best]
            protected = [x for x in assignments if x["completeness"] >= totals["Qwen"]["completeness"]
                         and x["mr"] <= totals["Qwen"]["mr"] and x["aar"] >= totals["Qwen"]["aar"]]
            tie_note = (f"Across all {len(assignments)} fixed assignments to the five target tasks, "
                        f"the indexed maximum is {best}/15; its tied assignments span completeness "
                        f"{min(completion)}–{max(completion)} points. Requiring aggregate target completeness "
                        f"and AAR at least Qwen's and MR at most Qwen's leaves an indexed ceiling of "
                        f"{max(x['indexed'] for x in protected)}/15. These are hindsight bounds.")
    lines.extend(["", tie_note])
    return "\n".join(lines)


if __name__ == "__main__":
    print(routing_summary())
