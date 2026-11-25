from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if (ROOT / "data/tokenizer/9b5ad71b2ce5302211f9c61530b329a4922fc6a4").exists():
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / "data/tokenizer"))


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: Any) -> str:
    return hashlib.sha256((value if isinstance(value, bytes) else
                           value.encode() if isinstance(value, str) else canonical(value).encode())).hexdigest()


def dump(path: Path, value: Any) -> None:
    from .transport_helpers import atomic_json
    atomic_json(path, value)


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower())


def parse_object(text: str) -> dict:
    decoder = json.JSONDecoder()
    stripped = text.strip()
    if stripped.startswith("```blob"):
        raise ValueError("unexpected fenced object")
    for pos, char in enumerate(stripped):
        if char == "{":
            try:
                obj, _ = decoder.raw_decode(stripped[pos:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object")


def token_estimate(text: str) -> int:
    """A recorded budget estimator, never a certification of the Qwen tokenizer."""
    import tiktoken
    return len(tiktoken.get_encoding("cl100k_base").encode(text))


def dataset_files(version: str):
    """Read the version's immutable dataset paths; legacy runs keep original data."""
    path=ROOT/'configs'/f'experiment_{version}.json'
    pending=ROOT/'configs'/f'dataset_{version}.json'
    settings=json.loads(path.read_text()).get('dataset',{}) if path.exists() else (json.loads(pending.read_text()) if pending.exists() else {})
    return (ROOT/settings.get('cases_path','data/cases.json'),
            ROOT/settings.get('references_path','data/evaluation_references.json'))


def load_cases(version: str):
    return json.loads(dataset_files(version)[0].read_text())


def load_references(version: str):
    return json.loads(dataset_files(version)[1].read_text())
