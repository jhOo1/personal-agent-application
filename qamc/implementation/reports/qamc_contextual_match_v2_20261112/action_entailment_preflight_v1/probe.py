"""Offline eligibility check for answer-side natural-language action verification."""
import hashlib
import json
from pathlib import Path
import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"
MAX = 512
WINDOW = 384
THRESHOLD = 0.70


def load(relative):
    return json.loads((PARENT / relative).read_text())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def unique(rows, id_fragment, method=None):
    row, = (r for r in rows if id_fragment in r["uid"] and (method is None or r["method"] == method))
    if "actor_status" in row and row["actor_status"] != "OK":
        raise ValueError(f"Missing archived answer for {id_fragment}")
    return row


def cases():
    rp = "RPR_PAPER_FULL"
    rpe = load("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
    mg = load("native_residual_v1/rpe_memgate_bridge_v1/RESULTS.json")["rows"]
    participants = load("participant_constraints_v1/RESULTS.json")["rows"]
    air = load("answer_intent_round_trip_v1/FROZEN_PANEL.json")["roots"]
    bench = load("paper_baseline_validation_156_v1/SAVED_OPPONENT_ROWS.json")
    return {
        "child_outing": (
            ("方案推荐孩子参加手工制作活动。", "方案排除剪纸、粘贴等手工制作活动。"),
            (("recommended", unique(mg, "/implicit/146")["answer"]),
             ("excluded", unique(rpe, "/implicit/146", rp)["answer"]))),
        "seafood_takeout": (
            ("方案推荐吃鱼或虾作为主菜。", "方案禁止海鲜主菜及含海鲜成分的配料。"),
            (("recommended", unique(rpe, "/implicit/004", rp)["answer"]),
             ("excluded", unique(rpe, "/implicit/004", "MEMADAPTER_FULL")["answer"]))),
        "group_lunch": (
            ("The main recipe calls for adding sliced onion.",
             "The main recipe omits solid onion and garlic as ingredients."),
            (("recommended", unique(participants, "65666d8d", "MEMGATE_FIXED")["answer"]),
             ("excluded", unique(participants, "65666d8d", "PARTICIPANT_CONSTRAINTS")["answer"]))),
        "book_club": (
            ("The primary venue proposal puts Alex in the same room as the cat.",
             "The invitation chooses a cat-free venue as the primary plan."),
            (("recommended", unique(air, "dbcf603f")["draft"]),
             ("uncommitted", unique(participants, "dbcf603f", "PARTICIPANT_CONSTRAINTS")["answer"]))),
        "formal_signature": (
            ("The formal email is signed using the sender's nickname Rocky.",
             "The formal email is signed with the sender's full name instead of the nickname."),
            (("recommended", unique(bench, "29b7ae84", rp)["answer"]),
             ("excluded", unique(bench, "29b7ae84", "DES2GEN_FULL")["answer"]))),
    }


def windows(tokenizer, answer):
    count = lambda s: len(tokenizer(s, add_special_tokens=False)["input_ids"])
    result, current = [], ""
    for line in answer.splitlines(keepends=True):
        if current and count(current + line) > WINDOW:
            result.append(current)
            current = ""
        current += line
    if current:
        result.append(current)
    if "".join(result) != answer:
        raise ValueError("Premise segment text drift")
    return result


def evaluate():
    started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL, revision=REVISION, local_files_only=True).eval()
    entailment, = (k for k, v in model.config.id2label.items() if v.casefold() == "entailment")
    torch.set_num_threads(4)
    rows = []
    for case, (hypotheses, inputs) in cases().items():
        for role, answer in inputs:
            parts = windows(tokenizer, answer)
            if not parts:
                raise ValueError("Empty archived answer")
            for view, premises in (("head", [answer]), ("windows", parts)):
                result = []
                for premise in premises:
                    counts = [len(tokenizer(premise, h)["input_ids"]) for h in hypotheses]
                    if view == "windows" and max(counts) > MAX:
                        raise ValueError(f"Over-limit whole-line window in {case}")
                    options = {"truncation": "only_first", "max_length": MAX} if view == "head" else {}
                    input_ids = tokenizer([premise] * 2, list(hypotheses), padding=True,
                                          return_tensors="pt", **options)
                    with torch.inference_mode():
                        probs = model(**input_ids).logits.softmax(-1).tolist()
                    result.append({"premise_sha256": digest(premise), "tokens_before_cap": counts,
                                   "scores": [{model.config.id2label[i]: x for i, x in enumerate(p)}
                                              for p in probs]})
                label = model.config.id2label[entailment]
                best = [max(w["scores"][i][label] for w in result) for i in range(2)]
                decision = ("ambiguous" if min(best) >= THRESHOLD else "recommended" if best[0] >= THRESHOLD
                            else "excluded" if best[1] >= THRESHOLD else "uncommitted")
                rows.append({"case": case, "expected": role, "answer_sha256": digest(answer),
                             "view": view, "windows": result, "entailment": best, "decision": decision})
    return {"model": MODEL, "revision": REVISION, "threshold": THRESHOLD, "rows": rows,
            "elapsed_seconds": round(time.monotonic() - started, 3), "api_requests": 0}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
