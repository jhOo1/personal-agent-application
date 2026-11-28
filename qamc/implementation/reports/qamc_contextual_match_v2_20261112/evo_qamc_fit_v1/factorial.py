"""Estimate planned effects from the four exposure-by-planning cells."""
from collections import Counter, defaultdict
import json

from paired_macro import DOMAINS, contributions
from summarize import metrics
from summarize_reassembly import aligned
from trial import RUN

SELECTED = RUN.with_name(RUN.name+'_selected_planning')
CELLS = ('GENERIC','TASK_ACTIONS','SELECTED_GENERIC','SELECTED_TASK_ACTIONS')
EFFECTS = {
    'actions_on_full_history': {'GENERIC':-1,'TASK_ACTIONS':1},
    'actions_on_selected_history': {'SELECTED_GENERIC':-1,'SELECTED_TASK_ACTIONS':1},
    'selection_on_generic': {'GENERIC':-1,'SELECTED_GENERIC':1},
    'selection_on_actions': {'TASK_ACTIONS':-1,'SELECTED_TASK_ACTIONS':1},
    'interaction': {'GENERIC':1,'TASK_ACTIONS':-1,'SELECTED_GENERIC':-1,'SELECTED_TASK_ACTIONS':1},
}


def read(path):
    return json.loads(path.read_text())


def effects(domain, rows):
    assigned = {name:[0.0,0.0] for name in EFFECTS}
    defined = False
    for slots, cap, score in contributions(domain,rows):
        defined = True
        for name, coefficients in EFFECTS.items():
            low, high = assigned[name]
            for arm, sign in coefficients.items():
                grade = slots[arm]
                if grade is None:
                    low += min(0,sign*cap)
                    high += max(0,sign*cap)
                else:
                    value = sign*score(grade)
                    low += value
                    high += value
            assigned[name] = [low,high]
    return assigned if defined else {name:None for name in EFFECTS}


def collect(panel, outcomes):
    scores = {(x['uid'],x['method']):x['score'] for x in outcomes}
    assert len(scores)==len(panel)*len(CELLS)==len(outcomes)
    groups = defaultdict(list)
    for card in panel:
        uid = card['uid']
        values = {arm:metrics(card,scores[uid,arm]) for arm in CELLS}
        values['BASE'] = metrics(card,card['base_score'])
        assert values['BASE'] is not None
        for arm in CELLS:
            if values[arm] is not None:
                assert aligned(values,('BASE',arm))
        groups[card['domain']].append((card,None,values))
    return groups


def analyze(groups):
    domains = {}
    for domain in DOMAINS:
        rows = groups[domain]
        common = [r for r in rows if aligned(r[2],('BASE',*CELLS))]
        counts = Counter()
        for card,_,_ in common:
            counts[card['stratum']]+=1
        native = {arm:Counter() for arm in CELLS}
        for _,_,values in common:
            for arm in CELLS:
                native[arm].update(values[arm])
        domains[domain] = dict(assigned_tasks=len(rows),common_tasks=len(common),common_strata=counts,
            availability={a:sum(v[a] is not None for _,_,v in rows) for a in CELLS},
            common_native=native,common_effects=effects(domain,common),assigned_bounds=effects(domain,rows))
    macro = {}
    for name in EFFECTS:
        item = {}
        for key in ('common_effects','assigned_bounds'):
            values = [domains[d][key][name] for d in DOMAINS]
            item[key] = ([sum(v[i] for v in values)/3 for i in (0,1)] if all(v is not None for v in values) else None)
        macro[name] = item
    return dict(domains=domains,macro=macro)


if __name__=='__main__':
    cards = read(RUN/'private/FROZEN.json')['rows']
    original = read(RUN/'RESULTS.json')['rows']
    filtered = read(SELECTED/'COMBINED.json')['rows']
    print(json.dumps(analyze(collect(cards,[*original,*filtered])),indent=2))
