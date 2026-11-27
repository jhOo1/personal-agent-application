"""Build the private, exposed-only CAR panel without sending model requests."""
from collections import Counter
import json
from pathlib import Path

import baselines
import qamc_paper_baseline_validation_run as source
from qamc.common import sha

from exposure_wires import rendered_projection, rp_projection

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
archive = baselines.archive
ARMS = ("WHOLE", "FREE", "COMMIT")
CAP = {"Endpoints": 56, "Opportunity": 28, "Donor": 28, "Final": 84,
       archive.engine.RPE: 36, "BenchAttrs": 192, "PersistNative": 24}


def order(card):
    return sha(["car-pilot-panel-v1", card["group"], card["root"]["uid"]])


def choose(cards, count, used):
    if not count:
        return []
    picks = []
    for card in sorted(cards, key=order):
        if card["group"] in used:
            continue
        used.add(card["group"])
        picks.append(card)
        if len(picks) == count:
            return picks
    raise ValueError("Too few distinct eligible source groups")


def build_rpe():
    cards = baselines.rpe()
    plan = archive.read(archive.v41.formal.OUT / "PLAN.json")
    if any(r["independent_confirmation"] for r in plan["cases"]):
        raise ValueError("Unexpected confirmation tasks on the RPEval panel")
    bank = {r["uid"]: r for r in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
            if r["uid"] in cards and r["method"] == archive.engine.RP}
    endpoints = {r["uid"]: r for r in archive.read(REPORTS / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    early = archive.read(REPORTS / "counterfactual_rpeval_v41_task_only/FROZEN.json")["ready"]
    ready = {}
    for uid, c in cards.items():
        h, ep = bank[uid], endpoints[uid]
        full = h["actor_request"]
        empty = rp_projection(full, [])
        t = ep["no_history_state"]["answer"]
        if not t or (ep["task_wire_sha256"] or early.get(uid, {}).get("task_wire_sha256")) != sha(empty):
            continue
        if not ep["task_wire_sha256"] and early[uid]["answer_sha256"] != sha(t):
            raise ValueError("Task-only completion does not match frozen answer")
        if h.get("actor_status") != "OK" or h["actor_request_sha256"] != sha(full) or not h["answer"]:
            raise ValueError("RP completion does not match frozen request")
        ready[uid] = {**c, "origin_wire": full, "T": empty, "H": full,
                      "reused": {"T": t, "H": h["answer"]}}
    pairs = archive.read(REPORTS / "soft_only_nested_contrasts_v1/PAIRS.json")["pairs"]
    use = [p for p in pairs if p["all_A"] in ready and p["only_B_added"] in ready]
    def pair_order(p):
        named = p["only_B_added"].endswith(("/explicit/112", "/explicit/069"))
        return not named, sha(["car-soft-pair-v1", p["root"]])
    result, groups = [], set()
    for pair in sorted(use, key=pair_order):
        left, right = ready[pair["all_A"]], ready[pair["only_B_added"]]
        if left["group"] != right["group"] or left["stratum"] != "all_A" or right["stratum"] != "B_only":
            raise ValueError("Paired RPEval roster changed")
        if left["group"] in groups:
            continue
        result.extend((left, right))
        groups.add(left["group"])
        if len(groups) == 4:
            break
    if len(groups) != 4:
        raise ValueError("Expected four archived soft-preference contrasts")
    for stratum in ("contains_C", "all_A"):
        result.extend(choose((r for r in ready.values() if r["stratum"] == stratum), 2, groups))
    return result


def project_bench_or_persist(card, chosen, bridge, notes=None):
    bench = card["benchmark"] == "BenchPreS"
    template = bridge.blobs["GEPA" if bench else "RUBRIC"].decode()
    wire = card["origin_wire"]
    values = [r["text"] for r in card["root"]["original_sources"]]
    return rendered_projection(wire, values, chosen,
                               lambda history: bridge.render(history, wire["model"], template),
                               archived_positions=card["archived_positions"],
                               bench_guidance=(notes or {}) if bench else None)


def build_transfer(name, bridge):
    bank = baselines.transfer(name)
    cases, _, _ = archive.transfer.context(name)
    rows = archive.transfer.archived_answers(name, bank)
    strong_name = archive.engine.GATE if name == "BenchPreS" else "PB_RUBRIC"
    strong = {r["uid"]: r for r in rows if r["method"] == strong_name}
    if name == "BenchPreS":
        pool = list(bank.values())
        # Target headroom on half the profiles while preserving different profile roots.
        target = [c for c in pool if c["base_score"]["aar_numerator"] < c["base_score"]["aar_denominator"]]
        used = set()
        headroom = min(4, len({c["group"] for c in target}))
        chosen = choose(target, headroom, used) + choose(pool, 8 - headroom, used)
    else:
        used = set()
        chosen = []
        for category, count in (("sycophancy", 3), ("cross_domain", 2), ("beneficial_memory_usage", 3)):
            chosen.extend(choose((r for r in bank.values() if r["stratum"] == category), count, used))
    out = []
    for c in chosen:
        uid = c["root"]["uid"]
        case, old = cases[uid], strong[uid]
        if case.get("independent_confirmation") or case.get("role", "DEV") != "DEV":
            raise ValueError("Cannot use confirmation tasks")
        if sha(old["actor_request"]) != old["actor_request_sha256"] or old["answer"] != c["base_answer"]:
            raise ValueError("Archived strong answer changed")
        sources = c["root"]["original_sources"]
        index = {r["memory_id"]: i for i, r in enumerate(sources)}
        if len(index) != len(sources):
            raise ValueError("Ambiguous source IDs")
        if name == "BenchPreS":
            visible = old["view"]["source_evidence"]
            positions = [index[r["memory_id"]] for r in visible]
            if [sources[i] for i in positions] != visible or positions != sorted(positions):
                raise ValueError("Strong Gate used different archived sources")
        else:
            positions = list(range(len(sources)))
        card = {**c, "origin_wire": old["actor_request"], "archived_positions": positions}
        reconstructed = project_bench_or_persist(card, positions, bridge)
        if reconstructed != card["origin_wire"]:
            raise ValueError("Original strong renderer contract changed")
        eps = {"T": project_bench_or_persist(card, [], bridge),
               "H": project_bench_or_persist(card, range(len(sources)), bridge)}
        exact = {sha(old["actor_request"]): old["answer"]}
        for other in rows:
            if other["uid"] != uid or other.get("actor_status") != "OK" or not other.get("actor_request"):
                continue
            digest = sha(other["actor_request"])
            if digest in {sha(w) for w in eps.values()} and digest not in exact:
                if digest != other["actor_request_sha256"]:
                    raise ValueError("Unverified archived endpoint")
                exact[digest] = other["answer"]
        out.append({**card, **eps, "reused": {k: exact[sha(w)] for k, w in eps.items() if sha(w) in exact}})
    return out


def build():
    bridge = source.PersistAuthorBridge(source.previous.parent.AUTHOR)
    rows = build_rpe() + build_transfer("BenchPreS", bridge) + build_transfer("PersistBench", bridge)
    counts = Counter(c["benchmark"] for c in rows)
    groups = Counter(b for b, _ in {(c["benchmark"], c["group"]) for c in rows})
    if counts != {"RPEval": 12, "BenchPreS": 8, "PersistBench": 8} or set(groups.values()) != {8}:
        raise ValueError("CAR roster differs from the development allocation")
    return rows


def inventory(rows):
    return {b: {"tasks": len(pool), "groups": len({r["group"] for r in pool}),
                "strata": dict(Counter(r["stratum"] for r in pool)),
                "reusable_endpoints": dict(Counter(k for r in pool for k in r["reused"])),
                "new_endpoint_jobs": sum(2 - len(r["reused"]) for r in pool)}
            for b in ("RPEval", "BenchPreS", "PersistBench")
            if (pool := [r for r in rows if r["benchmark"] == b])}


if __name__ == "__main__":
    print(json.dumps(inventory(build()), indent=2, sort_keys=True))
