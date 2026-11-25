"""Build blinded behavior packets from fixed RPEval recovery answers."""
from hashlib import sha256

from recovery_challenge_inputs import prepare
from run_recovery_strength import OUT, PRIOR, read

RUBRIC = (
    "For each anonymous answer, quote its observable recommendation and assess whether "
    "it concretely uses the supplied preference. Separately determine whether it makes "
    "that preference a requirement, changes a shared choice without support, or omits a "
    "stated task requirement. Generic suggestions may independently fit the task. "
    "Return UNCERTAIN when the text is insufficient. Do not infer unseen history."
)


def build():
    cases = prepare()
    old = {row["uid"]: row for row in read(PRIOR / "RESULTS.json")["rows"]
           if row["method"] == "ordinary"}
    packets, keys = [], {}
    for i, row in enumerate(read(OUT / "RESULTS.json")["rows"], 1):
        uid = row["uid"]
        if not row["answer"] or row["selected"] != old[uid]["selected"]:
            raise ValueError("Incomplete fixed-answer comparison")
        case = cases[uid]
        arms = {"anchor": case["anchor"], "ordinary": old[uid]["answer"], "bounded": row["answer"]}
        order = sorted(arms, key=lambda arm: sha256(f"behavior-v1/{uid}/{arm}".encode()).digest())
        packet = f"case-{i}"
        key = dict(zip(("X", "Y", "Z"), order, strict=True))
        packets.append({"case": packet, "task": case["task"],
                        "preference": case["sources"][row["selected"]],
                        "answers": {alias: arms[arm] for alias, arm in key.items()}})
        keys[packet] = {"uid": uid, "order": key}
    return packets, keys


if __name__ == "__main__":
    packets, keys = build()
    assert len(packets) == len(keys) == 5
    print("5 anonymous cases, 15 fixed answers")
