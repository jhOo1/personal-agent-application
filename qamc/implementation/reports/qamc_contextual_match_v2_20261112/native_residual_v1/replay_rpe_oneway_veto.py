"""Source-disjoint out-of-fold replay of a supervised one-way RPEval veto."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import LogisticRegression

BASE = Path(__file__).resolve().parent.parent
CENSUS = BASE / "strong_actor_boundary_audit_v1" / "CENSUS.json"
ENDPOINTS = BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json"
ACTORS = BASE / "rpeval_formal_multi_coverage_v1" / "RESULT_ROWS.json"


def read(path):
    return json.loads(path.read_text())


def fold(group):
    return int(hashlib.sha256(group.encode()).hexdigest(), 16) % 4


def grams(text):
    return {text[i:i+2] for i in range(len(text) - 1)}


def signals(packet, text, action):
    query, source = grams(packet["query"]), grams(text)
    overlap = query & source
    yield "policy_" + action, 1
    yield "query_overlap", len(overlap) / max(len(query), 1)
    yield "memory_overlap", len(overlap) / max(len(source), 1)
    for prefix, values in (("q", query), ("m", source), ("hit", overlap)):
        scale = max(len(values), 1) ** -0.5
        for token in sorted(values):
            yield prefix + token, scale


def examples():
    endpoints = {row["uid"]: row for row in read(ENDPOINTS)["rows"]}
    eligible = {
        row["uid"]: row for row in read(CENSUS)["RPEval"]["roots"]
        if row["route"] == "RPR_PAPER_FULL"
    }
    rows = []
    for actor in read(ACTORS):
        uid = actor["uid"]
        if uid not in eligible or actor["method"] != "RPR_PAPER_FULL" or actor["actor_status"] != "OK":
            continue
        item = eligible[uid]
        packet = json.loads(actor["actor_request"]["messages"][1]["content"])
        evidence = {r["memory_id"]: r["text"] for r in packet["source_evidence"]}
        actions = {r["memory_id"]: r["policy"] for r in packet["preference_use_policy"]}
        if set(evidence) != {p["id"] for p in item["positions"]}:
            continue
        labels, features = [], []
        for position in item["positions"]:
            sid = position["id"]
            labels.append(position["author_label"] != "A")
            features.append(dict(signals(packet, evidence[sid], actions.get(sid, "unknown"))))
        rows.append((item["group"], labels, features, endpoints[uid]["scores"]))
    return rows


def replay(rows):
    result = Counter()
    hasher = FeatureHasher(n_features=2**16, input_type="dict")
    for test in range(4):
        calibration = (test + 1) % 4
        train = [row for row in rows if fold(row[0]) not in {test, calibration}]
        model = LogisticRegression(C=1, max_iter=1000, solver="liblinear")
        model.fit(hasher.transform([p for _, _, fs, _ in train for p in fs]),
                  [label for _, labels, _, _ in train for label in labels])

        def risk(row):
            return float(np.max(model.predict_proba(hasher.transform(row[2]))[:, 1]))

        calib_positive = [risk(row) for row in rows if fold(row[0]) == calibration and any(row[1])]
        boundary = min(calib_positive, default=0.0)
        for row in rows:
            if fold(row[0]) != test:
                continue
            applied = risk(row) < boundary
            result.update(history_roots=1, veto=applied, legal_veto=applied and any(row[1]),
                          all_a_veto=applied and not any(row[1]))
            scores = row[3]
            before, after = [(scores.get(key, {}).get("grade") or {}).get("match")
                             for key in ("IPE_C", "TASK_ONLY")]
            if not before or not after:
                result["missing_pair"] += 1
                continue
            result.update(common=1, positions=before["positions"], baseline=before["matched"],
                          veto_match=after["matched"] if applied else before["matched"])
    return dict(result)


if __name__ == "__main__":
    print(json.dumps(replay(examples()), sort_keys=True))
