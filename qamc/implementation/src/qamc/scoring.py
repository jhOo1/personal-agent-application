"""Native scoring definitions with an explicitly labeled Qwen judge variant."""
from __future__ import annotations

import ast
import json
import re
import string
from collections import Counter

import numpy as np
import regex
from nltk.stem import PorterStemmer

from .common import ROOT
from .memsyco_official_bridge import judge_spec, metric_map, parse_judge


def load_functions(path, roots, ns):
    source = path.read_text()
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    names, todo = set(roots), list(roots)
    while todo:
        for node in ast.walk(functions[todo.pop()]):
            if isinstance(node, ast.Name) and node.id in functions and node.id not in names:
                names.add(node.id)
                todo.append(node.id)
    text = "from __future__ import annotations\n" + "\n\n".join(ast.get_source_segment(source, functions[n]) for n in names)
    exec(compile(text, str(path), "exec"), ns)
    return ns


LME = load_functions(ROOT / "vendor/LongMemEval/src/evaluation/evaluate_qa.py", ["get_anscheck_prompt"], {})
LOCOMO = load_functions(ROOT / "vendor/locomo/task_eval/evaluation.py", ["eval_question_answering"],
                       {"regex": regex, "json": json, "string": string, "np": np, "Counter": Counter, "ps": PorterStemmer()})


class Scorer:
    def __init__(self, gateway):
        self.gateway = gateway

    def score(self, case, reference, answer, key):
        if case["benchmark"] == "memsyco":
            prompt, payload = judge_spec(case["category"], reference, answer)
            reply = self.gateway.complete(key + "/judge", prompt, payload, 4096)
            native = parse_judge(case["category"], reference, answer, reply)
            if not native.get("judge_parse_ok"):
                raise ValueError("native_judge_contract_failed:" + json.dumps(native, ensure_ascii=False))
            return {"metric": "native_rubric_Qwen_judge_variant", "native": native,
                    "metrics": metric_map(case["category"], native), "judge_raw": reply}
        if case["benchmark"] == "longmemeval":
            prompt = LME["get_anscheck_prompt"](reference["question_type"], reference["question"],
                                                reference["answer"], answer, "_abs" in reference["question_id"])
            reply = self.gateway.complete(key + "/judge", "Follow the evaluation instruction exactly.", prompt, 4096)
            clean = reply.strip().lower().rstrip(".")
            if clean not in ("yes", "no"):
                raise ValueError("yes_no_judge_contract_failed:" + reply)
            return {"metric": "official_prompt_Qwen_judge_variant", "metrics": {"accuracy": int(clean == "yes")},
                    "judge_raw": reply}
        # Category 5 references contain adversarial_answer, not an actual answer.
        # Native scorer never reads its value in that branch; the placeholder stays evaluation-only.
        row = {**reference, "answer": reference.get("answer", ""), "prediction": answer}
        f1 = float(LOCOMO["eval_question_answering"]([row], "prediction")[0][0])
        if reference["category"] == 5:
            prompt = LME["get_anscheck_prompt"]("single-session-user", reference["question"],
                                                "The requested information is not provided by the conversation.", answer, True)
        else:
            prompt = LME["get_anscheck_prompt"]("single-session-user", reference["question"], reference["answer"], answer)
        result = {"metric": "official_F1_open_ended_input", "metrics": {"native_f1": f1, "semantic_accuracy_Qwen_variant": None},
                  "adversarial_input_variant": "open question; no gold-derived multiple choice shown"}
        try:
            reply = self.gateway.complete(key + "/semantic_judge", "Follow the evaluation instruction exactly.", prompt, 4096)
            clean = reply.strip().lower().rstrip(".")
            if clean not in ("yes", "no"):
                raise ValueError("yes_no_judge_contract_failed:" + reply)
            result.update(semantic_judge_status="ok", judge_raw=reply)
            result["metrics"]["semantic_accuracy_Qwen_variant"] = int(clean == "yes")
        except Exception as exc:
            # Native lexical scoring does not depend on availability of an optional judge.
            result.update(semantic_judge_status="failed", semantic_judge_error=str(exc))
        return result
