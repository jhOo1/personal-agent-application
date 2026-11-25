"""Test fixed multilingual embeddings with the same source-disjoint veto replay."""
import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from replay_rpe_oneway_veto import ACTORS, CENSUS, ENDPOINTS, read, replay

SNAPSHOT = Path.home() / (
    ".cache/huggingface/hub/models--MoritzLaurer--mDeBERTa-v3-base-mnli-xnli/"
    "snapshots/8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"
)


def inventory():
    ends = {r["uid"]: r for r in read(ENDPOINTS)["rows"]}
    census = {r["uid"]: r for r in read(CENSUS)["RPEval"]["roots"]
              if r["route"] == "RPR_PAPER_FULL"}
    for a in read(ACTORS):
        uid = a["uid"]
        if a["method"] != "RPR_PAPER_FULL" or a["actor_status"] != "OK" or uid not in census:
            continue
        row = census[uid]
        packet = json.loads(a["actor_request"]["messages"][1]["content"])
        evidence = {p["memory_id"]: p["text"] for p in packet["source_evidence"]}
        if set(evidence) != {p["id"] for p in row["positions"]}:
            continue
        policy = {p["memory_id"]: p["policy"] for p in packet["preference_use_policy"]}
        yield row["group"], packet["query"], [
            (evidence[p["id"]], policy.get(p["id"], "unknown"), p["author_label"] != "A")
            for p in row["positions"]
        ], ends[uid]["scores"]


def embeddings(texts):
    tokenizer = AutoTokenizer.from_pretrained(SNAPSHOT, local_files_only=True)
    model = AutoModel.from_pretrained(SNAPSHOT, local_files_only=True).eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)
    output = {}
    with torch.inference_mode():
        for start in range(0, len(texts), 8):
            batch = texts[start:start + 8]
            inputs = tokenizer(batch, return_tensors="pt", padding=True,
                               truncation=True, max_length=256)
            inputs = {k: value.to(device) for k, value in inputs.items()}
            hidden = model(**inputs).last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1)
            means = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            vectors = torch.nn.functional.normalize(means, dim=1).cpu().numpy()
            output.update(zip(batch, vectors, strict=True))
    return output


def main():
    rows = list(inventory())
    texts = sorted({text for _, query, sources, _ in rows
                    for text in (query, *(item[0] for item in sources))})
    vectors = embeddings(texts)
    examples = []
    for group, query, sources, scores in rows:
        fs, labels = [], []
        q = vectors[query]
        for text, policy, label in sources:
            s = vectors[text]
            vector = np.concatenate((q, s, np.abs(q - s), q * s))
            feature = {f"emb{i}": float(value) for i, value in enumerate(vector)}
            feature.update({"policy_" + policy: 1, "cosine": float(q @ s)})
            fs.append(feature)
            labels.append(label)
        examples.append((group, labels, fs, scores))
    print(json.dumps({"encoded_texts": len(texts), **replay(examples)}, sort_keys=True))


if __name__ == "__main__":
    main()
