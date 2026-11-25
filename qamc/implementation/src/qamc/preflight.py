"""Freeze the 200-case protocol and verify it before any model dispatch."""
from __future__ import annotations

import collections
import argparse
import json
import statistics
from pathlib import Path

from .common import ROOT, dump, sha, token_estimate
from .data import MEMSYCO_TASKS


def assert_frozen(version="v0"):
    frozen = json.loads((ROOT / "configs" / f"source_freeze_{version}.json").read_text())
    amendments_path = ROOT / "configs/engineering_amendments.json"
    expected = dict(frozen["file_sha256"])
    if amendments_path.exists():
        for change in json.loads(amendments_path.read_text()):
            if change["version"] == version:
                assert expected[change["path"]] == change["before"]
                expected[change["path"]] = change["after"]
    for rel, digest in expected.items():
        assert sha((ROOT / rel).read_bytes()) == digest, "frozen file changed: " + rel
    assert sha((ROOT / frozen.get("cases_path", "data/cases.json")).read_bytes()) == frozen["cases_sha256"]
    assert sha((ROOT / frozen.get("references_path", "data/evaluation_references.json")).read_bytes()) == frozen["evaluation_references_sha256"]
    return frozen


def freeze(version="v0"):
    from .experiment import import_scope_r0
    from .memory_writer import chunks
    config_path = ROOT / "configs" / f"experiment_{version}.json"
    if config_path.exists():
        raise ValueError("configuration already frozen; use explicit revision/amendment")
    settings_path=ROOT/'configs'/f'dataset_{version}.json'
    dataset=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    cases_path=ROOT/dataset.get('cases_path','data/cases.json')
    references_path=ROOT/dataset.get('references_path','data/evaluation_references.json')
    manifest_path=ROOT/dataset.get('manifest_path','DATA_MANIFEST.json')
    cases=json.loads(cases_path.read_text())
    manifest=json.loads(manifest_path.read_text())
    if dataset.get('source_id_policy')!='chronological_opaque_v1':
        raise ValueError('New freezes require an explicit opaque-source dataset after the identifier-integrity correction')
    from .opaque_ids import validate_opaque_histories
    validate_opaque_histories(cases)
    selected={s['uid']:s for s in manifest['selected']}
    assert all(sha(c['history'])==selected[c['uid']]['history_sha256'] for c in cases)
    assert len(cases) == 200
    for source in manifest["sources"].values():
        assert sha((ROOT / source["path"]).read_bytes()) == source["sha256"]
    smoke = [next(c["uid"] for c in cases if c["benchmark"] == "memsyco" and c["category"] == task) for task in MEMSYCO_TASKS]
    lme = sorted([s for s in manifest["selected"] if s["benchmark"] == "longmemeval"], key=lambda c: c["history_tokens_cl100k_estimate"])
    smoke.append(lme[len(lme) // 2]["uid"])
    smoke.append(next(c["uid"] for c in cases if c["benchmark"] == "locomo"))
    if dataset.get('smoke_ids'):smoke=dataset['smoke_ids']
    unique = {c["namespace"]: c for c in cases}
    writer_chunks = sum(sum(1 for _ in chunks(c["history"])) for c in unique.values())
    imported = [c["uid"] for c in cases if import_scope_r0(c, (ROOT / "prompts/actor.md").read_text())]
    config = {"version": version, "dataset":dataset, "seed": manifest["seed"], "dispatch_seed": 20261024, "workers": 10,
              "model": "qwen3.8-flash", "temperature": 0, "actor_max_tokens": 4096,
              "writer_compiler_max_tokens": 8192, "max_retrieval_rounds": 2, "top_k": 24,
              "candidate_budget_initial": 12000, "candidate_budget_union": 24000, "source_budget": 24000,
              "budget_tokenizer": "cl100k_base_estimator_not_Qwen_certification", "max_input_bytes_gate": 2000000,
              "sample_cases": 200, "answer_cells": 600, "writer_namespaces": len(unique), "writer_chunks_planned": writer_chunks,
              "smoke_ids": smoke, "exact_prior_R0_actor_reuse_candidates": imported,
              "estimated_requests_without_repairs_or_reuse": writer_chunks + 200 * 2 + 200 * 2 + 200 * (1 + 2 + 1 + 1),
              "contract_repair_limit": 1, "unknown_or_partial_transport_retries": 0,
              "known_precontent_429_max_recoveries": 1, "rate_limit_cooldown_seconds": 120, "dispatch_spacing_seconds": 2,
              "transport_settings": {"socket_timeout_seconds":600,"stream_observation_limit_seconds":1200,"strict_absolute_deadline":False},
              "dns_cache_settings": {"ttl":300.,"max_stale":1800.,"retry_spacing":30.},
              "rate_limit_exhaustion": "stop_new_dispatch", "major_method_revisions_allowed": 2,
              "sota_claim": False, "full_evaluation": "conditional_on_development_results"}
    recovery_path = ROOT / 'configs' / f'service_recovery_{version}.json'
    if recovery_path.exists():
        config['service_recovery'] = json.loads(recovery_path.read_text())
    incomplete_path = ROOT / 'configs' / f'incomplete_recovery_{version}.json'
    if incomplete_path.exists():
        config['explicit_incomplete_recovery'] = json.loads(incomplete_path.read_text())
    dump(config_path, config)
    paths = sorted([p for p in (ROOT / "src").rglob("*.py")] + list((ROOT / "prompts").glob("*.md")) +
                   [config_path, ROOT / "configs/retrieval_models.json", manifest_path, ROOT / "requirements.lock.txt", ROOT / "PROTOCOL.md"] + ([settings_path] if settings_path.exists() else []))
    dump(ROOT / "configs" / f"source_freeze_{version}.json", {"file_sha256": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths},
                                                 "cases_path":str(cases_path.relative_to(ROOT)), "references_path":str(references_path.relative_to(ROOT)),
                                                 "cases_sha256": sha(cases_path.read_bytes()),
                                                 "evaluation_references_sha256": sha(references_path.read_bytes())})
    dump(ROOT / "reports" / f"PHASE0_ACCEPTANCE_{version}.json", {"data_verified": True, "cases": 200, "namespaces": len(unique),
         "writer_chunks": writer_chunks, "smoke": smoke, "historical_R0_reuse_candidates": len(imported),
         "LME_history_token_estimate_min_median_max": [lme[0]["history_tokens_cl100k_estimate"], statistics.median(c["history_tokens_cl100k_estimate"] for c in lme), lme[-1]["history_tokens_cl100k_estimate"]],
         "new_real_model_requests": 0})
    print(json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0")
    freeze(parser.parse_args().version)
