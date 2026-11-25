"""Export a self-contained V42 review with public benchmark inputs and actual receipts."""
from argparse import ArgumentParser
import csv
from io import StringIO
import json
from pathlib import Path

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha

import run_visibility_v42 as study
from score_task_only import OUT as TASK_ONLY, saved_drafts
from settle_visibility_v42 import settle

CHOICES = ("rpeval/formal_multi_v1/explicit/009", "rpeval/formal_multi_v1/explicit/013",
           "rpeval/formal_multi_v1/explicit/018", "rpeval/formal_multi_v1/explicit/050",
           "rpeval/formal_multi_v1/explicit/067", "rpeval/formal_multi_v1/explicit/100",
           "rpeval/formal_multi_v1/implicit/013")
FIELDS = ("OPB", "UPB", "RII", "FM", "VG", "full_match")
METHODS = ("DIRECT_MASKED", "SCOPED_FULL", "SCOPED_MASKED", study.prior.GATE, study.prior.RP, "TASK_ONLY")


def block(value, language="json"):
    body = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return f"\n\n````{language}\n{body}\n````\n"


def choose_cases(rows):
    names = {row["uid"]: row for row in rows}
    chosen = {uid: "固定退步与合法偏好轨迹" for uid in CHOICES if uid in names}
    groups = {names[uid]["group"] for uid in chosen}
    for condition in ("all_A", "mixed_BC"):
        for lhs, rhs in study.COMPARISONS[:2]:
            cells = []
            for row in rows:
                pair = [row["native"][m]["fields"].get("match") for m in (lhs, rhs)]
                if all(pair) and (set(row["labels"]) == {"A"}) == (condition == "all_A"):
                    cells.append((pair[1]["matched"] - pair[0]["matched"], row["uid"], row["group"]))
            for gain in (False, True):
                for delta, uid, group in sorted(cells, key=lambda x: ((-x[0] if gain else x[0]), x[1])):
                    if ((delta > 0 if gain else delta < 0) and group not in groups and uid not in chosen):
                        chosen[uid] = f"{condition} {lhs} → {rhs} {'正差' if gain else '负差'}"
                        groups.add(group)
                        break
    return chosen


def score_csv(rows, ref):
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("uid", "source_group", "author_labels", "less_exposed",
                     *(f"{m}.{k}" for m in METHODS for k in ("match", *FIELDS, "component_status"))))
    for row in rows:
        cells = {**row["native"], "TASK_ONLY": ref[row["uid"]]["task_only"]}
        values = [row["uid"], row["group"], row["labels"], row["in_sensitivity"]]
        for method in METHODS:
            cell = cells[method]
            match = cell["fields"].get("match")
            values.extend((f"{match['matched']}/{match['positions']}" if match else "",
                           *(cell["fields"].get(k, "") for k in FIELDS),
                           row["answers"].get(method, {}).get("status", cell.get("status", "ARCHIVED"))))
        writer.writerow(values)
    return output.getvalue()


def ledger_csv(ledger):
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("wave", "stage", "root", "method", "status", "prompt_tokens", "completion_tokens",
                     "total_tokens", "elapsed_seconds", "retries", "request_sha256"))
    for wave, entry in ledger:
        unit, usage = entry["unit"], entry["usage"] or {}
        writer.writerow((wave, unit["stage"], unit["root_id"], unit["method"], entry["status"],
                         *(usage.get(key, "") for key in ("prompt_tokens", "completion_tokens", "total_tokens")),
                         entry.get("elapsed_seconds"), entry["automatic_retries"], entry["request_sha256"]))
    return output.getvalue()


def case_bundle(row, root, reason, formal, official, grade_control, draft, anchors):
    uid = row["uid"]
    selection_wires = {m: study.selection_request(root, m) for m in study.METHOD_PROMPTS}
    wires = {arm: study.actor_request(root, row["selected"][method]["scope"], masked=masked)
             for arm, (method, masked) in study.ARMS.items() if row["selected"][method]["scope"] is not None}
    graders = {}
    for arm in wires:
        if sha(wires[arm]) != row["answers"][arm]["request_sha256"]:
            raise ValueError("Actor request drift")
        answer = row["answers"][arm]["answer"]
        if answer:
            result_row = {"uid": uid, "method": study.prior.GATE, "actor_status": "OK", "answer": answer}
            item, = study.prior.formal.grading_jobs(formal, [official], [result_row])
            graders[arm] = item["request"]
            if row["native"][arm].get("judge_sha256") and sha(item["request"]) != row["native"][arm]["judge_sha256"]:
                raise ValueError("Judge request drift")
    for method, wire in selection_wires.items():
        if sha(wire) != row["selected"][method]["request_sha256"]:
            raise ValueError("Selector request drift")
    old = {m: anchors[uid, m]["actor_request"] for m in (study.prior.GATE, study.prior.RP)}
    for method, wire in old.items():
        if sha(wire) != root["archived"][method]["actor_sha256"]:
            raise ValueError("Archived comparator request drift")
    zero = study.prior.task_only_request(root)
    if sha(zero) != root["task_wire_sha256"]:
        raise ValueError("Archived task-only request drift")
    for request in (*selection_wires.values(), *wires.values(), *graders.values(), *old.values(), zero):
        validate_public_request(request)
    return {
        "witness_sampling_reason": reason, "public_task": root["public_task"], "memory": root["original_sources"],
        "benchmark_evaluation_only_author_labels": row["labels"], "selector_requests": selection_wires,
        "selector_outputs": row["selected"], "actor_requests": wires, "answers": row["answers"],
        "native_judge_requests": graders, "native_judge_replies_and_fields": row["native"],
        "archived_actor_requests": old, "archived_answers": root["archived"], "archived_RP_policy": root["archived_policy"],
        "archived_task_only_request": zero, "archived_task_only_answer": draft["answer"],
        "archived_task_only_judge": grade_control["task_only"],
    }


def render(expected=None):
    evidence = settle(expected)
    if expected is None and evidence["completed_roots"] != 233:
        raise ValueError("Final handoff requires the complete panel")
    plan = study.read(study.prior.OUT / "FROZEN.json")
    roots = {row["uid"]: row for row in plan["roots"]}
    drafts = saved_drafts(plan)
    task_only = {row["uid"]: row for row in study.read(TASK_ONLY / "RESULTS.json")["roots"]}
    formal = study.read(study.prior.formal.OUT / "PLAN.json")
    refs = study.prior.author_cases(formal)
    rows, ledger = [], []
    for wave in evidence["wave_proofs"]:
        file = study.OUT / f"wave_{wave['wave']:02d}" / "COMPLETED.json"
        if sha(file.read_bytes()) != wave["sha256"]:
            raise ValueError("A completed wave changed during rendering")
        payload = study.read(file)
        rows.extend(payload["rows"])
        ledger.extend((wave["wave"], r) for r in payload["ledger"])
    witnesses = choose_cases(rows)
    anchors = {(r["uid"], r["method"]): r for r in study.read(study.prior.formal.OUT / "RESULT_ROWS.json")
               if r["uid"] in witnesses and r["method"] in (study.prior.GATE, study.prior.RP)}
    label = "终态" if expected is None else "阶段预览"
    start = (f"# QAMC V42 {label}证据包\n\n"
             f"已曝光开发题 {len(rows)}/233。请核对原生分、来源组有效分母、失败、排序与成本；"
             "判断前置错误许可、实际可见性和评分器分别能够解释多少差异。核对能否保住合法 B/C。"
             "请以可验证的候选和强对照为依据给出研究判断，避免根据几个例子升级算法结论。\n")
    cuts = [start, "\n## 原冻结协议\n", (study.HERE / "PROTOCOL.md").read_text(),
            "\n## 选择、绑定和成稿完整代码\n", block((study.HERE / "contract.py").read_text(), "python")]
    for name in ("mle", "ipe", "generator"):
        source = study.prior.formal.ROOT / "proposals" / "qamc_rpreasoner_paper" / (name + ".md")
        cuts.extend([f"\n## RP 原归档 {name} 提示", block(source.read_text(), "text")])
    cuts.extend(["\n## 配对结果、冻结判断与回执证据", block(evidence),
                 "\n## 其余基准的对照与协议边界\n", (study.HERE / "TRANSFER_GRADING.md").read_text()])
    for row in rows:
        uid = row["uid"]
        if uid in witnesses:
            root = roots[uid]
            cuts.extend([f"\n## 原生案例 {uid}", block(case_bundle(
                row, root, witnesses[uid], formal, refs[uid], task_only[uid], drafts[root["task_wire_sha256"]], anchors))])
    cuts.extend(["\n## 全部逐题原生分", block(score_csv(rows, task_only), "csv"),
                 "\n## 真实物理请求账本", block(ledger_csv(ledger), "csv")])
    return "".join(cuts), len(witnesses)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected", type=int, help="Render an explicitly labeled partial preview.")
    args = parser.parse_args()
    text, witnesses = render(args.expected)
    with args.path.open("x", encoding="utf-8") as handle:
        handle.write(text)
    print(f"{witnesses} native witnesses, {len(text.encode())} bytes, sha256={sha(text)}")
