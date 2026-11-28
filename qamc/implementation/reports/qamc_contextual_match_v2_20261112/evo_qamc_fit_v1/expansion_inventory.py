"""Qualify existing exposed tasks for a larger same-protocol joint evaluation."""
from collections import Counter, defaultdict
import json

from baselines import rpe, transfer
from trial import HERE, PANEL, sha


def read(path):
    return json.loads(path.read_text())


def main():
    matrix = read(HERE.parent/'paired_regret_policy_v1/MATRIX.json')
    assert matrix['exposed_only']
    fitted = read(PANEL)
    fitted_ids = {r['uid'] for r in fitted}
    fitted_groups = {(r['domain'],r['group']) for r in fitted}
    banks = {'RPEval':rpe(),'BenchPreS':transfer('BenchPreS'),'PersistBench':transfer('PersistBench')}
    totals = defaultdict(Counter)
    groups = defaultdict(set)
    eligible = []
    for row in matrix['rows']:
        domain, uid, group, stratum = (row[k] for k in ('domain','uid','group','stratum'))
        matrix_metrics = row['metrics']
        specialist = row.get('ref_metrics') if domain=='PersistBench' else matrix_metrics[
            row['keep'] if domain=='RPEval' else 'G']
        if any(matrix_metrics[k] is None for k in ('T','H','G')) or specialist is None:
            continue
        c = banks[domain].get(uid)
        if c is not None:
            assert c['group']==group and c['stratum']==stratum
        if uid in fitted_ids:
            state = 'fit_task_in_matrix'
        elif (domain,group) in fitted_groups:
            state = 'fit_group_other_task'
        elif c is None:
            state = 'no_verified_exact_specialist_card'
        else:
            state = 'source_disjoint_candidate'
            eligible.append(dict(domain=domain,uid=uid,group=group,stratum=stratum,
                                 base_answer_sha256=c['baseline_answer_sha256']))
        for k in (domain,domain+'/'+stratum):
            totals[k].update(common_archive=1,**{state:1})
            if state=='source_disjoint_candidate':
                groups[k].add(group)
    assert sum(totals[k]['common_archive'] for k in banks)==296
    print(json.dumps(dict(observed_development_only=True,fit_tasks=len(fitted),
                          source_disjoint_qualified=len(eligible),
                          candidate_audit_sha256=sha(sorted(eligible,key=lambda r:r['uid'])),
                          strata={k:{**v,'qualified_source_groups':len(groups[k])}
                                  for k,v in sorted(totals.items())}),indent=2))


if __name__=='__main__':
    main()
