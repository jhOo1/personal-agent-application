"""Transfer settled controller decisions into exact archived Actor contracts."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from joint_context import (
    OUT as JOINT, engine, grading, metrics, prepare as fit, probe, read, sha, views,
)
from baselines import archive
from qamc.contextual_match.cache import service_filtered
from qamc.contextual_match.cache_inventory import inventory
from qamc.contextual_match.lossless_transport import filter_compatible_cache

OUT = JOINT.with_name('evo_qamc_fit_v1_pinned_actor_v1')
ARMS = ('PIN_GATE', 'PIN_JCC')


def memory_block(sources):
    return '<memories>\n' + '\n'.join('- ' + row['text'] for row in sources) + '\n</memories>'


def replace_block(system, original, chosen):
    block = memory_block(original)
    if system.count(block) != 1:
        raise ValueError('MEMORY_BLOCK_NOT_EXACT')
    before, after = system.split(block)
    if any(row['text'] in before + after for row in original if row not in chosen):
        raise ValueError('REMOVED_SOURCE_OUTSIDE_BLOCK')
    return before + memory_block(chosen) + after


def case_requests(domain, original, task, full, chosen):
    wire = deepcopy(original['actor_request'])
    if original['actor_request_sha256'] != sha(wire):
        raise ValueError('ARCHIVE_REQUEST_HASH_MISMATCH')
    system, user = wire['messages']
    if domain == 'PersistBench':
        if user['content'] != task['query'] or task['facts'] or task['current_context']:
            raise ValueError('ARCHIVE_TASK_MISMATCH')
        system['content'] = replace_block(system['content'], full, chosen)
        return wire

    payload = json.loads(user['content'])
    ids = {row['memory_id'] for row in chosen}
    if domain == 'RPEval':
        if (any(payload[key] != val for key, val in task.items())
                or payload['source_evidence'] != full):
            raise ValueError('RPEVAL_FIELDS_MISMATCH')
        policy = payload['preference_use_policy']
        if {p['memory_id'] for p in policy} != {s['memory_id'] for s in full} or len(policy) != len(full):
            raise ValueError('RPEVAL_POLICY_IDS_MISMATCH')
        payload['source_evidence'] = chosen
        payload['preference_use_policy'] = [p for p in policy if p['memory_id'] in ids]
    else:
        if (payload['query'] != task['query'] or payload['current_context'] != task['current_context']
                or payload['fixed_facts'] != task['facts']):
            raise ValueError('BENCH_TASK_MISMATCH')
        selected = original['view']['source_evidence']
        if any(s not in full for s in selected) or any(s not in selected for s in chosen):
            raise ValueError('NO_ARCHIVED_GUIDANCE_FOR_ADDED_SOURCE')
        guidance = payload['selected_memory_use_guidance']
        if [g['memory_position_1_based'] for g in guidance] != list(range(1, len(selected)+1)):
            raise ValueError('BENCH_GUIDANCE_POSITIONS_MISMATCH')
        mapped = {s['memory_id']: g['use_instruction'] for s, g in zip(selected, guidance)}
        if any(s['text'] in mapped[g['memory_id']] for s in selected if s not in chosen for g in chosen):
            raise ValueError('REMOVED_SOURCE_IN_GUIDANCE')
        payload['selected_memory_use_guidance'] = [
            {'memory_position_1_based': position, 'use_instruction': mapped[s['memory_id']]}
            for position, s in enumerate(chosen, 1)
        ]
        system['content'] = replace_block(system['content'], selected, chosen)
    # Keep a byte-identical archive request when the semantic payload is unchanged.
    if json.loads(user['content']) != payload:
        user['content'] = json.dumps(payload, ensure_ascii=False)
    return wire


def archives(cards):
    uids = {c['uid'] for c in cards}
    result = {}
    inputs = [row for row in read(archive.v41.formal.OUT/'RESULT_ROWS.json')
              if row['method'] == engine.RP and row['uid'] in uids]
    for domain, method in (('BenchPreS', engine.GATE), ('PersistBench', 'PB_RUBRIC')):
        cases, _, _ = archive.transfer.context(domain)
        inputs.extend(r for r in archive.transfer.archived_answers(domain, uids & cases.keys())
                      if r['method'] == method)
    for row in inputs:
        if row['actor_status'] == 'OK':
            uid = row['uid']
            if uid in result:
                raise ValueError('Conflicting pinned Actor archives')
            result[uid] = row
    return result


def prior_receipts(requests, cache, service):
    root = Path.cwd()
    wanted = {sha(wire) for wire in requests.values()}
    index = inventory(root, wanted)
    index['records'] = [row for row in index['records']
                        if OUT.name not in Path(row['origin']).parts]
    index = filter_compatible_cache(root, service_filtered(root, index, wanted, service))
    blocked = set()
    for row in index['records']:
        digest = row['body_sha256']
        if row['status'] == 'ok' and row['response_path']:
            answer = read(root / row['response_path']).get('answer')
            if isinstance(answer, str) and answer.strip():
                cache[digest].add(answer)
                continue
        blocked.add(digest)
    return blocked


def prepare():
    parent, cards, originals, scope, _, _ = fit()
    result = read(JOINT/'RESULTS.json')
    decisions = {(uid, arm): value for uid, arm, value in read(JOINT/'private/DECISIONS.json')}
    old = archives(cards)
    previous_rpe = {row['uid']: row for row in read(
        Path(__file__).resolve().parent.parent/'ipe_c_two_endpoint_completion_v1/RESULTS.json')['rows']}
    service = probe.read_reference()[1]
    jobs, statuses, reference = {}, {}, {}
    cache = defaultdict(set)
    report_rows = {(r['uid'], r['method']): r for r in result['rows']}
    for card in cards:
        uid, domain = card['uid'], card['domain']
        task, full = (card['payload'][key] for key in ('task', 'source_evidence'))
        original = old[uid]
        reference[uid] = dict(base=card['base_score'], scope=scope[uid]['score'],
                              gate=report_rows[uid,'OPT_GATE'], joint=report_rows[uid,'JCC'])
        cache[original['actor_request_sha256']].add(original['answer'])
        reference[uid]['archived_grades'] = {}
        if domain == 'RPEval':
            previous = previous_rpe[uid]
            rp = previous['scores'][engine.RP]
            if rp['answer_sha256'] != sha(original['answer']):
                raise ValueError('RP score does not match the pinned archive')
            reference[uid]['archived_grades'][rp['answer_sha256']] = rp
            zero = previous['no_history_state']
            if zero.get('answer'):
                task_wire = case_requests(domain, original, task, full, [])
                from_score = previous['scores']['TASK_ONLY']
                if sha(zero['answer']) != from_score['answer_sha256']:
                    raise ValueError('Task-only score does not match the archived completion')
                cache[sha(task_wire)].add(zero['answer'])
                reference[uid]['archived_grades'][from_score['answer_sha256']] = from_score
        else:
            reference[uid]['archived_grades'][sha(original['answer'])] = dict(
                grade=card['base_score'], flags=card['base_flags'])
        for decision, arm in zip(('OPT_GATE', 'JCC'), ARMS):
            key = uid, arm
            if (uid, decision) not in decisions:
                statuses[key] = 'NO_CONTROL_RECEIPT'
                continue
            request = views(originals[uid], full, decision, json.dumps(decisions[uid, decision]))[decision]
            if sha(request) != report_rows[uid, decision]['actor_request_sha256']:
                raise ValueError('Controller does not reconstruct original Scope experiment')
            subset = json.loads(request['messages'][1]['content'])['source_evidence']
            try:
                jobs[key] = case_requests(domain, original, task, full, subset)
            except ValueError as error:
                statuses[key] = str(error)
    blocked = prior_receipts(jobs, cache, service)
    for key, wire in list(jobs.items()):
        digest = sha(wire)
        if len(cache[digest]) > 1:
            statuses[key] = 'AMBIGUOUS_EXACT_ARCHIVE'
            del jobs[key]
        elif not cache[digest] and digest in blocked:
            statuses[key] = 'PRIOR_ATTEMPT_NOT_REISSUED'
            del jobs[key]
    for card in cards:
        uid = card['uid']
        if not all((uid, arm) in jobs for arm in ARMS):
            for arm in ARMS:
                if jobs.pop((uid, arm), None) is not None:
                    statuses[uid, arm] = 'UNPAIRED_INPUT'
    wanted = {sha(wire) for wire in jobs.values()}
    cache = {digest: next(iter(answers)) for digest, answers in cache.items()
             if len(answers) == 1 and digest in wanted}
    pin = dict(code=sha(Path(__file__).read_bytes()), parent=sha(parent),
               results=sha(result), reconciliation=sha(reference),
               service_reference_sha256=service, cached_response_hashes={h:sha(a) for h,a in cache.items()},
               jobs=[[uid, arm, sha(request)] for (uid, arm), request in jobs.items()],
               unconstructed=[[uid, arm, status] for (uid, arm), status in statuses.items()])
    return pin, cards, jobs, statuses, reference, cache


def summary(cards, rows, ledger, ref):
    indexed = {(row['uid'], row['method']): row for row in rows}
    totals = defaultdict(lambda: dict(assigned=0, common=0, unflagged=0,
        values=defaultdict(Counter), clean=defaultdict(Counter), status=Counter(), paired=Counter()))
    for card in cards:
        uid, domain = card['uid'], card['domain']
        r = ref[uid]
        a, b = (indexed[uid, key] for key in ARMS)
        scores = dict(STRONG=r['base'], SCOPE_GATE=r['gate']['score'], SCOPE_JCC=r['joint']['score'],
                      PIN_GATE=a['score'], PIN_JCC=b['score'])
        values = {arm: metrics(card, score) for arm, score in scores.items()}
        clean = domain == 'RPEval' and all(flag == [] for flag in (
            card['base_flags'], r['gate'].get('score_flags'), r['joint'].get('score_flags'),
            a.get('score_flags'), b.get('score_flags')))
        for name in (domain, domain + '/' + card['stratum']):
            d = totals[name]
            d['assigned'] += 1
            d['status'].update((a['actor_status'], b['actor_status']))
            if any(value is None for value in values.values()):
                continue
            if len({(v['positions'], v.get('MR_denominator')) for v in values.values()}) != 1:
                raise ValueError('Compared denominators differ')
            d['common'] += 1
            delta = values['PIN_JCC']['primary'] - values['PIN_GATE']['primary']
            d['paired']['win' if delta > 0 else 'loss' if delta < 0 else 'tie'] += 1
            for arm, value in values.items():
                d['values'][arm].update(value)
                if clean:
                    d['clean'][arm].update(value)
            d['unflagged'] += clean
    return dict(domains=totals,
                dispatch=Counter(r['unit']['stage'] for r in ledger),
                statuses=Counter(r['status'] for r in ledger),
                tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger),
                unknown_usage=sum('total_tokens' not in (r.get('usage') or {}) for r in ledger))


def run(pin, cards, jobs, statuses, reference, cache):
    probe.RUN, probe.OUT, engine.OUT = OUT, OUT/'private', OUT/'private'
    counts = Counter(c['domain'] for c in cards)
    engine.CAP = {'Actor': len(jobs), engine.RPE: counts['RPEval']*2,
                  'BenchAttrs': counts['BenchPreS']*12, 'PersistNative': counts['PersistBench']*2}
    identity = dict(experiment_sha256=sha(pin), service_reference_sha256=pin['service_reference_sha256'])
    ledger = []
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name, requests, reused=None):
            return engine.stage(name, requests, identity, True, ledger, reused) if requests else {}

        received = stage('Actor', jobs, cache)
        rows = []
        for card in cards:
            uid = card['uid']
            for arm in ARMS:
                key = uid, arm
                reply = received.get(key, {})
                row = dict(uid=uid, method=arm, benchmark=card['domain'], stratum=card['stratum'],
                           sources=card['payload']['source_evidence'],
                           actor_status=reply.get('status', statuses.get(key)),
                           actor_request_sha256=reply.get('request_sha256'), answer=reply.get('answer'),
                           score=None, score_flags=None)
                if row['actor_status'] == 'OK':
                    saved = reference[uid]['archived_grades'].get(sha(row['answer']))
                    if saved and saved['grade']:
                        row.update(score=saved['grade'], score_flags=saved['flags'])
                rows.append(row)
        grading(rows, stage)
        probe.freeze(OUT/'RESULTS.json', dict(rows=rows, ledger=ledger))
    return summary(cards, rows, ledger, reference)


if __name__ == '__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('inventory', 'freeze', 'run', 'report'))
    args = cli.parse_args()
    inputs = prepare()
    pin, cards, jobs, statuses, reference, cache = inputs
    path = OUT/'private/FROZEN.json'
    if args.action == 'freeze':
        path.parent.mkdir(parents=True, exist_ok=True)
        probe.freeze(path, pin)
    elif args.action != 'inventory' and read(path) != pin:
        raise ValueError('Transfer manifest drift')
    if args.action == 'run':
        response = run(*inputs)
    elif args.action == 'report':
        saved = read(OUT/'RESULTS.json')
        response = summary(cards, saved['rows'], saved['ledger'], reference)
    else:
        domains = {card['uid']:card['domain'] for card in cards}
        response = {
            'eligible_pairs': dict(Counter(domains[uid] for uid, arm in jobs if arm == 'PIN_GATE'
                                           and (uid, 'PIN_JCC') in jobs)),
            'status': dict(Counter(statuses.values())),
            'eligible_distinct_requests': dict(Counter(domains[uid] for uid, arm in jobs
                if arm == 'PIN_GATE' and (uid,'PIN_JCC') in jobs and jobs[uid,arm] != jobs[uid,'PIN_JCC'])),
            'new_unique_wires_after_exact_archive_scan': len({sha(w) for w in jobs.values()} - cache.keys()),
        }
    print(json.dumps(response, indent=2), flush=True)
