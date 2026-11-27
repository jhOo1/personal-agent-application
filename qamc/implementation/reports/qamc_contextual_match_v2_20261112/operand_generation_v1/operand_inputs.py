"""Bind one shared input per arm to the exact exposed baseline archives."""
from collections import Counter
import json
from pathlib import Path

from assembler import anchors
from complete import ROOT, RUN as PERSIST_RUN, archive, get_author, read
from compare_controls import load_verified_scores
from delta import index
from protected import source_texts
from qamc.common import sha
import relation_trial as bench
import run_delta as rpe


BASE = Path(__file__).resolve().parent.parent
RPE_SLICES = {
    "b1d78fb1": "formalwear",
    "ee35becc": "children_dishes",
    "6991a537": "omega3",
    "f051b02d": "parents_brunch",
    "81fef011": "plant_muscle",
    "4417f7b0": "winter_family",
    "d8ea0f8d": "farewell_gift",
    "f3ee87d4": "cat_gift",
}
PERSIST_SLICES = {
    "b664c8fa": "partner_trip",
    "36bd0c4f": "family_chapter",
    "ef273934": "named_life_facts",
    "0613beea": "project_template",
}


def prefix(rows, name):
    match, = [row for uid, row in rows.items() if uid.rsplit("/", 1)[-1].startswith(name)]
    return match


def rpe_cards():
    packets, binding, choices, _, _ = rpe.assign()
    history = {row["uid"]: row for row in rpe.trial.read(
        rpe.trial.VETO.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")["rows"]}
    # Baseline identity is obtained without constructing any benchmark grade request.
    uid_keys = {row["uid"]: key for key, row in binding.items()}
    cards = {}
    group_plan = rpe.trial.read(BASE / "paper_baseline_validation_156_v1/MANIFEST_156.json")
    groups = {row["uid"]: row for row in group_plan if row["benchmark"] == "rpeval"}
    grade_plan = rpe.trial.read(rpe.RUN / "SCORED_ROWS.json")
    for known, label in RPE_SLICES.items():
        key = prefix(uid_keys, known)
        uid = binding[key]["uid"]
        case = groups[uid]
        if case["independent_confirmation"]:
            raise ValueError("Sealed RPEval task")
        packet = packets[key]
        chosen = choices[key]["choice"] or packet["default_id"]
        draft = packet["candidates"][chosen]
        context = packet["context"]
        base_grade = grade_plan[key]["grade"]["V1"]
        if base_grade is None:
            raise ValueError("Missing RPEval V1 grade")
        refs = dict(history[uid]["scores"])
        refs["RP"] = refs.pop("RPR_PAPER_FULL")
        refs["Des2Gen"] = refs.pop("DES2GEN_FULL")
        refs["MemAdapter"] = refs.pop("MEMADAPTER_FULL")
        cards["RPEval/" + label] = {
            "key": key, "uid": uid, "group": case["group_id"],
            "draft": draft, "score": base_grade, "references": refs,
            "context": {k: context[k] for k in ("query", "current_context", "facts")},
            "history": context["history"], "candidate_solutions": {
                ref: answer for ref, answer in packet["candidates"].items() if ref != chosen},
            "raw_packet": packet, "binding": binding[key],
        }
    return cards


def bench_cards():
    source, _, protocol, _ = bench.prepare()
    cards = {}
    for name, data in source.items():
        if name in ("protection_1", "protection_2"):
            continue
        original = json.loads(data["original"]["messages"][-1]["content"])
        case, base, external = (data[key] for key in ("case", "base", "external"))
        cards["BenchPreS/" + name] = {
            "uid": case["uid"], "group": base["profile_group"], "case": case,
            "draft": base["answer"], "score": bench.summarize(base["attributes"], base["old_completeness"]),
            "references": {"Selectivity": bench.summarize(external["attributes"], external["old_completeness"])
                           if external["old_strict_score"] else None},
            "context": {"query": original["query"], "current_context": original["current_context"],
                        "facts": original["fixed_facts"]},
            "history": original.get("source_evidence", []),
            "guidance": original["selected_memory_use_guidance"], "grade_protocol": protocol,
        }
    return cards


def persist_cards():
    author, envelopes, _ = get_author()
    scores, controls = load_verified_scores()
    selections = {}
    for name in ("selected_gepa_expansion_v1", "persist_performance_v1"):
        rows, _ = archive["supplementary"](BASE / "native_residual_v1" / name, envelopes, Counter())
        selections.update({r["uid"]: r for r in rows if r["method"] == "SELECTED_GEPA"})
    rows, _ = archive["factorial"](envelopes, Counter())
    selections.update({r["uid"]: r for r in rows})
    selections.update({r["uid"]: r for r in read(PERSIST_RUN / "RESULTS.json")["rows"] if r["score"] is not None})
    if set(selections) != set(scores):
        raise ValueError("SELECTED_GEPA inventory differs from exact grade coverage")
    plan = read(BASE / "persist_author_controls_v2/PLAN.json")
    cases = {c["uid"]: c for c in plan["cases"] if c["role"] == "DEV" and c["uid"] in scores}
    if set(cases) != set(scores):
        raise ValueError("Only exposed PersistBench cases permitted")
    picked = {label: prefix(cases, lead) for lead, label in PERSIST_SLICES.items()}
    group_ids = {case["group_id"] for case in picked.values()}
    for i, category in enumerate(("beneficial_memory_usage", "beneficial_memory_usage", "cross_domain", "sycophancy"), 1):
        candidates = [case for uid, case in cases.items() if case["category"] == category
                      and case["group_id"] not in group_ids
                      and archive["passes"](scores[uid][1], category)]
        row = min(candidates, key=lambda case: sha(["operand-protection", case["group_id"], case["uid"]]))
        picked[f"protection_{i}"] = row
        group_ids.add(row["group_id"])
    cards = {}
    for name, case in picked.items():
        uid = case["uid"]
        text = archive["persist"].author.parent.smoke.task_for(case)
        memories = [m.text for m in text.memories]
        if sha({"query": text.query, "memories": memories}) != case["public_sha256"]:
            raise ValueError("PersistBench original candidates changed")
        row = selections[uid]
        if row["score"] != scores[uid][1] or not row["answer"]:
            raise ValueError("PersistBench answer and grade do not bind")
        refs = {key: value for key, value in controls[uid].items()
                if key in ("PB_RUBRIC", "PB_GEPA", "PB_NO_MEMORY", "MEMADAPTER_FULL", "PB_FILTER_NATIVE")}
        cards["PersistBench/" + name] = {
            "uid": uid, "group": case["group_id"], "track": case["category"], "draft": row["answer"],
            "score": row["score"], "references": refs,
            "context": {"query": text.query, "current_context": text.current_context, "facts": []},
            "history": memories, "score_envelope": envelopes[uid],
        }
    return cards


def task_packet(card):
    context = card["context"]
    facts = list(source_texts(context["facts"]))
    history = list(source_texts(card["history"]))
    # Original history becomes a source for the OPTIONAL action. REPORT_EVENT reads only single
    # fixed fact entries. Source IDs are generated from the visible inputs and include no case identity.
    facts = {f"F{i}": text for i, text in enumerate(facts, 1)}
    offers = {f"M{i}": text for i, text in enumerate(history, 1)}
    protected = anchors({**context, "facts": []}, card["draft"])
    return {"task": {"query": context["query"], "current_context": context["current_context"]},
            "fact_operands": facts, "offer_operands": offers,
            "preference_guidance": card.get("guidance", []),
            "candidate_solutions": card.get("candidate_solutions", {}),
            "draft_units": index(card["draft"]), "protected_literals": protected}


def prepare():
    cards = {**rpe_cards(), **bench_cards(), **persist_cards()}
    counts = Counter(label.split("/", 1)[0] for label in cards)
    if set(counts.values()) != {8} or len(counts) != 3 or len({c["uid"] for c in cards.values()}) != len(cards):
        raise ValueError("Unexpected three-benchmark development roster")
    return cards, {name: task_packet(card) for name, card in cards.items()}
