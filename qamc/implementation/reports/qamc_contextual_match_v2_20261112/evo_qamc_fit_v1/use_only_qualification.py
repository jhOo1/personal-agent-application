"""Inventory genuine existing option and operand evidence in exposed inputs."""
from collections import Counter
import json
from pathlib import Path
import re

from blind_behavior_packet import BASE, RUNS, read, write_private
from check_exposure_fr3 import prepare

ALTERNATIVES = re.compile(
    r"还是|或者|二选[一二]|选哪|(?:^|\n)\s*(?:[A-D][.)]|\d+[.)、])\s+|"
    r"\b(?:choose between|either|versus|vs\.?|options? (?:are|include)|or)\b", re.I)
OPERANDS = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"(?:[$€£¥￥]\s*\d|\d+(?:\.\d+)?\s*(?:元|公里|千米|小时|分钟|dollars?|hours?|minutes?))", re.I)
ENUMERATION = re.compile(r"(?:^|\n)\s*(?:[A-D][.)]|\d+[.)、])\s+")
OUTPUT = RUNS / "use_only_qualification_v1" / "private"


def option_signal(text):
    return bool(ALTERNATIVES.search(text) or len(ENUMERATION.findall(text)) >= 2)


def numeric_signal(text):
    return bool(OPERANDS.search(text))


def pools():
    directory = BASE / "rpeval_formal_multi_coverage_v1"
    plan = read(directory / "PLAN.json")
    roster = {case["uid"] for case in plan["cases"] if case["independent_confirmation"] is False}
    cases = read(directory / "PUBLIC_TASKS.json")
    if len(roster) != 300 or roster != cases.keys():
        raise ValueError("RPEval development roster mismatch")
    yield "RPEval", {uid: {"query": c["query"], "context": c["current_context"],
                         "facts": c["fixed_facts"], "memory": [m["text"] for m in c["memories"]]}
                     for uid, c in cases.items()}
    persist, inputs, *_ = prepare()
    yield "PersistBench", {uid: {"query": inputs[uid]["public"]["query"], "context": "", "facts": [],
                               "memory": inputs[uid]["public"]["memories"]} for uid in persist}
    backbone = RUNS / "evo_qamc_fit_v1_backbone_interface_v1" / "private"
    # Read task input only. Multiple trusted snapshots must agree on all original fields.
    bench = {}
    for path in sorted(backbone.glob("BEHAVIOR_SNAPSHOT_*.json")):
        for uid, case in read(path).items():
            if case["benchmark"] != "BenchPreS":
                continue
            task = case["task"]
            plan = case["arms"]["Q/PLAN/SELECTED"]["plan"]
            card = {"query": task["query"], "context": task["current_context"],
                    "facts": task["facts"], "plan": plan, "memory": [
                v["text"] for v in case["arms"]["Q/PLAN/SELECTED"]["source_evidence"]]}
            if card != bench.setdefault(uid, card):
                raise ValueError("BenchPreS frozen input identity drifted")
    if len(bench) != 4:
        raise ValueError("Require the four frozen exposed BenchPreS profiles")
    yield "BenchPreS", bench


def main():
    totals = {}
    candidates = {}
    for name, cards in pools():
        count = Counter(assigned=len(cards))
        for uid, card in cards.items():
            task = "\n".join((card["query"], card["context"] or ""))
            alternative = option_signal(task)
            current_operand = numeric_signal(task)
            auxiliary_operand = any(map(numeric_signal, card["facts"] + card["memory"]))
            count.update(task_option_signal=int(alternative), current_operand_signal=int(current_operand),
                         auxiliary_operand_signal=int(auxiliary_operand),
                         option_and_auxiliary_operand_signal=int(alternative and auxiliary_operand))
            if alternative or current_operand or name == "BenchPreS":
                candidates[uid] = {"benchmark": name, "task_option_signal": alternative,
                                   "current_operand_signal": current_operand,
                                   "auxiliary_operand_signal": auxiliary_operand, **card}
        totals[name] = dict(count)
    OUTPUT.mkdir(parents=True, mode=0o700, exist_ok=True)
    write_private("INPUT_SCREEN.json", candidates, output=OUTPUT)
    print(json.dumps({"counts": totals, "retained_for_input_inspection": len(candidates),
                      "model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
