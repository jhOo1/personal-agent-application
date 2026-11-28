"""Reuse the exact two planning policies with history selected before both model calls."""
from argparse import ArgumentParser
from pathlib import Path
from collections import Counter
import json

import trial
from trial import COMMON, HERE, POLICIES, RUN, probe, sha, wire

OUT = RUN.with_name(RUN.name+'_selected_planning')
SELECTED = RUN.with_name(RUN.name+'_self_recheck')


def read(path):
    return json.loads(path.read_text())


def prepare():
    base = read(RUN/'private/FROZEN.json')
    upstream = read(SELECTED/'private/Actor_MANIFEST.json')
    selected = {}
    for unit in upstream['units']:
        uid = unit['unit']['root_id']
        assert uid not in selected
        selected[uid] = json.loads(unit['request']['messages'][1]['content'])
    rows, exact, absent = [], [], []
    for case in base['rows']:
        uid = case['uid']
        card = {k:case[k] for k in ('uid','domain','stratum','group')}
        if uid not in selected:
            absent.append(card)
            continue
        payload = selected[uid]
        original = case['payload']
        assert payload['task']==original['task'] and set(payload)==set(original)
        ids = {s['memory_id'] for s in payload['source_evidence']}
        assert payload['source_evidence']==[s for s in original['source_evidence'] if s['memory_id'] in ids]
        if payload==original:
            exact.append(card)
            continue
        requests = {name:sha(wire(COMMON+'\n\n'+prompt,payload,4096)) for name,prompt in POLICIES.items()}
        rows.append({**card,'payload':payload,'plan_request_hashes':requests,
                     'evaluation_sources':original['source_evidence']})
    return dict(rows=rows,exact=exact,absent=absent,input_sha256=sha(base),selected_sha256=sha(upstream),
                code_hash=sha(Path(__file__).read_bytes()),seeds_code_hash=sha((HERE/'trial.py').read_bytes()),
                service_reference_sha256=probe.read_reference()[1])


def measure(plan):
    # The original scorer requires all source slots, even when inference saw a strict subset.
    old_grading = trial.grading

    def grade_all_sources(rows,stage):
        originals = {r['uid']:r['evaluation_sources'] for r in plan['rows']}
        for row in rows:
            row['sources'] = originals[row['uid']]
        old_grading(rows,stage)

    trial.RUN = OUT
    trial.grading = grade_all_sources
    trial.run(plan)
    freshly_scored = read(OUT/'RESULTS.json')
    base = read(RUN/'RESULTS.json')
    index = {(r['uid'],r['method']):r for r in base['rows']}
    rows = freshly_scored['rows']
    for card in plan['exact']:
        for method in POLICIES:
            rows.append({**index[card['uid'],method],'result_origin':'EXACT_FULL_HISTORY_SEED'})
    for card in plan['absent']:
        for method in POLICIES:
            rows.append(dict(uid=card['uid'],method=method,benchmark=card['domain'],group=card['group'],
                             stratum=card['stratum'],score=None,actor_status='SELECTION_UNAVAILABLE'))
    for row in rows:
        row['method'] = 'SELECTED_'+row['method']
    assert len(rows)==2*sum(len(plan[k]) for k in ('rows','exact','absent'))
    probe.freeze(OUT/'COMBINED.json',freshly_scored)


if __name__=='__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','check','run'))
    args=cli.parse_args()
    prepared=prepare()
    pin=OUT/'private/FROZEN.json'
    print(Counter(r['domain'] for r in prepared['rows']),
          'exact',len(prepared['exact']),'absent',len(prepared['absent']),flush=True)
    if args.action=='freeze':
        pin.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(pin,prepared)
    else:
        assert read(pin)==prepared
        if args.action=='run':
            measure(prepared)
