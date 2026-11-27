"""Compare the frozen feature trial with archived full pipelines by exact UID."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PEERS = ("RPR_PAPER_FULL", "DES2GEN_FULL", "MEMADAPTER_FULL", "GEPA_SELECTED_BOUNDS")
ARMS = ("IPE-C", "TASK_FEATURE", "MEMORY_FEATURE")
FIELDS = ("OPB", "UPB", "FM")


def load(path):
    return json.loads(path.read_text())


def summary(sets, cards, arms):
    common = [u for u in cards if all(valid(sets[u].get(m), cards[u]) for m in arms)]
    totals = []
    for method in arms:
        scores = [sets[u][method] for u in common]
        totals.append([sum(s["match"]["matched"] for s in scores),
                       *(sum(s[k] for s in scores) for k in FIELDS)])
    return len(common), sum(cards[u] for u in common), totals


def valid(score, n):
    if not score or not score.get("match"):
        return False
    match = score["match"]
    return (match["positions"] == n and 0 <= match["matched"] <= n and
            all(type(score.get(k)) is int for k in FIELDS))


def main():
    panel = load(HERE / "PANEL.json")["cases"]
    cards = {p["uid"]: p["base_grade"]["match"]["positions"] for p in panel}
    sets = {p["uid"]: {"IPE-C": p["base_grade"]} for p in panel}
    for row in load(HERE / "receipts/RESULTS.json")["rows"]:
        sets[row["uid"]][row["method"]] = row["score"]
    for row in load(HERE.parent / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
        uid, method = row["uid"], row["method"]
        if uid not in cards or method not in PEERS:
            continue
        if method in sets[uid]:
            raise ValueError("Duplicate archived row")
        if row.get("native_fields") and (row.get("score") or {}).get("judge_variant") != "author_rubric_GPT41_8192":
            raise ValueError("Incompatible archived Judge")
        sets[uid][method] = row.get("native_fields")
    for peer in PEERS:
        print(peer, *summary(sets, cards, (*ARMS, peer)))
    print("All methods", *summary(sets, cards, (*ARMS, *PEERS)))
    clean = {u:n for u,n in cards.items() if not u.endswith(("/implicit/070","/explicit/089"))}
    print("Documented sensitivity, all methods", *summary(sets, clean, (*ARMS, *PEERS)))


if __name__ == "__main__":
    main()
