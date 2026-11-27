"""Inventory unauthenticated model listings. Never send benchmark content."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODELS = {
    "DeepSeek-R1": ("deepseek/deepseek-r1", "deepseek-ai/DeepSeek-R1"),
    "Kimi-K2-Thinking": ("moonshotai/kimi-k2-thinking", "moonshotai/Kimi-K2-Thinking"),
}


def parse_listing(host, model, payload):
    if host == "openrouter":
        listing = payload["data"]
        if listing["id"] != model or not isinstance(listing["endpoints"], list):
            raise ValueError("Unexpected OpenRouter model or endpoint schema")
        return {
            "model_id": model,
            "endpoint_count": len(listing["endpoints"]),
            "providers": [r.get("provider_name") for r in listing["endpoints"]],
        }
    if payload["id"] != model or not isinstance(payload["inferenceProviderMapping"], dict):
        raise ValueError("Unexpected Hub model or provider schema")
    return {
        "model_id": model,
        "revision": payload["sha"],
        "inference_providers": sorted(payload["inferenceProviderMapping"]),
    }


def get_listing(job):
    name, host, model = job
    if host == "openrouter":
        url = f"https://openrouter.ai/api/v1/models/{model}/endpoints"
    else:
        url = f"https://huggingface.co/api/models/{model}?expand=inferenceProviderMapping&expand=sha"
    result = {"name": name, "registry": host, "url": url}
    try:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "qamc-public-route-audit/1"})
        with urlopen(req, timeout=18) as stream:
            result["http_status"] = stream.status
            result.update(parse_listing(host, model, json.load(stream)))
    except HTTPError as failure:
        result.update(http_status=failure.code, observation="http_error")
    except (URLError, TimeoutError, ValueError, TypeError, KeyError) as failure:
        result.update(observation="unavailable_or_unexpected_listing", error_type=type(failure).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    jobs = [(name, host, model) for name, ids in MODELS.items()
            for host, model in zip(("openrouter", "huggingface"), ids)]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        listing = list(pool.map(get_listing, jobs))
    output = {"observed_utc": datetime.now(timezone.utc).isoformat(), "public_listings": listing,
              "authenticated_requests": 0, "inference_requests": 0}
    rendered = json.dumps(output, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x") as stream:
            stream.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
