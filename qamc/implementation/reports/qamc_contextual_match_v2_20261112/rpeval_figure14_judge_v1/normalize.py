"""Read Figure 14's unquoted fraction notation without altering semantic grade fields."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from runpy import run_path

HERE = Path(__file__).resolve().parent
m = run_path(str(HERE / "evaluate.py"))
RUN, STAGE, archive, sha, fields, prepare = (m[k] for k in ("RUN", "STAGE", "archive", "sha", "fields", "prepare"))
FULL, ZERO, ROUTED = (m[k] for k in ("FULL", "ZERO", "ROUTED"))

FRACTION = re.compile(r'^([ \t]*"MICRO"[ \t]*:[ \t]*)(\d+[ \t]*/[ \t]*\d+)\.?([ \t]*,?[ \t]*)$', re.MULTILINE)


def quote_fraction(text):
    if not isinstance(text, str) or len(FRACTION.findall(text)) != 1:
        return text
    return FRACTION.sub(lambda match: match[1] + json.dumps(match[2]) + match[3], text, count=1)


def audit(asset):
    pin, cards, wires = prepare(asset)
    private = RUN / "private"
    if archive.read(private / "FROZEN.json") != pin:
        raise ValueError("Archived cohort changed")
    data = archive.read(private / "RESULTS.json")
    received = {}
    for p in (RUN / STAGE).glob("visible/*/record.json"):
        r = archive.read(p)
        key = r["unit"]["root_id"], r["unit"]["method"]
        digest = sha(archive.read(p.with_name("request.json")))
        if digest != sha(wires[key]) or digest != r["request_sha256"] or key in received:
            raise ValueError("Mismatched original Judge receipt")
        result = {"status": r["status"], "answer": None}
        answer = p.with_name("response.json")
        if answer.is_file():
            result["answer"] = archive.read(answer).get("answer")
        received[key] = result
    if set(received) != set(wires) or len(data["ledger"]) != len(received):
        raise ValueError("Incomplete receipt coverage")
    metrics = defaultdict(Counter)
    contracts, repairs, rows = Counter(), Counter(), []
    for uid, item in cards.items():
        adjusted, raw = {}, {}
        for method in (FULL, ZERO):
            r = received[uid, method]
            plain = fields(r, item["positions"])
            raw[method] = plain["status"]
            normalized = quote_fraction(r["answer"])
            grade = fields(dict(r, answer=normalized), item["positions"]) if plain["status"] == "INVALID_JSON" else plain
            if plain["status"] == "INVALID_JSON" and normalized != r["answer"]:
                repairs[grade["status"]] += 1
            adjusted[method] = grade
            contracts[grade["status"]] += 1
        adjusted[ROUTED] = adjusted[item["routed"]]
        valid = all(grade["status"] == "OK" for grade in adjusted.values()) and all(
            v and v.get("match") and v["match"]["positions"] == item["positions"] for v in item["adapted"].values())
        if valid:
            for method, new in adjusted.items():
                old = item["adapted"][method]["match"]
                metrics[method].update(tasks=1, positions=new["positions"], figure_match=new["matched"],
                                       figure_exact=int(new["macro"]), adapted_match=old["matched"],
                                       adapted_exact=int(old["matched"] == old["positions"]))
        rows.append({"case": "/".join(uid.split("/")[-2:]), "raw_status": raw, "fraction_normalized": adjusted,
                     "common_valid_with_original_rules": valid})
    return {"new_calls": 0, "contracts": contracts, "syntax_normalization": repairs,
            "paired": metrics, "cases": rows,
            "raw_contract": data["aggregate"]["contracts"], "raw_paired": data["aggregate"]["common"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("figure", type=Path)
    print(json.dumps(audit(parser.parse_args().figure.read_bytes()), sort_keys=True, indent=2))
