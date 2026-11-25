"""Verified range-resume for a public immutable benchmark artifact (not model calls)."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .common import ROOT, dump


def main():
    url = "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json"
    size = 277383467
    expected = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
    partial = ROOT / "data/longmemeval_s_cleaned.json.part"
    prefix = partial.stat().st_size
    directory = ROOT / "data/download_ranges"
    directory.mkdir(exist_ok=True)
    step = 4 * 1024 * 1024
    spans = [(a, min(size - 1, a + step - 1)) for a in range(prefix, size, step)]

    def fetch(span):
        start, end = span
        path = directory / f"{start}-{end}.part"
        errors = []
        for attempt in range(4):
            have = path.stat().st_size if path.exists() else 0
            if have == end - start + 1:
                return {"start": start, "end": end, "errors": errors, "status": "downloaded"}
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={start + have}-{end}"})
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=60) as res:
                    content_range = res.headers.get("Content-Range", "")
                    if res.status != 206 or not content_range.startswith(f"bytes {start + have}-{end}/"):
                        raise ValueError("range_not_honored:" + str(res.status) + ":" + content_range)
                    with path.open("ab") as f:
                        while block := res.read(65536):
                            f.write(block)
                if path.stat().st_size != end - start + 1:
                    raise ValueError("incomplete_range")
                return {"start": start, "end": end, "errors": errors, "status": "downloaded"}
            except Exception as exc:
                errors.append({"attempt": attempt + 1, "error": type(exc).__name__ + ":" + str(exc)})
        return {"start": start, "end": end, "errors": errors, "status": "failed"}

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, span) for span in spans]):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
            dump(ROOT / "reports/DOWNLOAD_RECOVERY.json", {"prefix_bytes": prefix, "expected_size": size, "ranges": results})
    if any(r["status"] != "downloaded" for r in results):
        raise RuntimeError("incomplete public resource download; partials retained")
    with partial.open("ab") as out:
        for start, end in spans:
            with (directory / f"{start}-{end}.part").open("rb") as source:
                while block := source.read(1024 * 1024):
                    out.write(block)
    actual = hashlib.sha256(partial.read_bytes()).hexdigest()
    assert partial.stat().st_size == size and actual == expected, (partial.stat().st_size, actual)
    partial.rename(ROOT / "data/longmemeval_s_cleaned.json")
    dump(ROOT / "reports/DOWNLOAD_RECOVERY.json", {"prefix_bytes": prefix, "expected_size": size,
                                                  "ranges": results, "sha256_verified": actual})
    print("verified", actual, flush=True)


if __name__ == "__main__":
    main()
