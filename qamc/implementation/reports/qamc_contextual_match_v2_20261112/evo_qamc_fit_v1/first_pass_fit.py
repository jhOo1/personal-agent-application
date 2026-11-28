"""Run the initial equal-budget round of whole-instruction search on the fit panel."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from first_pass_inputs import fit_feedback
from first_pass_policy import ARMS as SEARCH_ARMS, METHOD, PROPOSER, SEED, validate
from joint_context import OUT as JOINT, engine, grading, metrics, prepare as fit, probe, read, sha, views, wire
from baselines import rpe, transfer

OUT = JOINT.with_name('evo_qamc_fit_v1_whole_actor_search_v1')
METHODS = ('SEED', *SEARCH_ARMS)
MODES = ('OPT_GATE', 'JCC')


def feedback_packet(offline, mode, seeds):
    cases = [case for contrasts in offline['examples'].values() for case in contrasts]
    packet = {'available_parent_systems': seeds,
              'task_contexts': [dict(task=c['task'], original_history=c['history']) for c in cases]}
    if mode == 'CRITERIA_SEARCH':
        packet['matched_contrasts'] = [
            dict(context_index=i, runs=[dict(answer=c['parent_answer'], observations=c['current'],
                                            method='current_shared'),
                                        dict(answer=c['comparison_answer'], observations=c['reference'],
                                             method='archive_specialist')])
            for i,c in enumerate(cases)]
    else:
        packet['individual_traces'] = [
            dict(context_index=i, answer=c[answer], observations=c[score], method=owner)
            for answer, score, owner in (('parent_answer', 'current', 'current_shared'),
                                          ('comparison_answer', 'reference', 'archive_specialist'))
            for i,c in enumerate(cases)]
    return packet


def quick_panel(cards):
    out, used = [], set()
    for domain, kind in (('RPEval','all_A'), ('RPEval','B_only'), ('RPEval','contains_C'),
                         ('PersistBench','sycophancy'), ('PersistBench','cross_domain'),
                         ('PersistBench','beneficial_memory_usage')):
        group_candidates = [c for c in cards if (c['domain'],c['stratum']) == (domain,kind)
                            and (domain,c['group']) not in used]
        chosen = min(group_candidates, key=lambda c:sha(['whole-pass-fit-0',c['uid']]))
        out.append(chosen)
        used.add((domain,chosen['group']))
    for domain, kind in (('RPEval',None), ('BenchPreS',None), ('PersistBench',None)):
        pool = sorted((c for c in cards if c['domain'] == domain),
                      key=lambda c:sha(['whole-pass-fit-0',c['uid']]))
        for c in pool:
            if sum(row['domain'] == domain for row in out) == 4:
                break
            identity = domain,c['group']
            if identity not in used:
                out.append(c)
                used.add(identity)
        if sum(row['domain'] == domain for row in out) != 4:
            raise ValueError(f'No four fit source groups for {domain}')
    return out


def prepare():
    fit_pin, cards, originals, _, _, _ = fit()
    outcomes = read(JOINT/'RESULTS.json')['rows']
    original_rows = {(r['uid'],r['method']):r for r in outcomes}
    all_caps = quick_panel(cards)
    bases = {'RPEval':rpe(), 'BenchPreS':transfer('BenchPreS'),
             'PersistBench':transfer('PersistBench')}
    examples = fit_feedback({uid:r for (uid,arm),r in original_rows.items() if arm == 'JCC'},
                             {c['uid']:c for c in cards}, bases)
    # Clip only the offline example completions equally for both search methods.
    offline = {'examples': {domain: [
        {**ex,'parent_answer':ex['parent_answer'][:2800],
         'comparison_answer':ex['comparison_answer'][:2800]}
        for ex in cells] for domain,cells in examples.items()}}
    systems = {originals[c['uid']]['messages'][0]['content'] for c in all_caps}
    if len(systems) != 1:
        raise ValueError('Expected one archived Scope Actor')
    seed_systems = [systems.pop(), SEED]
    proposals = {arm:wire(PROPOSER + '\n\n' + METHOD[arm],
                          feedback_packet(offline, arm, seed_systems), 4096) for arm in SEARCH_ARMS}
    decisions = {(uid,arm):value for uid, arm, value in read(JOINT/'private/DECISIONS.json')}
    inputs = {}
    for c in all_caps:
        uid = c['uid']
        for route in MODES:
            payload = views(originals[uid], c['payload']['source_evidence'], route,
                            json.dumps(decisions[uid,route]))[route]
            if sha(payload) != original_rows[uid,route]['actor_request_sha256']:
                raise ValueError('Settled source wire not recovered')
            inputs[uid,route] = payload
    pin = dict(
        implementation=sha(Path(__file__).read_bytes()),
        policy_code=sha(Path(__file__).with_name('first_pass_policy.py').read_bytes()),
        fixture=sha(fit_pin), fitness_roster=[c['uid'] for c in all_caps],
        baseline=sha(outcomes), offline=sha(offline), service_reference_sha256=probe.read_reference()[1],
        offline_proposal_sha256={arm:sha(body) for arm,body in proposals.items()},
        exact_upstream=[[uid,route,sha(body)] for (uid,route),body in inputs.items()],
        actor_maximum=72, proposal_maximum=2,
    )
    return pin, all_caps, inputs, proposals, offline, original_rows


def summarize(cards, rows, reference, ledger):
    new = {(r['uid'],r['method']):r for r in rows}
    totals, coverage = {}, Counter()
    for c in cards:
        uid, domain, stratum = (c[k] for k in ('uid','domain','stratum'))
        for mode in MODES:
            indexed = {'BASE':{'score':c['base_score'],'score_flags':c['base_flags']},
                       'SCOPE':reference[uid,mode],
                       **{arm:new[uid,mode+'/'+arm] for arm in METHODS}}
            all_scores = {name:metrics(c,row['score']) for name,row in indexed.items()}
            for name, val in all_scores.items():
                coverage[domain+'/'+mode+'/'+name] += val is not None
            parts = [domain]
            if domain != 'BenchPreS':
                parts.append(domain+'/'+stratum)
            for key in parts:
                slot = totals.setdefault(mode, {}).setdefault(key, dict(
                    assigned=0, common=0, clean=0,
                    metrics={name:Counter() for name in indexed},
                    unflagged={name:Counter() for name in indexed}))
                slot['assigned'] += 1
                if any(v is None for v in all_scores.values()):
                    continue
                slot['common'] += 1
                clean = domain == 'RPEval' and all(row.get('score_flags') == [] for row in indexed.values())
                slot['clean'] += clean
                for name,val in all_scores.items():
                    slot['metrics'][name].update(val)
                    if clean:
                        slot['unflagged'][name].update(val)
    return dict(rollups=totals, coverage=coverage,
                physical=Counter(x['unit']['stage'] for x in ledger),
                status=Counter(x['status'] for x in ledger),
                tokens=sum((x.get('usage') or {}).get('total_tokens') or 0 for x in ledger),
                unknown_usage=sum('total_tokens' not in (x.get('usage') or {}) for x in ledger))


def run(pin, cards, inputs, proposals, feedback, reference):
    directory = OUT/'private'
    probe.RUN, probe.OUT, engine.OUT = OUT, directory, directory
    counts = Counter(c['domain'] for c in cards)
    engine.CAP = {'Propose':2,'Actor':72,engine.RPE:counts['RPEval']*6,
                  'BenchAttrs':counts['BenchPreS']*36,'PersistNative':counts['PersistBench']*6}
    identity = dict(experiment_sha256=sha(pin), service_reference_sha256=pin['service_reference_sha256'])
    ledger = []
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name, requested, cache=None):
            return engine.stage(name, requested, identity, True, ledger, cache) if requested else {}

        proposal_receipts = stage('Propose', {('whole_actor',arm):body for arm,body in proposals.items()})
        systems = {'SEED':SEED}
        failures = {}
        for (_,arm), receipt in proposal_receipts.items():
            if receipt['status'] != 'OK':
                failures[arm] = receipt['status']
                continue
            try:
                systems[arm] = validate(receipt['answer'], feedback)
            except ValueError as exc:
                failures[arm] = str(exc)
        probe.freeze(directory/'PROPOSALS.json', dict(systems=systems, validation=failures))
        jobs = {}
        targets = {}
        for c in cards:
            uid = c['uid']
            for mode in MODES:
                source = inputs[uid,mode]
                for arm in METHODS:
                    key = (uid,mode+'/'+arm)
                    targets[key] = dict(uid=uid,method=key[1],benchmark=c['domain'],stratum=c['stratum'],
                                        sources=c['payload']['source_evidence'],actor_status=failures.get(arm),
                                        answer=None,score=None,score_flags=None)
                    if arm in systems:
                        request = deepcopy(source)
                        request['messages'][0]['content'] = systems[arm]
                        jobs[key] = request
        for key, receipt in stage('Actor', jobs).items():
            targets[key].update(actor_status=receipt['status'],answer=receipt.get('answer'),
                                actor_request_sha256=receipt['request_sha256'])
            uid, method = key
            old = reference[uid,method.split('/')[0]]
            if receipt['status'] == 'OK' and old['answer'] == receipt.get('answer'):
                targets[key].update(score=old['score'],score_flags=old.get('score_flags'))
        rows = list(targets.values())
        grading(rows, stage)
        probe.freeze(OUT/'RESULTS.json',dict(rows=rows,ledger=ledger))
        print(json.dumps(summarize(cards,rows,reference,ledger),indent=2),flush=True)


if __name__ == '__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','run','report'))
    args = cli.parse_args()
    bundle = prepare()
    path = OUT/'private/FROZEN.json'
    if args.action == 'freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,bundle[0])
        print(dict(assigned=len(bundle[1]),proposals=len(bundle[3]),upstream=len(bundle[2])))
    elif read(path) != bundle[0]:
        raise ValueError('Frozen first-pass fit arguments changed')
    elif args.action == 'run':
        run(*bundle)
    else:
        result = read(OUT/'RESULTS.json')
        print(json.dumps(summarize(bundle[1],result['rows'],bundle[-1],result['ledger']),indent=2))
