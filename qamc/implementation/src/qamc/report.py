"""Offline, denominator-preserving reports; importing this module never calls a model."""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
from pathlib import Path

from .common import ROOT, dump, sha, load_cases, load_references

METHODS = ("R0", "R1", "QAMC")
PRIMARY = {"memsyco": "native_joint", "longmemeval": "accuracy", "locomo": "native_f1"}


def read(version):
    root = ROOT / "runs" / version
    cells = {}
    for p in (root / "cells").glob("*.json"):
        row = json.loads(p.read_text())
        assert (row["uid"], row["method"]) not in cells
        row["artifact"] = str(p.relative_to(ROOT))
        cells[row["uid"], row["method"]] = row
    ledger = []
    path = root / "api/ledger.sqlite"
    if path.exists():
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            ledger = [json.loads(r[0]) for r in db.execute("SELECT data FROM requests ORDER BY request_id")]
    return cells, ledger


def metric(cell, name):
    if not cell or cell.get("score_status") != "ok":
        return None
    value = cell.get("score", {}).get("metrics", {}).get(name)
    return float(value) if isinstance(value, (int, float, bool)) else None


def summary(cases, cells, method, field):
    rows = [cells.get((c["uid"], method)) for c in cases]
    values = [metric(c, field) for c in rows]
    values = [v for v in values if v is not None]
    return {"planned": len(cases), "present": sum(c is not None for c in rows),
            "terminal": sum(c is not None and (c["actor_status"] == "failed" or c["score_status"] != "not_dispatched") for c in rows),
            "generated": sum(c is not None and c["actor_status"] == "ok" for c in rows),
            "valid": len(values), "mean": sum(values) / len(values) if values else None,
            "sum": sum(values), "metric": field,
            "actor_failed": sum(c is not None and c["actor_status"] == "failed" for c in rows),
            "score_failed": sum(c is not None and c["score_status"] == "failed" for c in rows),
            "reused_actor": sum(bool(c and c.get("reused_actor")) for c in rows)}


def paired(cases, cells, left, right, field):
    rows = []
    for c in cases:
        a, b = metric(cells.get((c["uid"], left)), field), metric(cells.get((c["uid"], right)), field)
        if a is not None and b is not None:
            rows.append({"uid": c["uid"], "left": a, "right": b, "difference": b-a})
    return {"valid_pairs": len(rows), "missing_pairs": len(cases)-len(rows),
            "right_wins": sum(r["difference"] > 1e-8 for r in rows),
            "left_wins": sum(r["difference"] < -1e-8 for r in rows),
            "ties": sum(abs(r["difference"]) <= 1e-8 for r in rows),
            "mean_right_minus_left": sum(r["difference"] for r in rows)/len(rows) if rows else None,
            "rows": rows}


def pct(value):
    return "NA" if value is None else f"{100*value:.1f}%"


def report(version="v0"):
    cases = load_cases(version)
    refs = load_references(version)
    cells, ledger = read(version)
    groups, pairs, category = {}, {}, {}
    for benchmark, field in PRIMARY.items():
        part = [c for c in cases if c["benchmark"] == benchmark]
        groups[benchmark] = {m: summary(part, cells, m, field) for m in METHODS}
        if benchmark == "locomo":
            groups[benchmark + "_semantic_Qwen_variant"] = {m: summary(part, cells, m, "semantic_accuracy_Qwen_variant") for m in METHODS}
        pairs[benchmark] = {left + "_to_QAMC": paired(part, cells, left, "QAMC", field) for left in ("R0", "R1")}
        for cat in sorted({c["category"] for c in part}):
            subset = [c for c in part if c["category"] == cat]
            category[benchmark + "/" + cat] = {m: summary(subset, cells, m, field) for m in METHODS}
    terminal = sum(c["actor_status"] == "failed" or c["score_status"] != "not_dispatched" for c in cells.values())
    statuses = collections.Counter(r["status"] for r in ledger)
    known_usage = {k: sum((r.get("usage") or {}).get(k, 0) for r in ledger) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    imports = []
    import_path = ROOT / "runs" / version / "api/cache_imports.json"
    ledger_path = ROOT / "runs" / version / "api/ledger.sqlite"
    if ledger_path.exists():
        with sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True) as db:
            if db.execute("SELECT name FROM sqlite_master WHERE name='cache_imports'").fetchone():
                imports = [json.loads(r[0]) for r in db.execute("SELECT data FROM cache_imports ORDER BY key")]
    result = {"status": "complete" if terminal == 600 else "partial", "terminal_cells": terminal, "planned_cells": 600,
              "groups": groups, "pairs": pairs, "categories": category,
              "calls": {"real_requests": len(ledger), "statuses": dict(statuses), "known_usage": known_usage,
                        "usage_unknown": sum(r.get("usage") is None for r in ledger),
                        "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger),
                        "returned_models": dict(collections.Counter(r.get("returned_model") for r in ledger)),
                        "errors": dict(collections.Counter(r.get("error") for r in ledger if r.get("error")))}}
    result["calls"]["exact_prior_version_cached_imports"] = len(imports)
    result["calls"]["cache_is_new_independent_generation"] = False
    validity_path=ROOT/'reports/EVALUATION_VALIDITY.json'
    validity=json.loads(validity_path.read_text()).get('versions',{}).get(version,{}) if validity_path.exists() else {}
    result['evaluation_validity']=validity
    output = ROOT / "reports" / version
    output.mkdir(exist_ok=True)
    dump(output / "RESULTS.json", result)
    dump(ROOT / "runs" / version / "api/request_ledger.json", ledger)
    lines = [f"# QAMC {version}：200 题首轮", "", f"状态：**{result['status']}**；{terminal}/600 个方法轨迹进入终态。",
             "分数基于本轮冻结开发抽样。MemSyco 为原生联合通过率，LongMemEval 为官方 Prompt 的 Qwen Judge 变体，LoCoMo 为原生 F1（开放问题输入）。同模型 Judge 未经真人校准，不能据此声称 SOTA。", "",
             "| Benchmark / 指标 | 方法 | 计划 | 生成 | 有效评分 | 分数 | 生成失败 | 评分失败 | 历史 Actor 复用 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    if validity.get('longmemeval_native_identifier_leak'):
        lines[2:2]=['**输入隔离更正：本版本 LongMemEval 原生 answer_* 会话标识泄露支持会话位置，分数仅作带缺陷的探索记录，不能作为无泄漏验证或 SOTA 证据。见 INPUT_INTEGRITY_CORRECTION.md。**','']
    for name, methods in groups.items():
        for m, g in methods.items():
            lines.append(f"| {name} / {g['metric']} | {m} | {g['planned']} | {g['generated']} | {g['valid']} | {pct(g['mean'])} | {g['actor_failed']} | {g['score_failed']} | {g['reused_actor']} |")
    lines += ["", "## 同题有效配对", "", "| Benchmark | 比较 | 配对数 | QAMC 赢 | 基线赢 | 相同 | QAMC−基线 | 缺配对 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, comparisons in pairs.items():
        for compare, p in comparisons.items():
            lines.append(f"| {name} | {compare} | {p['valid_pairs']} | {p['right_wins']} | {p['left_wins']} | {p['ties']} | {pct(p['mean_right_minus_left'])} | {p['missing_pairs']} |")
    lines += ["", "## 调用与覆盖", "", json.dumps(result["calls"], ensure_ascii=False, indent=2), "",
              "失败不计正确/安全，不把未知 usage 填零；已知 completion tokens 可能包含推理。R0 Full History 不隐式截断；容量/传输故障单独保留。旧结果导入有独立来源，不计新请求。", "",
              "原始轨迹、Memory View、检索轮次与原始响应在 `runs/`；问题级表在同目录 `QUESTION_DETAILS.json`。"]
    (output / "RESULTS.md").write_text("\n".join(lines))
    lines = ["# 按原生类别分项", "", "| 类别 / 原生指标 | 方法 | 有效/计划 | 均值 |", "|---|---|---:|---:|"]
    for name, methods in category.items():
        for m, g in methods.items():
            lines.append(f"| {name} / {g['metric']} | {m} | {g['valid']}/{g['planned']} | {pct(g['mean'])} |")
    (output / "PER_CATEGORY.md").write_text("\n".join(lines))
    details, losses, gains = [], [], []
    for c in cases:
        item = {"question_id": c["uid"], "question": c["query"], "reference_answer": refs[c["uid"]].get("answer", refs[c["uid"]].get("evaluation", {}).get("reference_answer")),
                "category": c["category"], "methods": {m: cells.get((c["uid"], m)) for m in METHODS}}
        details.append(item)
        field = PRIMARY[c["benchmark"]]
        q = metric(cells.get((c["uid"], "QAMC")), field)
        for m in ("R0", "R1"):
            b = metric(cells.get((c["uid"], m)), field)
            if q is not None and b is not None and q != b:
                record = {"uid": c["uid"], "benchmark": c["benchmark"], "baseline": m, "baseline_score": b, "QAMC_score": q,
                          "attribution": "pending_source_and_answer_audit_not_model_self_explanation"}
                (losses if q < b else gains).append(record)
    dump(output / "QUESTION_DETAILS.json", details)
    dump(output / "WIN_LOSS.json", {"losses": losses, "gains": gains})
    lines = ["# 真实失败与收益入口", "", "以下仅是原生分数的配对胜负；原因需要查实际来源、检索、版本、编译、Actor 和 Judge。不能把模型自述当因果诊断。", "",
             f"QAMC 低于至少一个基线的配对记录 {len(losses)}，高于基线 {len(gains)}。", "", "| 方向 | ID | 对照 | 基线 | QAMC |", "|---|---|---|---:|---:|"]
    for direction, rows in (("loss", losses), ("gain", gains)):
        for row in rows:
            lines.append(f"| {direction} | {row['uid']} | {row['baseline']} | {row['baseline_score']:.3f} | {row['QAMC_score']:.3f} |")
    (output / "ERROR_ANALYSIS.md").write_text("\n".join(lines))
    (output / "DECISION.md").write_text(f"# 阶段判断\n\n当前状态：{result['status']}，终态 {terminal}/600。\n\n" +
        ("首轮尚未完成；目前不能判断方法有效性或启动正式全量评测。继续执行冻结的未完成轨迹，保留已完成项。\n" if terminal < 600 else
         "首轮已进入终态；需要完成逐项输入/调用审计、配对输赢的来源核验和有限修订决策，再判断是否扩大。本自动汇总不能替代最终机制分析。\n"))
    for name in ("RESULTS.md", "PER_CATEGORY.md", "ERROR_ANALYSIS.md", "DECISION.md"):
        (ROOT / "reports" / name).write_text((output / name).read_text())
    print(json.dumps({"status": result["status"], "terminal_cells": terminal, "calls": result["calls"]}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0")
    report(parser.parse_args().version)
