"""Build a private behavior-review packet without method names or scorer results."""
import argparse
import json
from pathlib import Path
from runpy import run_path

from qamc.common import sha

HERE = Path(__file__).resolve().parent


def packet(pin, data, rows, waves):
    expected = {(uid, arm, wave) for uid in pin["tracks"]
                for arm in pin["arms"] for wave in waves}
    items, mapping, missing, seen = {}, {}, [], set()
    for row in rows:
        uid, arm, wave = (row[key] for key in ("uid", "arm", "wave"))
        coordinate = (uid, arm, wave)
        if coordinate not in expected or coordinate in seen:
            raise ValueError("Unexpected or duplicate behavior review position")
        seen.add(coordinate)
        answer = row["answer"]
        ref = {"uid": uid, "arm": arm, "wave": wave}
        if not answer:
            missing.append({**ref, "status": row["status"]})
            continue
        tag = sha(["equal-cap-safety-behavior", uid, answer])
        public = data[uid][0]
        items[tag] = {"review_id": tag, "query": public["query"],
                      "original_candidate_memory": public["memories"], "answer": answer}
        mapping.setdefault(tag, []).append(ref)
    if seen != expected:
        raise ValueError("Behavior review omitted frozen positions")
    return {"items": [items[k] for k in sorted(items)]}, {
        "mapping": mapping, "missing_answers": missing, "waves": list(waves)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waves", type=int, nargs="+", choices=(1, 2))
    args = parser.parse_args()
    waves = sorted(set(args.waves))
    runner = run_path(str(HERE / "run_safety.py"))
    run, read = runner["RUN"], runner["read"]
    pin, _, _, data, *_ = runner["prepare"]()
    if pin != read(run / "FROZEN.json"):
        raise ValueError("Audit inputs differ from experiment freeze")
    identity = read(run / "EXECUTION.json")
    checkpoints = [read(run / f"WAVE{wave}.json") for wave in waves]
    if any(cp["identity"] != identity for cp in checkpoints):
        raise ValueError("Audit checkpoint identity mismatch")
    rows = [row for cp in checkpoints for row in cp["rows"]]
    blind, manifest = packet(pin, data, rows, waves)
    suffix = "_".join(map(str, waves))
    freeze = runner["probe"].freeze
    freeze(run / f"BEHAVIOR_PACKET_PRIVATE_{suffix}.json", blind)
    freeze(run / f"BEHAVIOR_MAPPING_PRIVATE_{suffix}.json", manifest)
    print(json.dumps({"available_unique": len(blind["items"]),
                      "missing_positions": len(manifest["missing_answers"]),
                      "waves": waves}))


if __name__ == "__main__":
    main()
