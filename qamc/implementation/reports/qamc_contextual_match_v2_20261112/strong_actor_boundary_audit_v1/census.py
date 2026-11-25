"""Count where legitimate preferences were lost on the exact reference paths."""
import json
from collections import Counter
from pathlib import Path
import re
import unicodedata

from qamc.common import sha
import run_patches as prior

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
read = prior.probe.read
transfer = prior.engine.transfer


def normalized(text):
    value = unicodedata.normalize("NFKC", str(text)).casefold()
    return " ".join(re.findall(r"\w+", value))


def actor_row(row):
    if row.get("actor_status") != "OK" or not row.get("answer"):
        raise ValueError("Missing successful Actor endpoint")
    if sha(row["actor_request"]) != row["actor_request_sha256"]:
        raise ValueError("Actor hash mismatch")
    return row


def rpe():
    archive = prior.R["archived"]
    frozen = read(archive.v41.OUT / "FROZEN.json")
    roots = {r["uid"]: r for r in frozen["roots"]}
    inspect = read(BASE / "counterfactual_rpeval_v41_task_only/RESULTS.json")
    labels = {r["uid"]: r["labels"] for r in inspect["roots"]}
    frontier = read(BASE / "selective_path_frontier_v1/RESULTS.json")["rows"]
    original = read(archive.v41.formal.OUT / "RESULT_ROWS.json")
    actors = {r["uid"]: r for r in original if r["method"]=="RPR_PAPER_FULL" and r["uid"] in roots}
    counts, by_root = Counter(), []
    for card in frontier:
        uid, route = card["uid"], card["base"]
        root = roots[uid]
        sources = root["original_sources"]
        annotation = labels[uid]
        if len(sources) != len(annotation) or len({s["memory_id"] for s in sources}) != len(sources):
            raise ValueError("Invalid RPEval original-source alignment")
        if route == "TASK_ONLY":
            packet = json.loads(archive.v41.task_only_request(root)["messages"][1]["content"])
            if packet["source_evidence"] or packet["preference_use_policy"]:
                raise ValueError("Task-only history scope changed")
        else:
            row = actor_row(actors[uid])
            if sha(row["answer"].strip()) != card["cells"][route]["answer_sha256"]:
                raise ValueError("Different RPEval draft")
            packet = json.loads(row["actor_request"]["messages"][1]["content"])
        text = {s["memory_id"]: s["text"] for s in packet.get("source_evidence", [])}
        action = {s["memory_id"]: s["policy"] for s in packet.get("preference_use_policy", [])}
        row = {"uid": uid, "group": card["source_group"], "route": route, "stratum": card["stratum"],
               "positions": [], "base_scores": card["cells"][route]}
        for source, label in zip(sources, annotation, strict=True):
            sid = source["memory_id"]
            if sid in text and source["text"] != text[sid]:
                raise ValueError("Visible source is not verbatim")
            state = "HIDDEN" if sid not in text else "VISIBLE_" + action.get(sid, "UNDECLARED")
            counts[(label, state)] += 1
            row["positions"].append({"id": sid, "author_label": label, "state": state,
                                     "source_sha256": sha(source["text"])})
        by_root.append(row)
    return {"counts": {f"{a}/{b}": n for (a,b),n in sorted(counts.items())},
            "roots": by_root, "groups": len({r["group"] for r in by_root})}


def bench():
    cases, _, controls = transfer.context("BenchPreS")
    old = {r["uid"]: actor_row(r) for r in transfer.archived_answers("BenchPreS", cases)
           if r["method"] == "GEPA_SELECTED_BOUNDS" and r["actor_status"] == "OK"}
    control = {(r["uid"], r["method"]): r["score"] for r in controls}
    rows, counts = [], Counter()
    for uid, case in cases.items():
        base = control.get((uid,"GEPA_SELECTED_BOUNDS"))
        if not base or uid not in old:
            continue
        a = old[uid]
        payload = json.loads(a["actor_request"]["messages"][1]["content"])
        audit = a["input_audit"]
        selected = audit["compiled_original_texts_in_author_order"]
        system = a["actor_request"]["messages"][0]["content"]
        if not all(normalized(text) in normalized(system) for text in selected):
            raise ValueError("BenchPreS selected text not present in actual system message")
        facts = [normalized(x) for x in payload["fixed_facts"]]
        for index, obj in enumerate(base["decisions"]):
            if not obj["appropriate"] or "bold text" in obj["preference"].lower():
                continue
            phrase = normalized(obj["preference"])
            excerpt = [text for text in selected if phrase in normalized(text)]
            exact = ("SELECTED_EXACT" if excerpt else "FACTS_EXACT" if any(phrase in f for f in facts)
                     else "NO_EXACT_EXPRESSION")
            counts[f"{obj['label']}/{exact}"] += 1
            target = {"uid": uid, "profile_group": case["analysis_group_id"], "position": index,
                      "preference": obj["preference"], "base_follow": obj["label"], "expression": exact,
                      "actor_request_sha256": a["actor_request_sha256"], "answer_sha256": sha(a["answer"]),
                      "comparators": {}}
            for method in ("PAPER_SELECTIVITY", "RPR_PAPER_FULL"):
                other = control.get((uid,method))
                if other:
                    value = other["decisions"][index]
                    if (value["preference"], value["appropriate"]) != (obj["preference"], obj["appropriate"]):
                        raise ValueError("BenchPreS preference alignment failed")
                    target["comparators"][method] = value["label"]
            rows.append(target)
    return {"counts": dict(sorted(counts.items())), "attributes": rows}


def persist():
    cases, _, controls = transfer.context("PersistBench")
    archive = {r["uid"]: actor_row(r) for r in transfer.archived_answers("PersistBench", cases)
               if r["method"]=="PB_RUBRIC" and r["actor_status"]=="OK"}
    rows = []
    for row in controls:
        if row["method"] != "PB_RUBRIC" or row["score"] is None or row["uid"] not in archive:
            continue
        uid = row["uid"]
        rows.append({"uid": uid, "group": cases[uid]["group_id"], "category": cases[uid]["category"],
                     "actor_request_sha256": archive[uid]["actor_request_sha256"],
                     "answer_sha256": sha(archive[uid]["answer"]), "score": row["score"]})
    return {"roots": rows}


if __name__ == "__main__":
    print(json.dumps({"RPEval": rpe(), "BenchPreS": bench(), "PersistBench": persist()},
                     ensure_ascii=False, indent=2))
