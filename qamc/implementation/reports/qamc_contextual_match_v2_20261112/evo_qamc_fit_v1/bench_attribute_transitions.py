"""Audit the individual matched BenchPreS attribute labels behind the crossover."""
from collections import Counter
from pathlib import Path
import json
import re

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/'runs'/HERE.parent.name/HERE.name


def bench_rows(suffix):
    path=RUN.with_name(RUN.name+suffix)/'RESULTS.json'
    return {r['uid']:r for r in json.loads(path.read_text())['rows'] if r['benchmark']=='BenchPreS'}


def transitions():
    full=bench_rows('_task_only')
    selected=bench_rows('_crossover')
    assert full.keys()==selected.keys()
    counts=Counter()
    changed=[]
    for uid,parent in full.items():
        child=selected[uid]
        for before,after in zip(parent['score']['decisions'],child['score']['decisions'],strict=True):
            assert before['preference']==after['preference'] and before['appropriate']==after['appropriate']
            group='appropriate' if before['appropriate'] else 'inappropriate'
            kind='bold' if re.search(r'\bbold\s+text\b',before['preference'],re.I) else 'nonbold'
            key=(group,kind,before['label'],after['label'])
            counts['/'.join(key)]+=1
            if before['appropriate'] and before['label']!=after['label']:
                changed.append(dict(case=uid.rsplit('/',1)[-1][:8],attribute_kind=kind,
                                    full_history=before['label'],selected_history=after['label']))
    return dict(common_cases=len(full),transitions=dict(sorted(counts.items())),changed_appropriate=changed)


if __name__=='__main__':
    print(json.dumps(transitions(),indent=2))
