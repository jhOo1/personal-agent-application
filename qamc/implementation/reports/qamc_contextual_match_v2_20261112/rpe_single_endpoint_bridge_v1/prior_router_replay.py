"""Transfer the six existing estimator rules without changing either single-preference endpoint."""
from collections import Counter
import json

from qamc.common import sha

from replay import RULES, predict
from run_bridge import EXTERNAL, FULL, OLD, RUN, ZERO, frozen_manifest


def read(path):
    return json.loads(path.read_text())


def routes_for(row, archived):
    if len(archived["aggregation"]) != 1 or any(
        archived["reader_statuses"].get(role) != "OK" for role in ("RPR_MLE", "RPR_IPE")
    ):
        raise ValueError("Missing original preference estimator result")
    item = archived["aggregation"][0]
    request = archived["actor_request"]
    packet = json.loads(request["messages"][1]["content"])
    expected_policy = [{"memory_id": "M0", "policy": item["policy"]}]
    if (
        item["memory_id"] != "M0"
        or sorted(item["mle_order"]) != list("ABC")
        or sorted(item["ipe_order"]) != list("ABC")
        or item["policy"] not in {"A", "B", "C"}
        or packet["preference_use_policy"] != expected_policy
        or sha(request) != archived["actor_request_sha256"]
    ):
        raise ValueError("Frozen ranking or Actor policy changed")
    routes = predict(item["mle_order"][0], item["ipe_order"][0], item["policy"])
    if (FULL if routes["IPE_C"] else ZERO) != row["route"]:
        raise ValueError("Fixed IPE-C route changed")
    return routes


def summarize(rows, archived):
    tables = {}
    for label in ("ALL", "A", "B", "C"):
        table = {rule: Counter() for rule in RULES}
        oracle = Counter()
        for row in rows:
            if label != "ALL" and row["label"] != label:
                continue
            routes = routes_for(row, archived[row["uid"]])
            scores = row["scores"]
            ipe = scores["IPE_C"]
            if ipe != scores[row["route"]]:
                raise ValueError("IPE-C does not equal its selected endpoint")
            pair = [scores[FULL], scores[ZERO]]
            common = all(score is not None for score in pair)
            if common:
                ceiling = max(score["matched"] for score in pair)
                oracle.update(positions=1, match=ceiling, ipe=ipe["matched"], **{
                    method: scores[method]["matched"] for method in EXTERNAL
                })
            for rule, enabled in routes.items():
                cell = table[rule]
                cell.update(assigned=1, history=enabled, changed=enabled != routes["IPE_C"])
                selected = scores[FULL if enabled else ZERO]
                if selected is not None:
                    cell.update(available=1, available_match=selected["matched"])
                if common:
                    delta = selected["matched"] - ipe["matched"]
                    cell.update(
                        common=1, match=selected["matched"],
                        wins=delta > 0, losses=delta < 0, ties=delta == 0,
                        **{k: selected["severity"][k] for k in ("OPB", "UPB", "FM")},
                    )
        tables[label] = {"rules": table, "oracle_on_common": oracle}
    return tables


def main():
    manifest = frozen_manifest()
    rows = read(RUN / "RESULTS.json")["rows"]
    archived = {
        row["uid"]: row for row in read(OLD / "SAVED_OPPONENT_ROWS.json")
        if row["method"] == FULL and row["uid"] in manifest
    }
    if (
        len(rows) != len(manifest)
        or set(manifest) != {row["uid"] for row in rows}
        or set(manifest) != set(archived)
    ):
        raise ValueError("Single-preference roster changed")
    print(json.dumps(summarize(rows, archived), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
