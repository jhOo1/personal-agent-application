"""Identity-only grouped manifests; selection never reads evaluation labels."""
import json
from collections import defaultdict
from qamc.common import ROOT, sha
from qamc.bace.audit import write_new, digest
from .audit import OUT


def balanced(rows, group, count):
    pools = defaultdict(list)
    for row in rows: pools[row[group]].append(row)
    for values in pools.values(): values.sort(key=lambda x: sha(['bace-v2-v1', x['uid']]))
    result = []
    while len(result) < count and any(pools.values()):
        for key in sorted(pools):
            if pools[key]: result.append(pools[key].pop(0))
            if len(result) == count: break
    return result


def build(old):
    bench_select_roots = sorted({r['profile_root'] for r in old['benchpres'] if r['split']=='select'})
    select_roots = set(bench_select_roots[:len(bench_select_roots)//2])
    contexts = sorted({r['context_root'] for r in old['benchpres']}, key=lambda c: sha(['bace-v2-context',c]))
    context_phase = {c: ('opt' if i < 10 else 'select' if i < 30 else 'confirm') for i,c in enumerate(contexts)}
    rows = []
    for benchmark in ('benchpres','prefeval'):
        for original in old[benchmark]:
            r = dict(original); r['benchmark'] = benchmark
            if benchmark == 'benchpres':
                r['root'] = r['profile_root']
                split = 'opt' if r['split']=='cal' else 'select' if r['root'] in select_roots else 'confirm'
                if context_phase[r['context_root']] != split: continue
                r['confirmation_claim'] = 'internal held-out profiles for v2; profiles previously exposed, not unseen-user SOTA'
            else:
                r['root'] = r['root_group']
                split = {'cal':'opt','select':'select','test':'confirm'}[r['split']]
                r['confirmation_claim'] = 'internal grouped holdout; exact exposure audit is not proof of no semantic exposure'
            r['v2_split'] = split; rows.append(r)
    chosen = {}
    for phase, count in [('opt',24),('select',50)]:
        chosen[phase] = []
        for benchmark in ('benchpres','prefeval'):
            eligible=[r for r in rows if r['benchmark']==benchmark and r['v2_split']==phase]
            chosen[phase] += balanced(eligible,'root' if benchmark=='benchpres' else 'topic',count)
    chosen['confirm'] = [r for r in rows if r['v2_split']=='confirm']
    # Forms are bound to the same base identity; smoke is a declared dev subset.
    for phase, cases in chosen.items():
        index = 0
        for row in cases:
            if row['benchmark']=='prefeval':
                row['history_form'] = ['explicit','persona-driven','choice-based'][index % 3]; index += 1
            else: row['history_form'] = 'official_profile'
    chosen['smoke'] = []
    for b in ('benchpres','prefeval'):
        chosen['smoke'] += [r for r in chosen['opt'] if r['benchmark']==b][:4]
    root_sets={phase:{(r['benchmark'],r['root']) for r in chosen[phase]} for phase in ('opt','select','confirm')}
    for a,b in [('opt','select'),('opt','confirm'),('select','confirm')]:
        if root_sets[a]&root_sets[b]: raise ValueError('Root leakage across v2 splits')
    return {'version':'v2-identities-v2','selection_uses_gold':False,'smoke_is_development_subset':True,
            'phases':chosen,'prior_source_manifest_preserved':True,
            'confirm_content_loaded_for_development':False,
            'limitations':['BenchPreS all profiles historically exposed; internal holdout only.',
                          'BenchPreS exact context roots also separated: 10 opt / 20 select / 9 confirm; broad domains may overlap.',
                          'Variant forms and lengths of each PrefEval pair inherit its root split.']}


def main():
    source = ROOT/'reports/qamc_bace_20261105/SPLITS_MANIFEST_V3.json'
    result = build(json.loads(source.read_text())); result['parent_manifest_sha256']=digest(source)
    path=OUT/'DATA_MANIFEST_V2.json'
    if path.exists():
        if json.loads(path.read_text()) != result: raise ValueError('Frozen manifest drift')
    else: write_new(path,result)
    print(json.dumps({p:len(rows) for p,rows in result['phases'].items()}))


if __name__ == '__main__': main()
