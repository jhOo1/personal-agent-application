"""Cross task-only plans with Self-ReCheck source exposure on the same final Actor."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from trial import ACTOR, RUN, engine, grading, probe, sha, wire

OUT = RUN.with_name(RUN.name+'_crossover')
TASK = RUN.with_name(RUN.name+'_task_only')
SELECTED = RUN.with_name(RUN.name+'_self_recheck')
METHOD = 'TASK_PLAN_SELECTED'


def read(path):
    return json.loads(path.read_text())


def actors(run):
    result = {}
    for path in (run/'Actor/visible').glob('*/record.json'):
        record = read(path)
        request = read(path.with_name('request.json'))
        uid = record['unit']['root_id']
        assert uid not in result and sha(request)==record['request_sha256']
        assert record['status']!='PENDING_DELIVERY_UNKNOWN'
        result[uid] = request, record
    return result


def prepare():
    frozen = read(RUN/'private/FROZEN.json')
    task_results = read(TASK/'RESULTS.json')
    selection_results = read(SELECTED/'RESULTS.json')
    task_outputs = {r['uid']:r for r in task_results['rows']}
    selected = {r['uid']:r for r in selection_results['rows']}
    task_wires, selection_wires = actors(TASK), actors(SELECTED)
    jobs, templates, cached = {}, {}, {}
    for row in frozen['rows']:
        uid = row['uid']
        key = (uid,METHOD)
        previous = task_outputs[uid]
        selection = selected[uid]
        template = dict(uid=uid,method=METHOD,benchmark=row['domain'],stratum=row['stratum'],
                        group=row['group'],sources=row['payload']['source_evidence'],
                        actor_status='NOT_DISPATCHED',answer=None,score=None)
        templates[key] = template
        if uid not in task_wires or uid not in selection_wires:
            template['reason'] = 'REQUIRED_PARENT_REQUEST_UNAVAILABLE'
            continue
        task_request, receipt = task_wires[uid]
        task = json.loads(task_request['messages'][1]['content'])
        memory = json.loads(selection_wires[uid][0]['messages'][1]['content'])
        assert task['task']==memory['task']==row['payload']['task']
        assert task['source_evidence']==row['payload']['source_evidence']
        raw = task['source_evidence']
        kept = memory['source_evidence']
        kept_ids = {r['memory_id'] for r in kept}
        assert kept==[item for item in raw if item['memory_id'] in kept_ids]
        assert len(kept)==selection['selected_count']
        request = wire(ACTOR, {**task,'source_evidence':kept},8192)
        template.update(full_sources=len(raw),selected_sources=len(kept))
        if request==task_request:
            assert previous['actor_status']==receipt['status']
            retained = {k:previous.get(k) for k in ('actor_status','answer','score','score_flags')}
            cached[key] = {**retained,'origin':'EXACT_TASK_ONLY','request_hash':sha(request)}
        else:
            jobs[key] = request
    pin = dict(panel=sha(frozen),task_parent=sha(task_results),selection_parent=sha(selection_results),
               code=sha(Path(__file__).read_bytes()), service_reference_sha256=probe.read_reference()[1],
               incoming=sha([[*k,sha(v)] for k,v in jobs.items()]),
               exact_actor_reuse=len(cached), new_actors=len(jobs), assigned=len(templates))
    return pin, jobs, templates, cached


def measure(pin,jobs,templates,cached):
    probe.RUN,probe.OUT,engine.OUT = OUT,OUT/'private',OUT/'private'
    engine.CAP = {'Actor':40,engine.RPE:16,'BenchAttrs':72,'PersistNative':12}
    identity = {'experiment_sha256':sha(pin),'service_reference_sha256':pin['service_reference_sha256']}
    ledger = []
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name,batch,cache=None):
            return engine.stage(name,batch,identity,True,ledger,cache) if batch else {}

        for key,receipt in stage('Actor',jobs).items():
            row = templates[key]
            row.update(actor_status=receipt['status'],answer=receipt.get('answer'),origin=receipt['origin'],
                       request_hash=receipt['request_sha256'])
        grading([templates[key] for key in jobs],stage)
        for key,data in cached.items():
            templates[key].update(data)
        probe.freeze(OUT/'RESULTS.json',dict(rows=list(templates.values()),ledger=ledger))
        print(Counter((r['unit']['stage'],r['status']) for r in ledger),flush=True)


if __name__ == '__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','check','run'))
    args = cli.parse_args()
    comparison = prepare()
    path = OUT/'private/FROZEN.json'
    if args.action=='freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,comparison[0])
    else:
        assert read(path)==comparison[0]
        if args.action=='run':
            measure(*comparison)
    print(comparison[0],flush=True)
