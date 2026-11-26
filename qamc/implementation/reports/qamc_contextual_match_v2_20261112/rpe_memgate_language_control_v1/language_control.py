"""Local source-representation diagnostic for the fixed published MemGate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from audit_memgate import load_gate
from qamc.common import sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORMAL = HERE.parent / "rpeval_formal_multi_coverage_v1"
RUN = ROOT / "runs" / HERE.parent.name
PILOT = RUN / HERE.name
REVISION = "cf109095479db38d6df799875e34039d4938aaa6"
MODEL_FILES = ("config.json", "generation_config.json", "pytorch_model.bin",
               "source.spm", "target.spm", "tokenizer_config.json", "vocab.json")
MAX_SOURCE = 384


def read(path):
    return json.loads(path.read_text())


def freeze(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError("Frozen diagnostic inputs changed")
        return
    with path.open("x") as out:
        json.dump(value, out, ensure_ascii=False, sort_keys=True)


def allocate(manifest, eligible):
    used, allocated = set(), []
    for track in ("explicit", "implicit"):
        options = [row for row in manifest if row["track"].split("/")[0] == track
                   and row["uid"] in eligible]
        count = 0
        for row in sorted(options, key=lambda r: sha("language-control-v1/" + r["uid"])):
            group = row["analysis_group_id"]
            if row["independent_confirmation"]:
                raise ValueError("Confirmation data is ineligible")
            if group in used:
                continue
            allocated.append(row["uid"])
            used.add(group)
            count += 1
            if count == 6:
                break
        if count != 6:
            raise ValueError("Did not recover the complete frozen allocation")
    return allocated


def pieces(tokenizer, text):
    """Find contiguous boundaries before the translator's fixed position cap."""
    pending = [text]
    result = []
    while pending:
        current = pending.pop()
        if len(tokenizer.encode(current, verbose=False)) <= MAX_SOURCE:
            result.append(current)
            continue
        middle = len(current) // 2
        boundaries = [
            x.end() for x in re.finditer(r"[。！？；\n]", current)
            if middle // 2 <= x.end() <= middle + middle // 2
        ]
        split = min(boundaries, key=lambda x: abs(x - middle)) if boundaries else middle
        if split <= 0 or split >= len(current):
            raise ValueError("Unable to split an overlength translation input")
        pending.extend([current[split:], current[:split]])
    if "".join(result) != text:
        raise ValueError("Translation input slicing changed source coverage")
    return result


def translate(tokenizer, model, texts):
    batches, ownership = [], []
    for i, text in enumerate(texts):
        parts = pieces(tokenizer, text)
        batches.extend(parts)
        ownership.extend([i] * len(parts))
    outputs = [[] for _ in texts]
    token_count = 0
    for start in range(0, len(batches), 8):
        batch = tokenizer(batches[start:start + 8], return_tensors="pt", padding=True,
                          truncation=False)
        token_count += int(batch["attention_mask"].sum())
        translated = model.generate(**batch, do_sample=False, num_beams=1, max_new_tokens=511)
        for uid, row in zip(ownership[start:start + 8], translated, strict=True):
            ids = row.tolist()
            output = tokenizer.decode(ids, skip_special_tokens=True).strip()
            if not output or tokenizer.eos_token_id not in ids[1:] or len(ids) >= 512:
                raise ValueError("Unusable translation output")
            outputs[uid].append(output)
    return [" ".join(parts) for parts in outputs], {"items": len(texts), "segments": len(batches),
                                                       "translator_input_tokens": token_count}


def top_k(scores, k):
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return sorted(order[:k])


def test_task(gate, tokenizer, translator, task, selected):
    ids = [item["memory_id"] for item in task["memories"]]
    zh = [task["query"], *(item["text"] for item in task["memories"])]
    en, accounting = translate(tokenizer, translator, zh)
    raw = {key: gate.score_candidates(texts[0], texts[1:])
           for key, texts in (("ZH", zh), ("EN", en))}
    kept = {key: [ids[i] for i, value in enumerate(values) if value > gate.threshold]
            for key, values in raw.items()}
    if kept["ZH"] != selected:
        raise ValueError("Existing original-language selection did not reproduce")
    metrics = {
        key: {
            "scores": values, "threshold": kept[key],
            "matched_zh_count": [ids[i] for i in top_k(values, len(kept["ZH"]))],
            "matched_en_count": [ids[i] for i in top_k(values, len(kept["EN"]))],
        }
        for key, values in raw.items()
    }
    return {"status": "OK", "modes": metrics, "translations": en, "accounting": accounting,
            "candidates": len(ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("embedding", type=Path)
    parser.add_argument("translator", type=Path)
    args = parser.parse_args()
    manifest = read(FORMAL / "MANIFEST_300.json")
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    plan = read(RUN / "rpe_memgate_matched_actor_v1/PREFLIGHT_PRIVATE.json")
    selection = plan["selection"]
    uids = allocate(manifest, selection)
    if len(manifest) != 300 or sha(selection) != plan["pins"]["selection_sha256"]:
        raise ValueError("Original source allocation changed")
    translator_assets = {name: sha((args.translator / name).read_bytes()) for name in MODEL_FILES}
    freeze(PILOT / "FROZEN.json", {
        "uids": uids, "source_inputs_sha256": sha({u: tasks[u] for u in uids}),
        "memgate_plan_sha256": plan["pins"]["selection_sha256"],
        "translation_assets": translator_assets, "translation_revision": REVISION,
        "code_sha256": sha(Path(__file__).read_bytes()), "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
    })
    torch.set_num_threads(2)
    gate, _ = load_gate(args.assets, args.embedding)
    tokenizer = AutoTokenizer.from_pretrained(args.translator, local_files_only=True)
    translator = AutoModelForSeq2SeqLM.from_pretrained(args.translator, local_files_only=True).eval()
    results = {}
    for number, uid in enumerate(uids, 1):
        target = PILOT / f"task_{number:02}.json"
        if target.exists():
            results[uid] = read(target)
            continue
        started = time.monotonic()
        with torch.inference_mode():
            try:
                result = test_task(gate, tokenizer, translator, tasks[uid], selection[uid]["kept"])
            except (RuntimeError, ValueError) as exc:
                result = {"status": "INVALID_TRANSLATION_OR_SCORE", "detail": str(exc)}
        freeze(target, result)
        results[uid] = result
        print(number, result["status"], round(time.monotonic() - started, 1), flush=True)
    freeze(PILOT / "RESULTS.json", results)
    print(json.dumps({"tasks": len(results), "statuses": Counter(x["status"] for x in results.values()),
                      "frozen_sha256": sha(read(PILOT / "FROZEN.json")), "new_cloud_requests": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
