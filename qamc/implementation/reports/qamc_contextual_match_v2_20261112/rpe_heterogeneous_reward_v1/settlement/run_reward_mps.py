"""Stream the pinned author's FP16 layers through Metal. No quantization."""
from argparse import ArgumentParser
import fcntl
import hashlib
from pathlib import Path
from time import monotonic

import accelerate
from accelerate.hooks import AlignDevicesHook, add_hook_to_module
import torch

from local_reward import load_model, read, save, score_packet, transformers_version
from selection import IDS, REVISION


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def activate_mps(model):
    if not torch.backends.mps.is_available():
        raise RuntimeError("Metal device is unavailable")
    for part in (model.model.tok_embeddings, model.model.norm, model.v_head):
        part.to("mps")
    for layer in model.model.layers:
        hook = AlignDevicesHook("mps", offload=True, weights_map=layer.state_dict(),
                                place_submodules=True)
        add_hook_to_module(layer, hook)
    if model.device.type != "mps":
        raise RuntimeError("The author tokenizer wrapper needs the Metal input device")
    return model


def score_all(root, snapshot):
    frozen = read(root / "FROZEN.json")
    from local_reward import __file__ as local_source
    from selection import __file__ as selection_source
    for source in map(Path, (local_source, selection_source)):
        if file_sha(source) != frozen["source_sha256"][source.name]:
            raise ValueError("Frozen reward source changed")
    packets_file = root / "BLIND_PACKETS.json"
    packets = read(packets_file)
    if len(packets) != 24 or any(set(p) != {"context", "candidates"} or set(p["candidates"]) != set(IDS)
                                for p in packets.values()):
        raise ValueError("Unexpected frozen input shape")
    here = Path(__file__).resolve()
    folder = root / "reward_mps_receipts"
    pin = {"revision": REVISION, "device": "mps_layer_offload", "dtype": "float16",
           "torch": torch.__version__, "transformers": transformers_version,
           "accelerate": accelerate.__version__, "backend_sha256": file_sha(here),
           "input_file_sha256": file_sha(packets_file)}
    if (folder / "RUNTIME.json").exists() and read(folder / "RUNTIME.json") != pin:
        raise ValueError("Local runtime changed")
    save(folder / "RUNTIME.json", pin)
    todo = [key for key in packets if not (folder / f"{key}.json").exists()]
    if todo:
        start = monotonic()
        model, tokenizer = load_model(snapshot)
        model = activate_mps(model)
        print(f"Loaded pinned weights after {monotonic() - start:.1f}s", flush=True)
        for key in todo:
            start = monotonic()
            try:
                scores, lengths = score_packet(model, tokenizer, packets[key])
                torch.mps.synchronize()
                row = {"status": "OK", "scores": scores, "input_tokens": lengths}
            except (ValueError, RuntimeError, TypeError, OverflowError) as error:
                row = {"status": "INVALID_REWARD", "error_type": type(error).__name__, "error": str(error)}
            row["seconds"] = monotonic() - start
            save(folder / f"{key}.json", row)
            print(f"{key[:8]} {row['status']} {row['seconds']:.1f}s", flush=True)
    output = {key: read(folder / f"{key}.json") for key in packets}
    result = root / "REWARDS.json"
    if result.exists() and read(result) != output:
        raise ValueError("Refusing to replace a settled reward result")
    save(result, output)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    with (args.run / "reward.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        score_all(args.run, args.snapshot)
