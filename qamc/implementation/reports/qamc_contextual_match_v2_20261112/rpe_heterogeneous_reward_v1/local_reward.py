"""Run the pinned author reward model on blind packets, with per-task receipts."""
from argparse import ArgumentParser
import hashlib
import json
import os
from pathlib import Path
from time import monotonic

import torch
from safetensors import safe_open
from transformers import AutoConfig, AutoModel, AutoTokenizer, __version__ as transformers_version
from accelerate import init_empty_weights
from transformers.modeling_utils import no_init_weights

from selection import IDS, REVISION, conversation, reward_choice


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def load_model(snapshot):
    if snapshot.name != REVISION or transformers_version != "4.41.2":
        raise ValueError("Unexpected author snapshot or transformers version")
    config = AutoConfig.from_pretrained(snapshot, trust_remote_code=True, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, trust_remote_code=True, local_files_only=True,
                                              use_fast=False)
    with no_init_weights(), init_empty_weights(include_buffers=False):
        model = AutoModel.from_config(config, trust_remote_code=True, torch_dtype=torch.float16)
    shards = sorted(set(read(snapshot / "model.safetensors.index.json")["weight_map"].values()))
    state = {}
    for name in shards:
        with safe_open(snapshot / name, framework="pt", device="cpu") as weights:
            state.update({key: weights.get_tensor(key) for key in weights.keys()})
    model.load_state_dict(state, strict=True, assign=True)
    for buffer in model.buffers():
        if buffer.is_meta:
            raise ValueError("A reward model buffer was not materialized")
    return model.eval(), tokenizer


def score_packet(model, tokenizer, packet):
    inputs = [conversation(packet["context"], packet["candidates"][cid]) for cid in IDS]
    lengths = [len(tokenizer.encode(tokenizer.apply_chat_template(
        item, tokenize=False, add_generation_prompt=False), add_special_tokens=False)) + 1 for item in inputs]
    if max(lengths) > model.config.max_position_embeddings:
        raise ValueError("Context exceeds reward model limit")
    values = model.get_scores(tokenizer, inputs, use_cache=False)
    scores = dict(zip(IDS, values, strict=True))
    reward_choice(scores)
    return scores, lengths


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    packets = read(args.run / "BLIND_PACKETS.json")
    if len(packets) != 24 or any(set(p) != {"context", "candidates"} for p in packets.values()):
        raise ValueError("Unexpected frozen input shape")
    run = args.run / "reward_receipts"
    pin = {"snapshot": REVISION, "torch": torch.__version__, "transformers": transformers_version,
           "threads": args.threads, "device": "cpu", "dtype": "float16",
           "versions_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if (run / "RUNTIME.json").exists() and read(run / "RUNTIME.json") != pin:
        raise ValueError("Local runtime changed")
    save(run / "RUNTIME.json", pin)
    pending = [key for key in packets if not (run / f"{key}.json").exists()]
    if pending:
        print(f"Loading pinned reward weights for {len(pending)} tasks", flush=True)
        model, tokenizer = load_model(args.snapshot)
        print("Reward weights loaded", flush=True)
        for key in pending:
            start = monotonic()
            try:
                scores, lengths = score_packet(model, tokenizer, packets[key])
                result = {"status": "OK", "scores": scores, "input_tokens": lengths}
            except (ValueError, RuntimeError, TypeError, OverflowError) as error:
                result = {"status": "INVALID_REWARD", "error_type": type(error).__name__,
                          "error": str(error)}
            result["seconds"] = monotonic() - start
            save(run / f"{key}.json", result)
            print(f"{key[:8]} {result['status']} {result['seconds']:.1f}s", flush=True)
    save(args.run / "REWARDS.json", {key: read(run / f"{key}.json") for key in packets})


if __name__ == "__main__":
    main()
