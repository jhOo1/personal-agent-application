"""Replay common fixed policies on all exposed complete rows, grouped by benchmark."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
matrix = json.loads((here.parent / 'paired_regret_policy_v1/MATRIX.json').read_text())
assert matrix['exposed_only']
result = {}
for row in matrix['rows']:
    options = dict(row['metrics'])
    if any(options[k] is None for k in ('T', 'H', 'G')):
        continue
    options['IPE-C'] = options[row['keep']]
    options['specialist'] = {
        'RPEval': options['IPE-C'],
        'BenchPreS': options['G'],
        'PersistBench': row.get('ref_metrics'),
    }[row['domain']]
    if options['specialist'] is None:
        continue
    table = result.setdefault(row['domain'], {'tasks': 0, 'positions': 0, 'primary': {}})
    table['tasks'] += 1
    table['positions'] += row['denom']
    for method, grade in options.items():
        table['primary'][method] = table['primary'].get(method, 0) + grade['primary']
print(json.dumps(result, indent=2))
