"""Run a matched second whole-Actor round using actual same-input first-round outcomes."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from first_pass_fit import OUT as FIRST, MODES, prepare as first, summarize
from first_pass_policy import ARMS, METHOD, PROPOSER, SEED, validate
from first_pass_readout import score
from joint_context import engine, grading, metrics, probe, read, sha, wire

OUT = FIRST.with_name('evo_qamc_fit_v1_whole_actor_search_r2')


def feedback(cards, up, old, current):
    examples = {}
    chosen = []
    for domain in ('RPEval','BenchPreS','PersistBench'):
        candidates = []
        for card in cards:
            uid = card['uid']
            if card['domain'] != domain:
                continue
            traces = {arm:current[uid,'JCC/'+arm] for arm in ARMS}
            traces['SCOPE'] = old[uid,'JCC']
            values = {name:metrics(card,row['score']) for name,row in traces.items()}
            if any(value is None for value in values.values()):
                continue
            primary = [v['primary'] for v in values.values()]
            flagged = domain == 'RPEval' and any(t.get('score_flags') != [] for t in traces.values())
            candidates.append(((flagged,-(max(primary)-min(primary)),sha(uid)),
                               card,traces,values))
        # Include two groups per domain when available, keeping flagged feedback explicit.
        for (flagged, _, _), card, traces, values in sorted(candidates)[:2]:
            uid = card['uid']
            user_input = json.loads(up[uid,'JCC']['messages'][1]['content'])
            chosen.append((card,user_input,traces,values,flagged))
            examples.setdefault(domain,[]).append({
                'task':user_input['task'], 'history':user_input['source_evidence'],
                'parent_answer':traces['SCOPE']['answer'],
                'comparison_answer':traces['GENERIC_SEARCH']['answer'],
            })
            examples[domain].append({
                'task':user_input['task'], 'history':user_input['source_evidence'],
                'parent_answer':traces['CRITERIA_SEARCH']['answer'],
                'comparison_answer':traces['SCOPE']['answer'],
            })
    if len(examples) != 3:
        raise ValueError('Settled round does not supply common examples in every benchmark')
    return chosen, {'examples':examples}


def packet(selected, mode, parents, answer_chars):
    entries, use = [], []
    for i, (_,user_input,traces,values,flagged) in enumerate(selected):
        entries.append(dict(actual_actor_input=user_input,known_score_conflict=flagged))
        use.append([dict(context_index=i, actor=name, answer=cell['answer'][:answer_chars],
                         observed=values[name]) for name,cell in traces.items()])
    data = dict(prior_systems=parents,contexts=entries)
    if mode == 'CRITERIA_SEARCH':
        data['matched_runs'] = use
    else:
        data['individual_traces'] = [group[k] for k in range(3) for group in use]
    return data


def prepare():
    pin,cards,up,_,_,base = first()
    if pin != read(FIRST/'private/FROZEN.json'):
        raise ValueError('First whole-Actor round manifest drift')
    first_results = read(FIRST/'RESULTS.json')
    prior = {(item['uid'],item['method']):item for item in first_results['rows']}
    systems = read(FIRST/'private/PROPOSALS.json')['systems']
    if any(arm not in systems for arm in ARMS):
        raise ValueError('Cannot compare equal revisions from failed branch')
    selected, reject = feedback(cards,up,base,prior)
    prior_systems = dict(SCOPE=next(iter(up.values()))['messages'][0]['content'],
                         SEED=SEED,**{arm:systems[arm] for arm in ARMS})
    for answer_chars in (2400, 1800, 1200, 700):
        try:
            proposals = {arm:wire(PROPOSER+'\n\n'+METHOD[arm]+
                                '\nUse the observed rollouts to propose a second-generation system. '
                                'You may keep, remove, or restructure a prior behavior but release one complete instruction.',
                                packet(selected,arm,prior_systems,answer_chars),4096)
                         for arm in ARMS}
            break
        except ValueError as exc:
            if 'Input capacity' not in str(exc) or answer_chars == 700:
                raise
    spec = dict(first=sha(pin),realizations=sha(first_results),
                code=sha(Path(__file__).read_bytes()),
                service_reference_sha256=probe.read_reference()[1],
                proposals={arm:sha(req) for arm,req in proposals.items()},
                feedback_groups=len(selected),answer_excerpt_chars=answer_chars)
    return spec,cards,up,base,prior,reject,proposals


def run(pin,cards,up,base,prior,reject,proposals):
    probe.RUN,probe.OUT,engine.OUT = OUT,OUT/'private',OUT/'private'
    engine.CAP = {'Propose':2,'Actor':48,engine.RPE:16,'BenchAttrs':96,'PersistNative':16}
    identity = dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    ledger = []
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name, jobs, cache=None):
            return engine.stage(name,jobs,identity,True,ledger,cache) if jobs else {}
        systems, failures = {}, {}
        for (_,arm),receipt in stage('Propose',{('whole_actor_round2',a):r for a,r in proposals.items()}).items():
            if receipt['status'] != 'OK':
                failures[arm] = receipt['status']
                continue
            try:
                systems[arm] = validate(receipt['answer'],reject)
            except ValueError as exc:
                failures[arm] = str(exc)
        probe.freeze(OUT/'private/PROPOSALS.json',dict(systems=systems,validation=failures))
        new_targets, jobs, cached_answers = {}, {}, {}
        archived_attempts = {}
        for row in prior.values():
            if row.get('actor_request_sha256'):
                digest = row['actor_request_sha256']
                if digest in archived_attempts and archived_attempts[digest]['answer'] != row['answer']:
                    raise ValueError('Conflicting first-round archive')
                archived_attempts[digest] = row
                if row['actor_status'] == 'OK':
                    cached_answers[digest] = row['answer']
        for c in cards:
            uid = c['uid']
            for route in MODES:
                for arm in ARMS:
                    key = uid,route+'/'+arm
                    target = dict(uid=uid,method=key[1],benchmark=c['domain'],stratum=c['stratum'],
                                  sources=c['payload']['source_evidence'],score=None,answer=None,
                                  actor_status=failures.get(arm),score_flags=None)
                    new_targets[key] = target
                    if arm not in systems:
                        continue
                    request = deepcopy(up[uid,route])
                    request['messages'][0]['content'] = systems[arm]
                    earlier = archived_attempts.get(sha(request))
                    if earlier and earlier['actor_status'] != 'OK':
                        target['actor_status'] = earlier['actor_status']
                        continue
                    jobs[key] = request
        for key, receipt in stage('Actor',jobs,cached_answers).items():
            row = new_targets[key]
            row.update(actor_status=receipt['status'],answer=receipt.get('answer'),
                       actor_request_sha256=receipt['request_sha256'])
            earlier = archived_attempts.get(receipt['request_sha256'])
            if earlier and earlier['answer'] == row['answer']:
                row.update(score=earlier['score'],score_flags=earlier.get('score_flags'), reused_grade=True)
        rows = list(new_targets.values())
        grading([row for row in rows if not row.get('reused_grade')],stage)
        rows.extend(v for k,v in prior.items() if k[1].endswith('/SEED'))
        probe.freeze(OUT/'RESULTS.json',dict(rows=rows,ledger=ledger))
        print(json.dumps(summarize(cards,rows,base,ledger),indent=2),flush=True)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','run','report'))
    args = parser.parse_args()
    inputs = prepare()
    path = OUT/'private/FROZEN.json'
    if args.action == 'freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,inputs[0])
        print(dict(assigned=len(inputs[1]),feedback_groups=inputs[0]['feedback_groups']))
    elif read(path) != inputs[0]:
        raise ValueError('Frozen refinement inputs changed')
    elif args.action == 'run':
        run(*inputs)
    else:
        print(json.dumps(score(inputs[1],read(OUT/'RESULTS.json'),inputs[3]),indent=2))
