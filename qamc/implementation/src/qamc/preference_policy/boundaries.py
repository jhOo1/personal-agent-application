"""Natural query contrasts from D_opt only; no manufactured user histories.

Availability is not validity. Applicability labels here are source-grounded Qwen
predictions and must remain separate from official labels and human reviews.
"""
import itertools,re
from qamc.common import sha
from .core import fields,short

PROMPT='''Examine two actual development requests from the same previously exposed user and the SAME quoted historical source. No answer, score or gold label is supplied. Does this source contain a genuine user preference whose legitimate use clearly differs between these two contexts?
Related source context contains same-attribute frozen Profile navigation and original sources, not new retrieval or verified truth. Check subject, qualifiers and explicit updates; an active past event is not automatically an ongoing state. Context is not the full history. If missing context could materially change applicability, use UNCERTAIN.
Return only {"source_is_preference":true,"role_A":"HELPFUL|NOT_APPLICABLE|UNCERTAIN","role_B":"HELPFUL|NOT_APPLICABLE|UNCERTAIN","reason":"short source-grounded explanation"}.
HELPFUL means it may improve this task, not necessarily be mentioned or win. NOT_APPLICABLE means applying it would introduce an irrelevant or wrong-scope influence. Do not force different labels. A different domain, recency or title alone does not prove a boundary. An assistant suggestion or user belief is not automatically an endorsed preference. If the two tasks both reasonably benefit, give HELPFUL for both. No new query, rewritten history or recommended answer. These are automatic diagnostics, not unit gold truth.'''


def natural_pairs(experiences):
    """At most two real shared preferences per request pair, four probes total.

    Input-only relevance and existing state navigation order the probes; no label,
    answer or forced negative history is used to construct a contrast.
    """
    result=[]
    for left,right in itertools.combinations(experiences,2):
        if left['persona_group']!=right['persona_group']:continue
        def by_version(experience):
            groups={}
            for unit in experience['input']['units']:
                if unit['carrier'] in {'user','system'}:groups.setdefault(unit['memory_version'],[]).append(unit)
            return groups
        a,b=by_version(left),by_version(right)
        # Prefer sources explicitly navigated by the frozen preference profile;
        # that old Writer metadata is a prediction, not a correctness label.
        shared=set(a)&set(b)&set(left['preference_source_versions'])&set(right['preference_source_versions'])
        if not shared:continue
        def context(experience,units):
            source_ids={u.get('source_id')for u in units};p=experience['input']
            facets=[f for f in p.get('profile_navigation',[])if set(f['source_ids'])&source_ids]
            attributes={f['attribute']for f in facets}
            related=[f for f in p.get('profile_navigation',[])if f['attribute']in attributes]
            refs={s for f in related for s in f['source_ids']}
            return {'current_context':p.get('current_context',[]),'query_time':p.get('query_time'),
                    'profile_navigation':related,'related_raw_units':[u for u in p['units']if u.get('source_id')in refs],
                    'source_metadata':{s:m for s,m in p.get('source_metadata',{}).items()if s in refs},
                    'coverage':'Shared preference and same-attribute frozen-R context, not complete history.'},facets
        def terms(text):return set(re.findall(r'\b[a-z]{4,}\b',text.lower()))
        qa=terms(left['input']['query'].split('\n\nChoose the best option')[0]);qb=terms(right['input']['query'].split('\n\nChoose the best option')[0])
        ranked=[]
        for version in shared:
            ca,fa=context(left,a[version]);cb,fb=context(right,b[version]);t=terms(' '.join(u['exact_text']for u in a[version]))
            x,y=len(qa&t),len(qb&t);active=all(any(f.get('stored_pool')=='active'for f in fs)for fs in [fa,fb])
            ranked.append((-int(active),-abs(x-y),-max(x,y),version,ca,cb))
        for _,_,_,version,ca,cb in sorted(ranked)[:2]:
            result.append({'pair_id':sha([left['experience_id'],right['experience_id'],version])[:24],
                'member_ids':[left['experience_id'],right['experience_id']],
                'input':{'query_A':left['input']['query'],'query_B':right['input']['query'],
                    'source':{'memory_version':version,'carrier':a[version][0]['carrier'],
                              'original_units_A':a[version],'original_units_B':b[version]},
                    'context_A':ca,'context_B':cb}})
    return result[:4]


def validate(obj):
    fields(obj,'source_is_preference role_A role_B reason')
    if type(obj['source_is_preference'])is not bool:raise ValueError('boolean preference classification required')
    if any(obj[k]not in {'HELPFUL','NOT_APPLICABLE','UNCERTAIN'}for k in ['role_A','role_B']):raise ValueError('invalid applicability')
    short(obj['reason'],700);return obj


def vet(pairs,gateway):
    rows=[]
    for pair in pairs:
        label=gateway.object('boundary_vet/'+sha(pair['input']),PROMPT,pair['input'],validate,2048)
        # A contrast requires real opposite applicability, not empty agreement.
        valid=label['source_is_preference']and {label['role_A'],label['role_B']}=={'HELPFUL','NOT_APPLICABLE'}
        rows.append({**pair,'automatic_label':label,'opposite_applicability':valid,
                     'feedback_level':'CONTEXTUAL_AUTO_JUDGE_NOT_UNIT_GOLD','human_reviews':0})
    return rows


def preserve_members(parent,candidate,member_ids):
    """Reject compensation across the two members of a vetted boundary contrast."""
    from .policies import promote
    for uid in member_ids:
        if uid not in parent or uid not in candidate or not promote(parent[uid],candidate[uid],True):return False
    return True
