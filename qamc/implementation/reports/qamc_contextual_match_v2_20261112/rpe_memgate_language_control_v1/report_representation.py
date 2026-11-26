"""Compare token coverage and unmasked cosine after selection has settled."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
import torch
from transformers import AutoTokenizer

from qamc.common import sha
from qamc.pa.core import digest

from report_language import FORMAL, ROOT, RUN, read, separation

ENCODER_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def coverage(tokenizer, texts, limit):
    factored = tokenizer(texts, truncation=False, add_special_tokens=False, verbose=False)["input_ids"]
    return Counter(texts=len(texts),
                   visible_tokens=sum(len(row[:limit]) for row in factored),
                   unknown_visible_tokens=sum(row[:limit].count(tokenizer.unk_token_id) for row in factored),
                   truncated_texts=sum(len(row) > limit for row in factored))


def report(run, embedding):
    outputs = read(run / "RESULTS.json")
    plan = read(run / "FROZEN.json")
    if outputs.keys() != set(plan["uids"]):
        raise ValueError("Expected a completed frozen panel")
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    manifest = {r["uid"]: r for r in read(FORMAL / "MANIFEST_300.json")}
    if any(manifest[u]["independent_confirmation"] for u in outputs):
        raise ValueError("Unexpected confirmation task")
    pin = read(run.parent / "rpe_memgate_matched_actor_v1/PREFLIGHT_PRIVATE.json")["pins"]
    weights = sha((embedding / "model.safetensors").read_bytes())
    if embedding.name != ENCODER_REVISION or weights != pin["released_artifacts"]["model.safetensors"]:
        raise ValueError("Expected the original encoder")
    torch.set_num_threads(2)
    model = SentenceTransformer(str(embedding), device="cpu", local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(embedding, local_files_only=True)
    limit = model.max_seq_length - tokenizer.num_special_tokens_to_add(pair=False)
    tok, scores = defaultdict(Counter), defaultdict(list)
    with torch.inference_mode():
        for uid, outcome in outputs.items():
            if outcome["status"] != "OK":
                continue
            task = tasks[uid]
            ref = read(ROOT / manifest[uid]["evaluation_path"])
            if digest(ref) != manifest[uid]["evaluation_hash"]:
                raise ValueError("The historical evaluation identity changed")
            labels = ref["intent_type"]
            originals = [task["query"], *(m["text"] for m in task["memories"])]
            for name, inputs in (("ZH", originals), ("EN", outcome["translations"])):
                if len(inputs) != len(labels) + 1:
                    raise ValueError("No one-to-one translation mapping")
                tok[name + "/query"].update(coverage(tokenizer, inputs[:1], limit))
                tok[name + "/memory"].update(coverage(tokenizer, inputs[1:], limit))
                if set(labels) == {"A"} or "A" not in labels:
                    continue
                embeddings = model.encode(inputs, normalize_embeddings=True, convert_to_tensor=True,
                                          show_progress_bar=False)
                cosine = (embeddings[1:] @ embeddings[0]).tolist()
                gated = outcome["modes"][name]["scores"]
                for label, positive in (("BC_vs_A", "BC"), ("B_vs_A", "B"), ("C_vs_A", "C")):
                    for mode, items in (("cosine", cosine), ("gated", gated)):
                        auc = separation(items, labels, positive)
                        if auc is not None:
                            scores[label, name, mode].append((manifest[uid]["analysis_group_id"], auc))
    return {
        "input_limit_including_special_tokens": model.max_seq_length,
        "encoder_weights_sha256": weights,
        "counted_rows": sum(r["status"] == "OK" for r in outputs.values()),
        "coverage": tok,
        "macro_within_task_auc": {
            "/".join(key): {"tasks": len(value), "source_groups": len({g for g, _ in value}),
                            "macro": round(sum(s for _, s in value) / len(value), 6)}
            for key, value in scores.items()
        },
        "new_cloud_requests": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("embedding", type=Path)
    parser.add_argument("--wide", action="store_true")
    args = parser.parse_args()
    folder = RUN.with_name("rpe_memgate_language_wide_v1") if args.wide else RUN
    print(json.dumps(report(folder, args.embedding), indent=2, sort_keys=True))
