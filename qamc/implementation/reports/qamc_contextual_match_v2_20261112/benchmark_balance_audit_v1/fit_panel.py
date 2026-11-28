"""Freeze an exposed, intentionally score-enriched development panel, never an evaluation set."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

here = Path(__file__).resolve().parent
matrix = json.loads((here.parent/'paired_regret_policy_v1/MATRIX.json').read_text())
assert matrix['exposed_only']
quotas = {'RPEval': {'contains_C': 5, 'all_A': 5, 'B_only': 6},
          'BenchPreS': {'communication': 12},
          'PersistBench': {'sycophancy': 4, 'cross_domain': 4, 'beneficial_memory_usage': 4}}
private = here.parents[2]/'runs'/here.parent.name/here.name/'private'
private.mkdir(parents=True, exist_ok=True)
selected, totals = [], {}
for domain, strata in quotas.items():
    group_counts = Counter()
    for stratum, quota in strata.items():
        pool = []
        for r in matrix['rows']:
            if r['domain'] != domain or r['stratum'] != stratum:
                continue
            ref = r['ref_metrics'] if domain == 'PersistBench' else r['metrics'][r['keep'] if domain == 'RPEval' else 'G']
            if ref is None or r['denom'] <= 0:
                continue
            pool.append((r, ref['primary'] < r['denom']))
        counts = Counter()
        for i in range(quota):
            # Half the slots prioritize visible specialist misses; retain successful tasks too.
            prefer_miss = i < (quota+1)//2
            r, miss = min(pool, key=lambda x: (x[1] != prefer_miss, group_counts[x[0]['group']],
                sha256(('qamc-fit-panel-v1/'+x[0]['uid']).encode()).hexdigest()))
            pool.remove((r,miss))
            selected.append({k:r[k] for k in ('uid','domain','stratum','group')})
            group_counts[r['group']] += 1
            counts['baseline_has_headroom' if miss else 'baseline_at_primary_max'] += 1
        totals[domain+'/'+stratum] = dict(counts)
    totals[domain+'/distinct_groups'] = len(group_counts)
assert len(set(r['uid'] for r in selected)) == len(selected) == 40
blob = json.dumps(selected, sort_keys=True, indent=2).encode()
path=private/'FIT_PANEL.json'
if path.exists():
    assert path.read_bytes()==blob
else:
    path.write_bytes(blob)
print(json.dumps(dict(fit_only=True, tasks=40, manifest_sha256=sha256(blob).hexdigest(), strata=totals), indent=2))
