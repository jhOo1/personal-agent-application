"""Locate each paired non-bold preference on the exact saved Actor wires."""

import argparse
from collections import Counter, defaultdict
import json
import re
import unicodedata

from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from report_qamc_benchpres_three_draw import metric_values
from trace_misuse import jobs, run
from trace_nonbold import BOLD, response


def words(value):
    text = unicodedata.normalize("NFKC", value).casefold()
    return " " + " ".join(re.findall(r"\w+", text)) + " "


def audit(waves):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")
    cases = {case["uid"]: case for case in plan["cases"]}
    bridge = PersistAuthorBridge(run.ROOT / "literature/qamc_pa_v1/PersistBench")
    template = bridge.blobs["GEPA"].decode().replace("{model_name}", "qwen3.8-flash")
    before, after = template.split("{memories}")
    delivery = defaultdict(Counter)
    series = defaultdict(Counter)
    for wave in waves:
        area = run.RUN / f"wave-{wave}"
        rows = run.read(area / "RESULTS.json")
        results = {(r["uid"], r["method"], r["replicate"]): r["score"] for r in rows}
        roots = plan["waves"][wave]
        if len(results) != len(rows) or set(results) != {(u, m, i) for u in roots
                                                        for m in run.METHODS for i in run.REPEATS}:
            raise ValueError("Settlement allocation changed")
        actors = jobs(area, "ACTOR")
        for uid in roots:
            case = cases[uid]
            ref = run.read(run.ROOT / case["evaluation_path"])
            if case["independent_confirmation"] or run.digest(ref) != case["evaluation_hash"]:
                raise ValueError("Expected frozen exposed development evaluation")
            for draw in run.REPEATS:
                gate, paper = (results[uid, method, draw] for method in run.METHODS)
                if gate is None or paper is None:
                    continue
                wires = {}
                for method, score in ((run.GATE, gate), (run.PAPER, paper)):
                    job = actors[uid, method, draw, "Actor"]
                    response(area, "generation", job)
                    metric_values(score, ref)
                    wires[method] = job["request"]["messages"]
                system, user = wires[run.GATE]
                system = system["content"]
                if not system.startswith(before) or not system.endswith(after):
                    raise ValueError("Gate source block differs from pinned renderer")
                block = system[len(before):len(system) - len(after)]
                if not block.startswith("<memories>\n") or not block.endswith("\n</memories>"):
                    raise ValueError("Unexpected Gate memory block")
                selected = [words(line) for line in block.splitlines()[1:-1]]
                facts = [words(fact) for fact in json.loads(user["content"])["fixed_facts"]]
                paper_wire = words(wires[run.PAPER][0]["content"])
                for i, (g, p) in enumerate(zip(gate["decisions"], paper["decisions"], strict=True)):
                    if not g["appropriate"] or BOLD.search(g["preference"]):
                        continue
                    phrase = words(g["preference"])
                    if any(phrase in text for text in selected):
                        source = "gate_selected_source_exact"
                    elif any(phrase in text for text in facts):
                        source = "gate_fixed_fact_exact"
                    else:
                        source = "gate_no_exact_expression"
                    g_hit, p_hit = g["label"] == "follow", p["label"] == "follow"
                    delivery[source].update(paired_positions=1, paper_wire_exact=phrase in paper_wire,
                                            gate_follow=g_hit, paper_follow=p_hit, neither=not (g_hit or p_hit),
                                            both=g_hit and p_hit)
                    series[uid, i].update(scored_draws=1, gate_follow=g_hit, paper_follow=p_hit)
    patterns = Counter(f"{s['scored_draws']} draws: Gate {s['gate_follow']}, Selectivity {s['paper_follow']}"
                       for s in series.values())
    return {"waves": waves, "unique_task_attributes": len(series), "paired_positions_by_gate_delivery": delivery,
            "recurrence": patterns, "model_calls": 0, "score_changes": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=range(6), required=True)
    args = parser.parse_args()
    print(json.dumps(audit(sorted(set(args.wave))), indent=2, sort_keys=True))
