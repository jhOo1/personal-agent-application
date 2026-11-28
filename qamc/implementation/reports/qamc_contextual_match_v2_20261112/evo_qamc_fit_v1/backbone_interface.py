"""Run a frozen three-benchmark model, interface and history crossover."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

from backbone_interface_inputs import ARMS, MODELS, INTERFACES, assemble, select, variants
from joint_context import RUN, engine, grading, metrics, probe, read, sha
from qamc.contextual_match.cache import service_filtered
from qamc.contextual_match.cache_inventory import inventory
from qamc.contextual_match.lossless_transport import filter_compatible_cache

OUT = RUN.with_name(RUN.name+'_backbone_interface_v1')


def recover(roster, jobs, service):
    fixed, scores = {}, {}
    for item in roster:
        uid = item['card']['uid']
        for old, arm in (('PLAN','Q/PLAN/SELECTED'),('DIRECT','Q/DIRECT/SELECTED'),
                         ('OFF_PLAN','Q/PLAN/OFF')):
            row = item['archive'].get(old)
            if row is None or row['actor_status'] != 'OK':
                continue
            digest = sha(jobs[uid,arm])
            if row.get('actor_request_sha256',digest) != digest:
                raise ValueError('Named archive wire mismatch')
            if digest in fixed and fixed[digest] != row['answer']:
                raise ValueError('Named known actor receipts conflict')
            fixed[digest] = row['answer']
            scores[uid,sha(row['answer'])] = row

    wanted = {sha(req) for req in jobs.values()} - fixed.keys()
    root = Path.cwd()
    history = inventory(root,wanted)
    history['records'] = [row for row in history['records']
                          if OUT.name not in Path(row['origin']).parts]
    history = filter_compatible_cache(root,service_filtered(root,history,wanted,service))
    attempts, possible = set(), defaultdict(set)
    for row in history['records']:
        digest = row['body_sha256']
        attempts.add(digest)
        if row['status'] == 'ok' and row['response_path']:
            answer = read(root/row['response_path']).get('answer')
            if isinstance(answer,str) and answer:
                possible[digest].add(answer)
    for digest, answers in possible.items():
        if len(answers) == 1:
            fixed[digest] = next(iter(answers))
    blocked = {digest:'AMBIGUOUS_PRIOR_ANSWER' if possible[digest] else 'PRIOR_FAILED_OR_UNVERIFIED'
               for digest in attempts - fixed.keys()}
    return fixed,scores,blocked


def prepare():
    batches,_,service = assemble()
    roster = select(batches)
    jobs = {(item['card']['uid'],arm):req for item in roster
            for arm,req in variants(item).items()}
    cache,scores,blocked = recover(roster,jobs,service)
    pin = dict(code=sha(Path(__file__).read_bytes()),
               construction=sha(Path(__file__).with_name('backbone_interface_inputs.py').read_bytes()),
               service_reference_sha256=service,
               schedule=[[uid,arm,sha(req)] for (uid,arm),req in jobs.items()],
               fixed_answer_hashes={digest:sha(answer) for digest,answer in cache.items()},
               need_no_dispatch=blocked,
               reference_grades=sha([[item['card']['uid'],item['card']['base_score']]
                                      for item in roster]))
    return pin,roster,jobs,cache,scores,blocked


def summarize(roster, rows, ledger):
    indexed = {(r['uid'],r['method']):r for r in rows}
    sections = defaultdict(lambda:dict(assigned=0, common=0, unflagged=0, available=Counter(),
                                       aggregates=defaultdict(Counter), clean=defaultdict(Counter),
                                       statuses=Counter()))
    for item in roster:
        card = item['card']
        uid,domain,stratum = (card[k] for k in ('uid','domain','stratum'))
        rows_for_task = {arm:indexed[uid,arm] for arm in ARMS}
        measures = {arm:metrics(card,row['score']) for arm,row in rows_for_task.items()}
        measures['BASE'] = metrics(card,card['base_score'])
        common = all(x is not None for x in measures.values())
        clean = common and domain == 'RPEval' and card['base_flags'] == [] and all(
            row.get('score_flags') == [] for row in rows_for_task.values())
        keys = (domain,domain+'/'+stratum,domain+'/source_role/'+item['source_role'])
        for key in keys:
            row = sections[key]
            row['assigned'] += 1
            row['available'].update(arm for arm,v in measures.items() if v is not None)
            row['statuses'].update(arm+'/'+r['actor_status'] for arm,r in rows_for_task.items())
            if not common:
                continue
            if len({(c['positions'],c.get('MR_denominator')) for c in measures.values()}) != 1:
                raise ValueError('Same-task supported positions do not match across arms')
            row['common'] += 1
            for arm, value in measures.items():
                row['aggregates'][arm].update(value)
            if clean:
                row['unflagged'] += 1
                for arm,value in measures.items():
                    row['clean'][arm].update(value)
    return dict(sections=sections,dispatches=Counter(r['unit']['stage'] for r in ledger),
                transport=Counter(r['status'] for r in ledger),
                tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger),
                unknown_usage=sum('total_tokens' not in (r.get('usage') or {}) for r in ledger))


def run(pin,roster,jobs,cache,archive,blocked):
    probe.RUN,probe.OUT,engine.OUT = OUT,OUT/'private',OUT/'private'
    engine.CAP = {'QActor':72,'DActor':72,engine.RPE:64,'BenchAttrs':192,'PersistNative':48}
    identity = dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    ledger = []
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name, wires, cached=None):
            return engine.stage(name,wires,identity,True,ledger,cached) if wires else {}

        received = {}
        for model_key in MODELS:
            wires = {key:req for key,req in jobs.items()
                     if key[1].startswith(model_key+'/') and sha(req) not in blocked}
            received.update(stage(model_key+'Actor',wires,cache))
        rows = []
        skip = set()
        for item in roster:
            c = item['card']
            uid = c['uid']
            for arm in ARMS:
                key = uid,arm
                receipt = received.get(key)
                digest = sha(jobs[key])
                row = dict(uid=uid,method=arm,benchmark=c['domain'],stratum=c['stratum'],
                           sources=c['payload']['source_evidence'],
                           actor_request_sha256=digest,score=None,answer=None,score_flags=None)
                if receipt:
                    row.update(actor_status=receipt['status'],answer=receipt.get('answer'))
                    if receipt['status'] == 'OK':
                        old = archive.get((uid,sha(row['answer'])))
                        if old and old.get('score') is not None:
                            row.update(score=old['score'],score_flags=old.get('score_flags'))
                            skip.add(key)
                else:
                    row['actor_status'] = blocked[digest]
                rows.append(row)
        grading([row for row in rows if (row['uid'],row['method']) not in skip],stage)
        probe.freeze(OUT/'RESULTS.json',dict(rows=rows,ledger=ledger))
    print(json.dumps(summarize(roster,rows,ledger),indent=2),flush=True)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','run','report'))
    args = parser.parse_args()
    inputs = prepare()
    pin,roster,jobs,cache,_,blocked = inputs
    path = OUT/'private/FROZEN.json'
    if args.action == 'freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,pin)
        print(json.dumps(dict(assigned=len(roster),logical_wires=len(jobs),archived=len(cache),
                              blocked=len(blocked),
                              max_new_unique_wires=len({sha(w) for w in jobs.values()}-
                                                       cache.keys()-blocked.keys())),indent=2))
    elif read(path) != pin:
        raise ValueError('Crossover manifest drift')
    elif args.action == 'run':
        run(*inputs)
    else:
        out = read(OUT/'RESULTS.json')
        print(json.dumps(summarize(roster,out['rows'],out['ledger']),indent=2))
