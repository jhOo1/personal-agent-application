"""Reconcile the exact paired renderings and the project BenchPreS grading ledger."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

trial = run_path(str(Path(__file__).with_name("trial.py")))
PRIVATE, RUN, archive, prepare, sha = (trial[k] for k in ("PRIVATE", "RUN", "archive", "prepare", "sha"))
METHODS = ("base", "external", *trial["OUTPUTS"])


def settle():
    cards, _, jobs, pin = prepare()
    if pin != archive.read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen comparison drift")
    data = archive.read(PRIVATE / "RESULTS.json")
    if set(data["metrics"]) != set(cards):
        raise ValueError("Missing assigned case")
    answers = {(l, a): text for l, a, text in data["answers"]}
    ledger = data["ledger"]
    receipts = []
    for p in RUN.glob("*/visible/*/record.json"):
        r = archive.read(p)
        if sha(archive.read(p.with_name("request.json"))) != r["request_sha256"]:
            raise ValueError("Physical request drift")
        receipts.append(r)

    def key(record):
        return record["unit"]["stage"], record["request_sha256"], record["status"]

    if Counter(map(key, receipts)) != Counter(map(key, ledger)):
        raise ValueError("Call ledger mismatch")
    exact_smoke = trial["render"]('{"header":"Dear reader,","actions":"Reply please.","context":"Background.","closing":"Thanks."}')
    if exact_smoke["ACTION_FIRST"] != "Dear reader,\n\nReply please.\n\nBackground.\n\nThanks.":
        raise ValueError("Rendering order regression")
    totals = {method: Counter() for method in METHODS}
    pair_totals = {method: Counter() for method in ("CONTEXT_FIRST", "ACTION_FIRST")}
    outcomes = Counter()
    result = []
    for label, values in data["metrics"].items():
        x, y = (answers.get((label, a)) for a in ("CONTEXT_FIRST", "ACTION_FIRST"))
        order_changed = None if x is None or y is None else x != y
        if order_changed and Counter(x.split()) != Counter(y.split()):
            raise ValueError("Word inventory differs within rendering pair")
        def accumulate(methods, acc):
            if not all(values.get(method) for method in methods):
                return
            for method in methods:
                cell = values[method]
                acc[method].update(tasks=1, completeness=cell["completeness"])
                for metric in ("aar", "nonbold", "mr"):
                    n, d = cell[metric]
                    acc[method].update({metric: n, metric + "_n": d})
        accumulate(METHODS, totals)
        accumulate(pair_totals, pair_totals)
        left, right = values["CONTEXT_FIRST"], values["ACTION_FIRST"]
        if left and right:
            delta = right["nonbold"][0] - left["nonbold"][0]
            outcomes["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
        result.append({"case": label, "profile_index": list(dict.fromkeys(c["base"]["profile_group"]
                        for c in cards.values())).index(cards[label]["base"]["profile_group"]) + 1,
                       "word_count": {method: len(answers[label, method].split()) for method in trial["OUTPUTS"]
                                      if (label, method) in answers},
                       "word_order_changed": order_changed, "methods": values})
    return {"cases": result, "all_methods_common": totals, "render_only_common": pair_totals,
            "nonbold_pair": outcomes, "failures": data["failures"],
            "physical_requests": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
            "transport": Counter(r["status"] for r in ledger), "archive": data["archive_reuse"],
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(settle(), sort_keys=True, indent=2))
