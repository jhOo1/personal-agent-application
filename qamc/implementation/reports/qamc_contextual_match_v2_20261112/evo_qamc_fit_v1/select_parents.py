"""Select shared algorithm parents from a settled, common-task development summary."""
from argparse import ArgumentParser
from pathlib import Path
import json

DOMAINS = ('RPEval','BenchPreS','PersistBench')
PROTECTIONS = ('rpe_less_opb','rpe_less_upb','rpe_less_fm',
               'bench_appropriate','bench_less_misuse','bench_completeness',
               'persist_utility','persist_less_cross_domain','persist_less_sycophancy')


def objective_row(summary, name):
    scores = summary['scores']
    rpe = scores['RPEval']['paired_native'][name]
    bench = scores['BenchPreS']['paired_native'][name]
    parts = summary['search_macro']['parts'][name]
    values = {domain:parts[domain] for domain in DOMAINS}
    values.update(rpe_less_opb=-rpe['OPB'],rpe_less_upb=-rpe['UPB'],rpe_less_fm=-rpe['FM'],
                  bench_appropriate=bench['primary'],bench_less_misuse=-bench['MR'],
                  bench_completeness=bench['completeness'])
    for key,field in (('beneficial_memory_usage','persist_utility'),
                      ('cross_domain','persist_less_cross_domain'),
                      ('sycophancy','persist_less_sycophancy')):
        track = scores['PersistBench/'+key]['paired_native'][name]
        values[field] = track['primary']
    return values


def dominates(a,b):
    return all(a[k]>=b[k] for k in a) and any(a[k]>b[k] for k in a)


def select(summary):
    macro = summary['search_macro']['common_macro']
    policies = sorted(set(macro)-{'BASE'})
    if len(policies)<2:
        raise ValueError('No complete common support for comparing shared policies')
    objectives = {name:objective_row(summary,name) for name in policies}
    dominated = {name:[other for other in policies if dominates(objectives[other],objectives[name])]
                 for name in policies}
    parents = sorted((name for name in policies if not dominated[name]),
                     key=lambda name:(-macro[name],name))
    leaders = {k:max(parents,key=lambda name:(objectives[name][k],macro[name])) for k in (*DOMAINS,*PROTECTIONS)}
    return dict(common={k:summary['scores'][k]['common'] for k in DOMAINS},
                common_macro={name:macro[name] for name in policies},
                frontier=parents, best_balanced_parent=parents[0],
                best_by_objective=leaders, dominated_by={name:items for name,items in dominated.items() if items},
                objectives=objectives)


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('summary',type=Path)
    args=cli.parse_args()
    print(json.dumps(select(json.loads(args.summary.read_text())),indent=2))
