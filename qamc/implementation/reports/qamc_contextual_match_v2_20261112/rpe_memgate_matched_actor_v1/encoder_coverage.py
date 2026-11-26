"""Audit loss of input tokens in the pinned released selector's tokenizer."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORMAL = HERE.parent / "rpeval_formal_multi_coverage_v1"
RUN = ROOT / "runs" / HERE.parent.name / HERE.name
HAN = re.compile(r"[\u3400-\u9fff]")


def read(path):
    return json.loads(path.read_text())


def audit(tokenizer, texts, limit):
    raw = tokenizer(texts, add_special_tokens=False, truncation=False, verbose=False)["input_ids"]
    available = limit - tokenizer.num_special_tokens_to_add(pair=False)
    counts = Counter()
    for text, ids in zip(texts, raw, strict=True):
        sent = ids[:available]
        unknown = sent.count(tokenizer.unk_token_id)
        han = len(HAN.findall(text))
        letters = sum(ch.isalpha() for ch in text)
        counts.update(texts=1, mostly_han=2 * han > letters, raw_tokens=len(ids),
                      visible_tokens=len(sent), unknown_visible_tokens=unknown,
                      texts_truncated=len(ids) > available, texts_any_unknown=unknown > 0,
                      majority_unknown_visible=2 * unknown > len(sent))
    return counts


def main(embedding):
    frozen = read(RUN / "PREFLIGHT_PRIVATE.json")
    expected = read(HERE / "PREFLIGHT.json")["pins"]
    if frozen["pins"] != expected or embedding.name != "1110a243fdf4706b3f48f1d95db1a4f5529b4d41":
        raise ValueError("Expected the frozen selector and matching tokenizer revision")
    tokenizer = AutoTokenizer.from_pretrained(embedding, local_files_only=True)
    limit = read(embedding / "sentence_bert_config.json")["max_seq_length"]
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    queries, retained, omitted = [], [], []
    for uid, selection in frozen["selection"].items():
        target = tasks[uid]
        queries.append(target["query"])
        for item in target["memories"]:
            (retained if item["memory_id"] in selection["kept"] else omitted).append(item["text"])
    out = {key: audit(tokenizer, value, limit) for key, value in
           (("queries", queries), ("retained_sources", retained), ("omitted_sources", omitted))}
    return {"model_max_input_tokens": limit, "tokenizer_revision": embedding.name,
            "vocab_sha256": hashlib.sha256((embedding / "vocab.txt").read_bytes()).hexdigest(),
            "coverage": out}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("embedding", type=Path)
    print(json.dumps(main(cli.parse_args().embedding), indent=2, sort_keys=True))
