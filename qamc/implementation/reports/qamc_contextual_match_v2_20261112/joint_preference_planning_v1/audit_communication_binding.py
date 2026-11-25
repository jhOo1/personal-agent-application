"""Verify shared predictions, actual source removal and paired native attribute changes."""
from argparse import ArgumentParser
from collections import Counter
import json
import re

from proposals.qamc_protocol_alignment.metric_coverage import metric_set
from qamc.common import parse_object, sha
from qamc.pa.core import digest

import run_communication_binding as run
from settle_realization_transfer import paired_summary


def allocation():
    plan, roots, requests = run.prepare()
    if plan != run.read(run.OUT / "FROZEN.json"):
        raise ValueError("The communication binding experiment changed")
    old = run.previous_receipts(plan)
    folder = run.OUT / run.BENCH
    run.probe.OUT, run.probe.RUN = folder, run.RUN / run.BENCH
    receipts = {}
    for stage in plan["panels"][run.BENCH]["caps"]:
        for record, raw in run.probe.stage_receipts(stage).values():
            if record is not None:
                key = stage, record["request_sha256"]
                if key in receipts or key in old:
                    raise ValueError("A physical request redundantly repeated an exact staged wire")
                receipts[key] = record, raw
    traces, counts, changes = {}, Counter(), []
    expected = {stage: {} for stage in (run.SELECT, run.ACTOR)}
    available = {**old, **receipts}
    for root in roots:
        uid = root["uid"]
        key = sha(requests[uid, "BOTH", run.SELECT])
        expected[run.SELECT].setdefault(key, (uid, "BOTH"))
        record, raw = available.get((run.SELECT, key), (None, None))
        status = record["status"] if record is not None else "UNISSUED"
        counts[status] += 1
        if status != "OK":
            continue
        try:
            view = run.binding.compile_views(root, raw)
        except (ValueError, KeyError, TypeError):
            counts["selector_contract_error"] += 1
            continue
        traces[uid] = view
        actor = {}
        for arm, select in run.ARMS:
            wire = run.binding.base.actor(root, view[select], run.binding.base.DIRECT)
            expected[run.ACTOR].setdefault(sha(wire), (uid, arm))
            actor[arm] = wire
        a, b = actor[run.OPEN], actor[run.BOUND]
        va, vb = (json.loads(w["messages"][1]["content"]) for w in (a, b))
        remove = {mid for mid, reason in view["gate"].items() if reason is not None}
        normalized = {**va,
                      "source_evidence": [m for m in va["source_evidence"] if m["memory_id"] not in remove],
                      "licensed_uses": [m for m in va["licensed_uses"] if m["memory_id"] not in remove]}
        if (vb != normalized or {**a, "messages": a["messages"][:1]} != {**b, "messages": b["messages"][:1]}
                or bool(remove) != (a != b) or va["task"] != root["public_task"]):
            raise ValueError("Treatment changed the task, Actor, or something beyond annotated source removal")
        if remove:
            changes.append({"uid": uid, "plain_sha256": sha(a), "bound_sha256": sha(b),
                            "removed": {mid: view["gate"][mid] for mid in sorted(remove)}})
    for name, entries in expected.items():
        path = folder / f"{name}_MANIFEST.json"
        if not path.exists() or (name == run.ACTOR and (counts["UNISSUED"] or counts["PENDING_DELIVERY_UNKNOWN"])):
            continue
        units = run.read(path)["units"]
        actual = {sha(x["request"]): (x["unit"]["root_id"], x["unit"]["method"]) for x in units}
        if (len(actual) != len(units)
                or actual != {key: value for key, value in entries.items() if (name, key) not in old}):
            raise ValueError(f"{name} manifest does not match the independent reconstruction")
    return roots, traces, receipts, {
        "selector_status": counts, "eligible_roots": len(roots), "valid_predictions": len(traces),
        "gate_active_roots": len(changes), "gate_removed": Counter(
            why for c in changes for why in c["removed"].values()),
        "projected_distinct_actor_wires_after_cache": sum((run.ACTOR, key) not in old for key in expected[run.ACTOR]),
        "gate_changes": changes, "new_model_calls": 0,
    }


def archived_admission_diagnostics(roots, traces):
    """Trace old native attributes through current source admission without rescoring them."""
    old = run.read(run.OLD_OUT / run.BENCH / "VISIBILITY_AUDIT.json")["cases"]
    root_by_uid = {root["uid"]: root for root in roots}
    counts, cases = Counter(), []
    for row in old:
        uid = row["uid"]
        trace = traces.get(uid)
        retained = {edge["memory_id"] for edge in trace["bound"]} if trace is not None else set()
        for score in row["decisions"]:
            if score["appropriate"]:
                family = "appropriate"
            elif score["visibility"] == "visible" and score["label"] == "follow":
                family = "old_used_inappropriate"
            else:
                continue
            related = set(score["exact_memory_ids"])
            if trace is None:
                step = "new_selector_unusable"
            elif not related:
                step = "no_exact_candidate"
            elif related & retained:
                step = "passed"
            elif any(trace["gate"].get(mid) for mid in related):
                step = "gate_removed"
            else:
                step = "selector_excluded"
            counts[f"{family}/{step}"] += 1
            if family == "appropriate":
                counts[f"appropriate_previously_{score['visibility']}/{step}"] += 1
            cases.append({"uid": uid, "preference": score["preference"], "group": family,
                          "exact_memory_ids": sorted(related), "new_source_disposition": step})
    exact_repetitions = []
    for uid, trace in traces.items():
        root = root_by_uid[uid]
        original = {m["memory_id"]: m["text"] for m in root["original_sources"]}
        exposed_task = [v.casefold() for v in run.binding.base.task_text(root["public_task"])]
        exposed_evidence = [original[edge["memory_id"]].casefold() for edge in trace["bound"]]
        for mid, reason in trace["gate"].items():
            if reason and any(original[mid].casefold() in text for text in (*exposed_task, *exposed_evidence)):
                exact_repetitions.append({"uid": uid, "memory_id": mid})
    return {"archived_scored_roots": len(old), "disposition_counts": counts, "cases": cases,
            "removed_exact_text_repeated_in_remaining_input": exact_repetitions,
            "evidence_type": "archived native attributes linked to new source admission only",
            "new_scores": 0}


def actor_output_diagnostics(roots, traces, physical):
    """Compare received answers before looking up any of the new native grades."""
    plan, _, _ = run.prepare()
    receipts = {**run.previous_receipts(plan), **physical}
    counts, cases = Counter(), []
    for root in roots:
        uid = root["uid"]
        trace = traces.get(uid)
        if trace is None or not any(trace["gate"].values()):
            continue
        wires, outputs = {}, {}
        for arm, view in run.ARMS:
            request = run.binding.base.actor(root, trace[view], run.binding.base.DIRECT)
            key = sha(request)
            record, answer = receipts.get((run.ACTOR, key), (None, None))
            if record is None or record["status"] != "OK" or not isinstance(answer, str) or not answer.strip():
                raise ValueError(f"Missing a usable paired Actor receipt for {uid}/{arm}")
            wires[arm] = key
            outputs[arm] = answer
        counts["active_paired_answers"] += 1
        counts["answers_differ"] += outputs[run.OPEN] != outputs[run.BOUND]
        sources = {source["memory_id"]: source["text"] for source in root["original_sources"]}
        exact_names = []
        for mid, reason in trace["gate"].items():
            relation = trace["typed"][mid]
            if reason != "INCOMPATIBLE_COMMUNICATION_ACT" or relation["source_act"] != "ADDRESS":
                continue
            aliases = re.findall(r'["“]([^"”]+)["”]', sources[mid])
            if len(aliases) != 1:
                counts["removed_address_source_without_one_literal"] += 1
                continue
            [name] = aliases
            pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
            hits = {arm: len(pattern.findall(answer)) for arm, answer in outputs.items()}
            counts[f"address_literal_present/{bool(hits[run.OPEN])}->{bool(hits[run.BOUND])}"] += 1
            exact_names.append({"memory_id": mid, "literal": name, "whole_word_occurrences": hits})
        pictographs = {}
        for mid, reason in trace["gate"].items():
            if reason == "REGISTER_NOT_SUPPORTED_FOR_DELIVERY" and re.search(r"\bemojis?\b", sources[mid], re.IGNORECASE):
                pictographs[mid] = {arm: len(re.findall(r"[\U0001F300-\U0001FAFF]", answer))
                                    for arm, answer in outputs.items()}
                before, after = (pictographs[mid][arm] for arm in (run.OPEN, run.BOUND))
                counts[f"emoji_range_present/{bool(before)}->{bool(after)}"] += 1
        cases.append({"uid": uid, "actor_wire_sha256": wires, "edit_surface": exact_names,
                      "emoji_range_counts": pictographs,
                      "answers": {arm: {"sha256": sha(answer), "characters": len(answer)}
                                  for arm, answer in outputs.items()}})
    return {"counts": counts, "cases": cases, "score_status": "no new grades used",
            "interpretation": "Literal surface checks, not benchmark labels or a complete style audit."}


def metric_availability(cases, rows, traces):
    """Check availability separately for the attribute set and task completeness."""
    def label(raw):
        try:
            value = parse_object(raw).get("label")
        except (TypeError, ValueError, AttributeError):
            return None
        return value if value in ("follow", "do_not_follow") else None

    common = {metric: [] for metric in ("MR", "AAR", "completeness")}
    by_attribute, missing = Counter(), Counter()
    for uid, case in cases.items():
        ref = run.read(run.archive.bench.ROOT / case["evaluation_path"])
        if digest(ref) != case["evaluation_hash"]:
            raise ValueError(f"BenchPreS evaluation reference changed: {uid}")
        attributes, permitted = ref["preference_attribute"], ref["preference_label"]
        pair, attribute_labels = [], []
        for arm, _ in run.ARMS:
            row = rows[uid, arm]
            raw = row.get("raw_scores", {})
            rating = re.search(r"Rating:\s*\[\[([1-5])\]\]\s*$", raw.get("BenchComplete", ""))
            labels = [label(raw.get(f"BenchAttr{i}")) for i in range(len(attributes))]
            attribute_labels.append(labels)
            observed = metric_set(attributes, permitted, labels, int(rating.group(1)) if rating else None)
            if row["score"]:
                score = row["score"]
                for name in ("aar", "mr"):
                    if observed[f"{name.upper()}_count"] != [score[f"{name}_numerator"], score[f"{name}_denominator"]]:
                        raise ValueError(f"Metric-specific parse differs from joint score: {uid}/{arm}/{name}")
                if observed["completeness"] != score["task_completeness"]:
                    raise ValueError(f"Metric-specific task rating differs: {uid}/{arm}")
            pair.append(observed)
        left, right = pair
        group = case["analysis_group_id"]
        for metric in ("MR", "AAR"):
            x, y = (value[f"{metric}_count"] for value in pair)
            if x is not None and y is not None:
                common[metric].append((group, x[0], y[0], x[1]))
        if left["completeness"] is not None and right["completeness"] is not None:
            common["completeness"].append((group, left["completeness"], right["completeness"], 1))
        active = any(traces.get(uid, {}).get("gate", {}).values())
        for appropriate, a, b in zip(permitted, *attribute_labels, strict=True):
            key = f"{'active' if active else 'inactive'}/{'appropriate' if appropriate else 'inappropriate'}"
            if a is None or b is None:
                missing[key] += 1
            else:
                by_attribute[f"{key}/{a}->{b}"] += 1
    return {"complete_metrics": {metric: paired_summary(values) for metric, values in common.items()},
            "individual_attribute_transitions": by_attribute, "unpaired_attributes": missing}


def pending_metrics(roots, traces, physical):
    """Use the same grading adapter but represent unissued rows without dispatch."""
    plan, _, jobs = run.prepare()
    cache = {**run.previous_receipts(plan), **physical}

    def lookup(wires):
        returned = {}
        for key, request in wires.items():
            digest_value = sha(request)
            receipt, answer = cache.get((key[2], digest_value), (
                {"status": "NO_RECEIPT", "request_sha256": digest_value}, None))
            returned[key] = {**receipt, "answer": answer}
        return returned

    replayed = run.evaluate(plan, roots, jobs, lookup, {})
    rows = {(row["uid"], row["method"]): row for row in replayed["rows"]}
    cases, _, _ = run.archive.context(run.BENCH)
    return {"provisional": True, "new_model_calls": 0, "fully_scored_by_arm": replayed["valid"],
            **metric_availability(cases, rows, traces)}


def terminal(roots, traces, physical):
    folder = run.OUT / run.BENCH
    state, saved = (run.read(folder / name) for name in ("RUN_STATE.json", "SETTLED.json"))
    ledger = {(r["unit"]["stage"], r["request_sha256"]): r for r in saved["ledger"]}
    if (state["state"] != "COMPLETE" or state["physical_requests"] != len(physical)
            or len(saved["ledger"]) != len(ledger) or ledger != {key: pair[0] for key, pair in physical.items()}
            or any(r["status"] == "PENDING_DELIVERY_UNKNOWN" for r in ledger.values())):
        raise ValueError("Terminal figure is not backed by settled durable receipts")
    rows = {(r["uid"], r["method"]): r for r in saved["rows"]}
    if len(rows) != len(saved["rows"]) or rows.keys() != {(r["uid"], arm) for r in roots for arm, _ in run.ARMS}:
        raise ValueError("Terminal BenchPreS rows differ from the frozen panel")
    cases, _, _ = run.archive.context(run.BENCH)
    pair_cohorts = {"active": [], "unchanged": []}
    counts, changed, cells = Counter(), [], []
    for root in roots:
        uid = root["uid"]
        plain, bound = (rows[uid, arm] for arm, _ in run.ARMS)
        trace = traces.get(uid)
        active = trace is not None and any(trace["gate"].values())
        if plain["actor_sha256"] == bound["actor_sha256"] and (
                plain["answer"], plain["score"]) != (bound["answer"], bound["score"]):
            raise ValueError("Identical Actor requests produced inconsistent settlement rows")
        cohort = "active" if active else "unchanged"
        cells.append({"uid": uid, "cohort": cohort, "score_available": {
            arm: bool(row["score"]) for (arm, _), row in zip(run.ARMS, (plain, bound), strict=True)}})
        if not (plain["score"] and bound["score"]):
            continue
        pair_cohorts[cohort].append((cases[uid], plain["score"], bound["score"]))
        removed = {m["memory_id"]: m["text"] for m in root["original_sources"]
                   if trace["gate"].get(m["memory_id"])}
        base = {d["preference"]: d for d in plain["score"]["decisions"]}
        treatment = {d["preference"]: d for d in bound["score"]["decisions"]}
        if not (base.keys() == treatment.keys() and len(base) == len(plain["score"]["decisions"])
                == len(bound["score"]["decisions"])):
            raise ValueError("Native attribute rosters are not aligned one-to-one")
        for text, before in base.items():
            after = treatment[text]
            if before["appropriate"] != after["appropriate"]:
                raise ValueError("The scorer used different appropriateness references")
            disposition = "removed" if text in removed.values() else "not_removed"
            change = f"{before['label']}->{after['label']}"
            counts[f"{before['appropriate']}/{disposition}/{change}"] += 1
            if before["label"] != after["label"]:
                changed.append({"uid": uid, "preference": text, "appropriate": before["appropriate"],
                                "removed": disposition == "removed", "change": change})
    paired = [(case, rows[uid, run.OPEN]["score"], rows[uid, run.BOUND]["score"])
              for uid, case in cases.items() if all(rows[uid, arm]["score"] for arm, _ in run.ARMS)]
    if (len(paired) != sum(map(len, pair_cohorts.values()))
            or run.bench_comparison(paired) != saved["comparisons"][run.OPEN]):
        raise ValueError("Diagnostic cohorts or native metrics disagree with the common panel")
    return {"common_native_roots": len(paired), "attribute_counts": counts, "changed_attributes": changed,
            "score_availability": cells, "paired_diagnostics": {
                cohort: run.bench_comparison(items) for cohort, items in pair_cohorts.items()},
            "separate_metric_availability": metric_availability(cases, rows, traces),
            "receipt_hashes_verified": len(physical), "scores_modified": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("allocation", "admission", "outputs", "pending", "terminal"))
    phase = parser.parse_args().phase
    roots, traces, receipts, audit = allocation()
    if phase == "admission":
        audit["archived_admission"] = archived_admission_diagnostics(roots, traces)
    elif phase == "outputs":
        audit["actor_output_diagnostics"] = actor_output_diagnostics(roots, traces, receipts)
    elif phase == "pending":
        audit["pending_metrics"] = pending_metrics(roots, traces, receipts)
    elif phase == "terminal":
        audit.update(terminal(roots, traces, receipts))
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
