"""Build the existing BenchPreS paper baseline from pinned public rows."""
from pathlib import Path
from hashlib import sha256

import pyarrow.parquet as parquet

from qamc.common import sha
from qamc.pa.adapters import benchpres_public
from qamc.transport_helpers import atomic_json
from proposals.qamc_protocol_alignment.sampling import validate_public_request, sampling_key
from proposals.qamc_sentence_units.runtime import read
from qamc.contextual_match.native_generation import BENCHPRES_REPEATS
import run_qamc_benchpres_paper_prompt_bridge as pilot

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports/qamc_contextual_match_v2_20261112'
CATALOG = REPORTS / 'native_full_coverage_catalog_v1/CURRENT.json'
OUT = REPORTS / 'benchpres_formal_paper_bridge_v1'
NATIVE_SOURCE = ROOT / 'literature/bace_20261105/benchpres_test-00000-of-00001.parquet'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def request(public_prompt, defense, configuration):
    """Use the existing author-prompt bridge with the old transport envelope."""
    content = pilot.render(public_prompt, defense)
    if content.replace('\n' + defense, '', 1) != public_prompt:
        raise ValueError('Non-defense bytes differ from the source prompt')
    body = {**configuration, 'messages': [{'role': 'user', 'content': content}]}
    validate_public_request(body)
    return body


def source_rows():
    catalog = read(CATALOG)
    rows = sorted((r for r in catalog['rows'] if r['benchmark'] == 'benchpres'),
                  key=lambda r: r['row_index'])
    if [r['row_index'] for r in rows] != list(range(390)):
        raise ValueError('BenchPreS source population changed')
    if {r['source_file'] for r in rows} != {str(NATIVE_SOURCE.relative_to(ROOT))}:
        raise ValueError('Unexpected BenchPreS source identity')
    if {r['source_sha256'] for r in rows} != {digest(NATIVE_SOURCE)}:
        raise ValueError('Pinned BenchPreS source changed')
    # Keep evaluation labels out of generation construction.
    prompts = parquet.read_table(NATIVE_SOURCE, columns=['prompt']).column(0).to_pylist()
    if len(prompts) != len(rows):
        raise ValueError('Public rows do not align with the official catalogue')
    return rows, prompts


def build():
    rows, prompts = source_rows()
    old_plan = read(pilot.OUT / 'PLAN.json')
    pilot.check(old_plan)
    old_cases = {row['row_index']: row for row in old_plan['cases']}
    old_requests = {j['unit']['root_id']: j for j in old_plan['initial']}
    old_results = {r['uid']: r for r in read(pilot.OUT / 'PILOT.json')['rows']}
    wire_config = {k: v for k, v in old_plan['initial'][0]['request'].items() if k != 'messages'}
    defense = pilot.DEFENSE.read_text().strip()
    protocol = {'benchmark': 'benchpres', 'model': wire_config['model'],
                'repeat_policy': BENCHPRES_REPEATS,
                'actor_temperature': wire_config['temperature'],
                'actor_max_tokens': wire_config['max_tokens'],
                'purpose': 'sample-key inventory only, no dispatch'}
    if protocol['actor_temperature'] != 1:
        raise ValueError('Paper protocol temperature differs')
    requests = []
    artifact_paths = []
    for row, raw in zip(rows, prompts, strict=True):
        index = row['row_index']
        public = benchpres_public(raw, row['uid']).payload()
        if sha(public) != row['public_input_sha256']:
            raise ValueError(f'BenchPreS row {index} no longer matches the common candidate input')
        body = request(raw, defense, wire_config)
        unit_keys = [sampling_key({'protocol_sha256': sha(protocol), 'root_id': row['uid'],
                                  'method': pilot.METHOD, 'replicate': sample, 'stage': 'Actor'})
                     for sample in range(BENCHPRES_REPEATS['benchpres'])]
        item = {'uid': row['uid'], 'row_index': index, 'profile_group': row['analysis_group_id'],
                'public_input_sha256': sha(public), 'paper_actor_request_sha256': sha(body),
                'illustrative_sampling_keys': unit_keys,
                'is_prior_156_development_root': row['matches_current_development_payload']}
        if index in old_cases:
            prior = old_cases[index]
            uid = prior['uid']
            old_job = old_requests[uid]
            if old_job['request'] != body or prior['source_id'] != row['catalog_id']:
                raise ValueError('Saved paper prompt bridge does not match the reconstructed request')
            output_path = pilot.RUN / 'outputs' / (sampling_key(old_job['unit']) + '.json')
            output = read(output_path)
            if output['request_sha256'] != sha(body):
                raise ValueError('Saved pilot response has a different request hash')
            saved_answer = old_results[uid].get('answer')
            identical_answer = (bool(saved_answer) and output['status'] == 'OK'
                                and output.get('response', {}).get('answer') == saved_answer)
            item['historic_single_draw'] = {'uid': uid, 'answer_status': old_results[uid]['actor_status'],
                                            'answer_equal': identical_answer}
            artifact_paths.append(output_path)
        requests.append(item)
    if len({key for row in requests for key in row['illustrative_sampling_keys']}) != 1170:
        raise ValueError('Three independent sampling positions per root required')
    protected = (Path(__file__).resolve(), CATALOG, NATIVE_SOURCE, Path(pilot.__file__).resolve(),
                 pilot.DEFENSE, pilot.OUT / 'PLAN.json', pilot.OUT / 'PILOT.json', *artifact_paths)
    return {'methods': [pilot.METHOD], 'protocol_preview': protocol, 'official_rows': len(rows),
            'profile_groups': len({r['profile_group'] for r in requests}),
            'prior156_overlap': sum(r['is_prior_156_development_root'] for r in requests),
            'old_paper_pilot_draws_verified': sum(
                r.get('historic_single_draw', {}).get('answer_equal', False) for r in requests),
            'positions_per_method': {'independent_actor': 1170, 'existing_six_stage_judge_estimate': 7020},
            'prior_pilot_draws_counted_as_new_independent_repeats': 0,
            'rows': requests, 'public_prompts_or_labels_exported': False,
            'dispatch_plan_created': False, 'new_model_calls': 0,
            'source_pins': {str(p.relative_to(ROOT)): digest(p) for p in protected}}


if __name__ == '__main__':
    result = build()
    atomic_json(OUT / 'PUBLIC_REQUEST_REPLAY.json', result)
    print({k: v for k, v in result.items() if k not in ('rows', 'source_pins')})
