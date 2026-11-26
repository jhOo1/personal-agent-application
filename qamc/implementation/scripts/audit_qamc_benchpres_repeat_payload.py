"""Measure frozen BenchPreS Actor payload composition without exporting any text."""

from collections import Counter, defaultdict
import json

import run_qamc_benchpres_three_draw as run
from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge


def audit():
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    plan_hash = sha(plan)
    if plan_hash != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")

    bridge = PersistAuthorBridge(run.ROOT / "literature/qamc_pa_v1/PersistBench")
    template = bridge.blobs["GEPA"].decode().replace("{model_name}", "qwen3.8-flash")
    before, after = template.split("{memories}")
    requests = defaultdict(dict)
    for job in plan["generation"].values():
        unit = job["unit"]
        key = unit["root_id"], unit["method"]
        requests[key][unit["replicate"]] = job["request"]
    for draws in requests.values():
        if set(draws) != set(run.REPEATS) or len({sha(request) for request in draws.values()}) != 1:
            raise ValueError("Unexpected Actor payload changes between draws")

    counts = Counter()
    for root, method in requests:
        if method != run.GATE:
            continue
        gate = requests[root, method][0]["messages"]
        paper = requests[root, run.PAPER][0]["messages"]
        if [m["role"] for m in gate] != ["system", "user"] or [m["role"] for m in paper] != ["user"]:
            raise ValueError("Unexpected role layout")
        system = gate[0]["content"]
        if not system.startswith(before) or not system.endswith(after):
            raise ValueError("Gate system prompt differs from pinned GEPA scaffolding")
        memory_xml = system[len(before):len(system) - len(after)]
        if not memory_xml.startswith("<memories>\n") or not memory_xml.endswith("\n</memories>"):
            raise ValueError("Unexpected GEPA memory rendering")
        for key, text in (
            ("gate_static_system", before + after), ("gate_memory_xml", memory_xml),
            ("gate_user", gate[1]["content"]), ("selectivity_user", paper[0]["content"]),
        ):
            counts[key] += len(text.encode("utf-8"))
        for key, value in json.loads(gate[1]["content"]).items():
            counts["gate_json_value_" + key] += len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        counts["paired_roots"] += 1
    return {"plan_sha256": plan_hash, "author_template_commit": bridge.manifest()["author_commit"],
            "units": "utf8_message_content_bytes", "totals": counts}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
