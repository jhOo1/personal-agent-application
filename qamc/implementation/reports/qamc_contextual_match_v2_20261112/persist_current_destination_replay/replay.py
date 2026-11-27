"""Verify removal of one exposed inadmissible PersistBench memory against archived requests."""
from collections import Counter
import json
from pathlib import Path
import sys

from qamc.common import sha

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "persist_frozen_utility_review_v1"))
sys.path.insert(0, str(BASE / "persist_selected_gepa_completion_v1"))

from compare_controls import load_verified_scores
from complete import ROOT, archive, get_author, read
from extend import archived, receipt
from persist_grounding_gepa_wires import actor_request, select

TRAVEL = "persistbench/b664c8fa3f62042540fd"
CHAPTER = "persistbench/36bd0c4f04c3245067e2"
REPLAY_CASES = (TRAVEL, CHAPTER)
METHOD = "SELECTED_GEPA"


def find_wires(source, uid):
    output = {}
    for stage in ("QueryRoute", "EvidenceSelect", "FinalActor"):
        pin, = [u for u in read(source / (stage + "_MANIFEST.json"))["units"]
                if u["unit"]["root_id"] == uid and u["unit"]["method"] == METHOD]
        output[stage] = pin["request"]
    return output


def main():
    selected, controls = load_verified_scores()
    assert (len(selected), sum(archive["passes"](s, c) for c, s in selected.values())) == (49, 47)
    cases = {row["uid"]: row for row in read(BASE / "persist_author_controls_v2/PLAN.json")["cases"]
             if row["role"] == "DEV" and row["uid"] in REPLAY_CASES}
    if set(cases) != set(REPLAY_CASES):
        raise ValueError("All replay cases must be in the exposed author manifest")
    factorial = read(ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    src = BASE / "native_residual_v1/persist_performance_v1"
    selector_wires = find_wires(src, TRAVEL)
    plan, stored_envelopes, _ = get_author()
    selected_answer, = [r["answer"] for r in archive["supplementary"](src, stored_envelopes, Counter())[0]
                        if r["uid"] == TRAVEL and r["method"] == METHOD]
    run = ROOT / "runs" / BASE.name / src.name
    route = receipt(run, "QueryRoute", TRAVEL, selector_wires["QueryRoute"])
    chosen = receipt(run, "EvidenceSelect", TRAVEL, selector_wires["EvidenceSelect"])
    data = json.loads(selector_wires["EvidenceSelect"]["messages"][-1]["content"])
    public = {"query": data["query"], "memories": [row["text"] for row in data["memories"]]}
    if sha(public) != cases[TRAVEL]["public_sha256"]:
        raise ValueError("Travel task public inputs changed")
    kept = select(cases[TRAVEL], public, route, chosen)
    original = actor_request(cases[TRAVEL], public["query"], kept, factorial, factorial["prompts"]["gepa"])
    if (original != selector_wires["FinalActor"] or
            receipt(run, "FinalActor", TRAVEL, original) != selected_answer):
        raise ValueError("Travel Actor reconstruction changed")
    source = public["memories"][10]
    if kept.count(source) != 1:
        raise ValueError("Expected single included copy of travel source M11")
    ablated = [text for text in kept if text != source]
    wire = actor_request(cases[TRAVEL], public["query"], ablated, factorial, factorial["prompts"]["gepa"])
    if wire == original or source in wire["messages"][0]["content"]:
        raise ValueError("Unrelated history still reaches the ablated Actor")
    if (wire["messages"][-1] != original["messages"][-1] or
            any(wire[k] != v for k, v in original.items() if k != "messages")):
        raise ValueError("Ablation altered task or Actor envelope")
    author_wire, = [r["actor_request"] for r in plan if r["uid"] == TRAVEL and r["method"] == "PB_NO_MEMORY"]
    exact, scan = archived({(TRAVEL, "REMOVE_M11"): wire}, ROOT)
    saved = exact.get((TRAVEL, "REMOVE_M11"))

    chapter_wire = factorial["jobs"][CHAPTER][METHOD]["request"]
    chapter_score, = [r for r in archive["factorial"](stored_envelopes, Counter())[0] if r["uid"] == CHAPTER]
    chapter_evidence = factorial["evidence"][CHAPTER]
    rebuilt = actor_request(cases[CHAPTER], chapter_wire["messages"][-1]["content"], chapter_evidence,
                            factorial, factorial["prompts"]["gepa"])
    author_chapter, = [r for r in plan if r["uid"] == CHAPTER and r["method"] == "PB_NO_MEMORY"]

    print(json.dumps({
        "model_calls": 0,
        "travel": {
            "sources_before": len(kept), "sources_after": len(ablated),
            "actor_request_sha256": sha(original), "ablated_request_sha256": sha(wire),
            "same_as_author_empty": wire == author_wire,
            "exact_actor_archive": None if saved is None else {
                "origin": saved["archive"], "status": saved["status"], "answer_sha256": sha(saved["answer"])},
            "actor_model": wire["model"], "actor_max_tokens": wire["max_tokens"],
            "author_empty_max_tokens": author_wire["max_tokens"],
            "searched_sqlite_journals": scan, "old_ratings": {
                name: s["rating"] for name, s in controls[TRAVEL].items()},
            "selected_rating": selected[TRAVEL][1]["rating"],
        },
        "chapter": {
            "selected_sources": len(chapter_evidence), "same_as_author_empty": chapter_wire == author_chapter["actor_request"],
            "actor_request_verified": chapter_wire == rebuilt and sha(chapter_wire) == chapter_score["actor_request_sha256"],
            "selected_rating": chapter_score["score"]["rating"], "author_empty_rating": author_chapter["score"]["rating"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
