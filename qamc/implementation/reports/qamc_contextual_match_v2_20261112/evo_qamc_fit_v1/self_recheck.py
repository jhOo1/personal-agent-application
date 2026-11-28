"""Run the released ID selector on the same fit panel and final Actor."""
from argparse import ArgumentParser
from collections import Counter
import importlib.util
import json
from pathlib import Path

from trial import ACTOR, HERE, RUN, engine, grading, probe, sha, wire

OUT = RUN.with_name(RUN.name + '_self_recheck')
MOD = HERE.parent/'persist_public_self_recheck_v1/trial.py'


def released():
    spec = importlib.util.spec_from_file_location('persist_self_recheck_archive', MOD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prompt, parser = module.released()
    return module.rev, prompt, parser


def input_for(row):
    memories = [{'memory_id': f'memory_{i:02d}', 'content': item['text']}
                for i, item in enumerate(row['payload']['source_evidence'], 1)]
    return {'question': row['payload']['task']['query'], 'retrieved_memories': memories}


def prepare():
    previous = json.loads((RUN/'private/FROZEN.json').read_text())
    revision, prompt, parser = released()
    inputs = {row['uid']: input_for(row) for row in previous['rows']}
    requests = {(uid, 'SELF_RECHECK'): wire(prompt, packet, 8192) for uid, packet in inputs.items()}
    plan = dict(pin=sha(previous), revision=revision, code_hash=sha(Path(__file__).read_bytes()),
                service_reference_sha256=probe.read_reference()[1],
                request_hashes={uid: sha(req) for (uid, _), req in requests.items()})
    return plan, previous, inputs, requests, parser


def exact_selector_cache():
    """Reuse completed matching wires from the published 49-root comparator."""
    prior = OUT.parent/'persist_public_self_recheck_v1'
    cache, inconsistent = {}, set()
    for label in ('D1Select', 'D2Select', 'D3Select'):
        for record_file in (prior/label/'visible').glob('*/record.json'):
            record = json.loads(record_file.read_text())
            if record['status'] != 'OK':
                continue
            request = json.loads(record_file.with_name('request.json').read_text())
            response = json.loads(record_file.with_name('response.json').read_text())
            digest = sha(request)
            assert digest == record['request_sha256']
            if cache.setdefault(digest, response['answer']) != response['answer']:
                inconsistent.add(digest)
    return {key: value for key, value in cache.items() if key not in inconsistent}


def run(plan, previous, inputs, requests, parser):
    probe.RUN, probe.OUT, engine.OUT = OUT, OUT/'private', OUT/'private'
    engine.CAP = {'Selection': 40, 'Actor': 40, engine.RPE: 16, 'BenchAttrs': 72, 'PersistNative': 12}
    ledger = []
    identity = {'experiment_sha256': sha(plan), 'service_reference_sha256': plan['service_reference_sha256']}
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, identity, True, ledger, cache) if jobs else {}

        replies = stage('Selection', requests, exact_selector_cache())
        rows, generation = {}, {}
        for card in previous['rows']:
            uid = card['uid']
            key = uid, 'SELF_RECHECK'
            reply = replies[key]
            row = dict(uid=uid, method=key[1], benchmark=card['domain'], group=card['group'],
                       stratum=card['stratum'], sources=card['payload']['source_evidence'],
                       actor_status='NOT_DISPATCHED', score=None, answer=None,
                       selection_status=reply['status'], selection_origin=reply['origin'])
            rows[key] = row
            if reply['status'] != 'OK':
                continue
            memories = inputs[uid]['retrieved_memories']
            try:
                ids = parser(reply['answer'], memories, partition=False)
                declared = json.loads(reply['answer'])
            except (ValueError, TypeError, KeyError, AttributeError):
                row['selection_status'] = 'INVALID_ID_RESPONSE'
                continue
            row['field_present'] = 'keep_memory_ids' in declared
            sources = [original for memory, original in zip(memories, row['sources'], strict=True)
                       if memory['memory_id'] in ids]
            row['selected_count'] = len(sources)
            generation[key] = wire(ACTOR.replace('Use the plan as guidance. Verify any suggestion in it against the current task and supplied original memory. ',
                                                'Use the selected historical evidence where it is applicable. '),
                                   {'task': card['payload']['task'], 'source_evidence': sources}, 8192)
        for key, reply in stage('Actor', generation).items():
            rows[key].update(actor_status=reply['status'], answer=reply.get('answer'))
        items = list(rows.values())
        grading(items, stage)
        probe.freeze(OUT/'RESULTS.json', dict(rows=items, ledger=ledger))
        print(Counter((r['unit']['stage'], r['status']) for r in ledger), flush=True)


if __name__ == '__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('freeze', 'check', 'run'))
    action = cli.parse_args().action
    spec = prepare()
    path = OUT/'private/FROZEN.json'
    if action == 'freeze':
        path.parent.mkdir(parents=True, exist_ok=True)
        probe.freeze(path, spec[0])
    else:
        assert json.loads(path.read_text()) == spec[0]
        if action == 'run':
            run(*spec)
    print('Assigned selector requests:', len(spec[3]))
