"""Score unchanged RPEval endpoints using the paper's Figure 14 prompt text."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
old = run_path(str(BASE / "rpeval_released_judge_bridge_v1" / "score_release.py"))
previous = run_path(str(BASE / "strong_wire_pruning_replay_v1" / "run.py"))
archive, engine, probe, sha = (previous[k] for k in ("archive", "engine", "probe", "sha"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
APPENDIX_SHA256 = "0730f4b4677920abbff2cc184e56e4eddb6a5c036e6b575e00eb1bb6e3d72f1c"
STAGE = "Figure14Judge"
METRICS = ("FB", "UPB", "RII", "LF", "VG", "Judge")
FULL, ZERO, ROUTED = (old[k] for k in ("FULL", "ZERO", "ROUTED"))


def template(figure):
    if sha256(figure).hexdigest() != APPENDIX_SHA256:
        raise ValueError("Unrecognized arXiv source asset")
    raw = figure.decode("utf-8")
    begin = raw.index("    You are an evaluation assistant.")
    end = raw.index(r"    \end{verbatim}", begin)
    text = raw[begin:end]
    text = re.sub(r"\\text(?:bf|tt)\{([^{}]+)\}", r"\1", text)
    text = text.replace(r"\textless ", "<").replace(r"\textgreater", ">")
    text = text.replace(r"\begin{verbatim}", "").replace(r"\hrule", "").replace(r"\bigskip", "")
    text = text.replace(r"\\", "")
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def plain_prompt(src, ref, answer):
    fields = {"Preferences": ref["persona"], "Question": ref["question"],
              "Response": answer, "Intent": ref["intent_type"]}
    def fill(match):
        key = match[1]
        return "<" + key + ">\n" + str(fields[key]) + "\n</" + key + ">"
    if any(src.count(f"<{k}>") != (2 if k == "Intent" else 1) for k in fields):
        raise ValueError("Figure placeholders drift")
    return re.sub(r"<(Preferences|Question|Response|Intent)>", fill, src)


def prepare(figure):
    text = template(figure)
    source_plan = old["prepare"]()
    v41 = old["v41"]
    author = old["ext"].read(v41.formal.OUT / "PLAN.json")
    cases = v41.author_cases(author)
    bank = {r["uid"]: r for r in old["ext"].read(v41.formal.OUT / "RESULT_ROWS.json") if r["method"] == FULL}
    endpoints = old["ext"].index(old["ext"].read(old["ENDPOINTS"] / "RESULTS.json")["rows"])
    wires, saved = {}, {}
    for row in source_plan["cards"]:
        uid = row["uid"]
        ref = archive.read(v41.formal.ROOT / cases[uid]["evaluation_path"])
        end = endpoints[uid]
        count = len(end["labels"])
        if ref["intent_type"] != end["labels"] or count < 2:
            raise ValueError("Archived label mismatch")
        raw_answers = {FULL: bank[uid]["answer"], ZERO: end["no_history_state"]["answer"]}
        for method, answer in raw_answers.items():
            if sha(answer) != row["endpoint_hashes"][method]:
                raise ValueError("Fixed endpoint changed")
            old_wire = row["requests"][method]
            wire = {**old_wire, "messages": [old_wire["messages"][0],
                      {"role": "user", "content": plain_prompt(text, ref, answer)}]}
            wires[uid, method] = wire
        saved[uid] = {"positions": count, "stratum": row["stratum"], "routed": row["routed"],
                      "adapted": row["adapted"]}
    pin = {"source_asset": APPENDIX_SHA256, "source_plan": sha(source_plan),
           "requests": sha(list(wires.values())), "cap": len(wires), "code": sha(Path(__file__).read_bytes()),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()), "reference": probe.read_reference()[1]}
    return pin, saved, wires


def parse_micro(value, positions):
    if isinstance(value, str) and (match := re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*\.?\s*", value)):
        n, d = map(int, match.groups())
        return n if d == positions and 0 <= n <= d else None
    if type(value) not in (float, int) and not isinstance(value, str):
        return None
    try:
        score = Fraction(str(value).strip()) * positions
    except (ValueError, ZeroDivisionError):
        return None
    return int(score) if score.denominator == 1 and 0 <= score <= positions else None


def fields(receipt, positions):
    if receipt["status"] != "OK":
        return {"status": receipt["status"], "matched": None}
    try:
        parsed = old["parse_object"](receipt["answer"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"status": "INVALID_JSON", "matched": None}
    n = parse_micro(parsed.get("MICRO"), positions)
    macro = parsed.get("MACRO")
    if n is None:
        state = "INVALID_MICRO"
    elif type(macro) is not bool:
        state = "INVALID_MACRO"
    elif macro != (n == positions):
        state = "INCONSISTENT_MACRO"
    else:
        state = "OK"
    severity = {k: parsed[k] for k in METRICS if type(parsed.get(k)) in (int, float) and 0 <= parsed[k] <= 5}
    return {"status": state, "matched": n, "macro": macro if type(macro) is bool else None,
            "positions": positions, "severity": severity}


def run(pin, rows, wires, live):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {STAGE: pin["cap"]}
    ident = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        result = engine.stage(STAGE, wires, ident, live, ledger)
        summary, states = defaultdict(Counter), Counter()
        per_case = []
        for uid, row in rows.items():
            grades = {m: fields(result[uid, m], row["positions"]) for m in (FULL, ZERO)}
            grades[ROUTED] = grades[row["routed"]]
            states.update(grades[m]["status"] for m in (FULL, ZERO))
            valid = all(g["status"] == "OK" for g in grades.values()) and all(
                s and s.get("match") and s["match"]["positions"] == row["positions"] for s in row["adapted"].values())
            for method in (FULL, ZERO, ROUTED):
                if valid:
                    g, a = grades[method], row["adapted"][method]
                    summary[method].update(tasks=1, positions=row["positions"], figure_match=g["matched"],
                                           figure_exact=int(g["macro"]), adapted_match=a["match"]["matched"],
                                           adapted_exact=int(a["match"]["matched"] == row["positions"]))
            per_case.append({"case": "/".join(uid.split("/")[-2:]), "stratum": row["stratum"], "grades": grades,
                             "adapted": row["adapted"], "common_valid": valid})
        aggregate = {"assigned": len(rows), "common": summary, "contracts": states,
                     "physical": len(ledger), "transport": Counter(r["status"] for r in ledger),
                     "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                     "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                     "retries": sum(r["automatic_retries"] for r in ledger), "cases": per_case}
        path = PRIVATE / "RESULTS.json"
        raw = {"aggregate": aggregate, "ledger": ledger}
        if live:
            probe.freeze(path, raw)
        elif raw != archive.read(path):
            raise ValueError("Figure 14 settlement differs on replay")
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "replay"))
    parser.add_argument("figure", type=Path)
    args = parser.parse_args()
    data = prepare(args.figure.read_bytes())
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = PRIVATE / "FROZEN.json"
    if args.action == "freeze":
        probe.freeze(path, data[0])
        print({"assigned": len(data[1]), "cap": data[0]["cap"]})
    elif archive.read(path) != data[0]:
        raise ValueError("Frozen Figure 14 comparison drift")
    else:
        run(*data, live=args.action == "run")
