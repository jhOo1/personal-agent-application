"""Allocation-only identities and conservative exposure propagation.

No model, benchmark scorer, reference labels, Store or dataset selection. Exact
identity and absence of recorded exposure never certify semantic independence.
"""
from collections import defaultdict
from proposals.qamc_selection_exposure.core import norm,digest,grouped


def add_source(rows,patterns,benchmark,path,index,query,memories,**metadata):
    qid=benchmark+':query:'+digest(norm(query));patterns[qid]=norm(query)
    mids=[]
    for memory in memories:
        if not isinstance(memory,str) or not norm(memory):continue
        mid=benchmark+':memory:'+digest(norm(memory));patterns[mid]=norm(memory);mids.append(mid)
    row={'source_id':digest([path,index]),'benchmark':benchmark,'source_file':path,'row_index':index,
        'query_probe':qid,'memory_probes':sorted(set(mids)),'lineage_keys':[qid,*sorted(set(mids))],**metadata}
    if benchmark=='benchpres':
        row['preference_bundle_group']=digest(sorted(set(mids)))
        row['context_group']=digest(norm(query))
        # The two grid axes are not unioned into a single connected component.
        row['lineage_keys']=['combination:'+digest([qid,row['profile_group']])]
    rows.append(row)


def finalize_groups(rows):
    groups=grouped(rows)
    for index,row in enumerate(rows):row['audit_group_id']=groups[index]


class ExposureIndex:
    def __init__(self,rows,patterns):
        self.rows=rows;self.patterns=patterns
        self.probe_groups=defaultdict(set);self.group_states=defaultdict(set)
        self.group_examples=defaultdict(dict);self.profile_bundles={};self.bundle_queries={}
        self.context_probes={}
        self.observed_profiles=set();self.observed_contexts=set();self.observed_combinations=set()
        for row in rows:
            for key in (row['query_probe'],*row['memory_probes']):
                self.probe_groups[key].add(row['audit_group_id'])
            if row['benchmark']=='benchpres':
                profile=row['profile_group'];self.profile_bundles[profile]=set(row['memory_probes'])
                self.bundle_queries[(profile,row['query_probe'])]=row['source_id']
                self.context_probes[row['query_probe']]=row['context_group']
        self.declared_allocations=defaultdict(set);self.historical_reservations=set()

    def register(self,matches,wire_hash,state,example):
        for group in {g for key in matches for g in self.probe_groups.get(key,())}:
            self.group_states[group].add(state)
            self.group_examples[group].setdefault(state,{'request_sha256':wire_hash,**example})
        for profile,required in self.profile_bundles.items():
            if required and required<=matches:
                self.observed_profiles.add(profile)
                for (p,query),source in self.bundle_queries.items():
                    if p==profile and query in matches:self.observed_combinations.add(source)
        self.observed_contexts.update(self.context_probes[key] for key in matches if key in self.context_probes)

    def rows_for_export(self,unprobed=()):
        unprobed=set(unprobed);output=[]
        group_allocated={row['audit_group_id'] for row in self.rows if row['source_id'] in self.declared_allocations}
        group_reserved={row['audit_group_id'] for row in self.rows if row['source_id'] in self.historical_reservations}
        short_groups={row['audit_group_id'] for row in self.rows
            if {row['query_probe'],*row['memory_probes']}&unprobed}
        for row in self.rows:
            group=row['audit_group_id'];seen=bool(self.group_states.get(group))
            short=group in short_groups
            value={k:v for k,v in row.items() if k!='lineage_keys'}
            value.update(recorded_exact_group_exposure=seen,
                observed_states=sorted(self.group_states.get(group,())),
                group_has_declared_allocation=group in group_allocated,
                group_has_historical_reservation=group in group_reserved,
                declared_allocation_files=sorted(self.declared_allocations.get(row['source_id'],())),
                historical_reservation=row['source_id'] in self.historical_reservations,
                short_source_probe_incomplete=short,
                preliminary_unobserved_upper_bound=not(seen or group in group_allocated or group in group_reserved or short),
                certified_independent=False)
            if row['benchmark']=='benchpres':
                value.update(profile_preference_bundle_observed=row['profile_group'] in self.observed_profiles,
                    task_context_observed=row['context_group'] in self.observed_contexts,
                    preference_bundle_query_coexposure=row['source_id'] in self.observed_combinations,
                    unseen_profile_upper_bound=not(seen or row['profile_group'] in self.observed_profiles
                        or group in group_allocated or group in group_reserved or short))
            output.append(value)
        return output


def capacity(rows):
    result={}
    for benchmark in ('rpeval','benchpres','persistbench'):
        selected=[r for r in rows if r['benchmark']==benchmark and r.get('population')=='official']
        available=[r for r in selected if r['preliminary_unobserved_upper_bound']]
        item={'official_rows':len(selected),'exact_source_connected_groups':len({r['audit_group_id'] for r in selected}),
            'recorded_exposed_rows':sum(r['recorded_exact_group_exposure'] for r in selected),
            'declared_allocation_group_rows':sum(r['group_has_declared_allocation'] for r in selected),
            'historically_reserved_group_rows':sum(r['group_has_historical_reservation'] for r in selected),
            'preliminary_unobserved_rows_upper_bound':len(available),
            'preliminary_unobserved_groups_upper_bound':len({r['audit_group_id'] for r in available}),
            'certified_independent_confirmation_capacity':'UNKNOWN',
            'near_source_screening_performed_in_this_census':False}
        if benchmark=='benchpres':
            item.update(profiles=len({r['profile_group'] for r in selected}),
                observed_profile_preference_bundles=len({r['profile_group'] for r in selected if r['profile_preference_bundle_observed']}),
                task_contexts=len({r['context_group'] for r in selected}),
                observed_contexts=len({r['context_group'] for r in selected if r['task_context_observed']}),
                recorded_bundle_query_coexposed_rows=sum(r['preference_bundle_query_coexposure'] for r in selected),
                unseen_profile_rows_upper_bound=sum(r['unseen_profile_upper_bound'] for r in selected),
                known_profile_unobserved_combination_rows_upper_bound=sum(
                    not(r['preference_bundle_query_coexposure'] or r['group_has_declared_allocation']
                        or r['group_has_historical_reservation'] or r['short_source_probe_incomplete']) for r in selected),
                component_exposure_is_not_proof_every_combination_was_run=True)
        dimension='track' if benchmark=='rpeval' else 'category' if benchmark=='persistbench' else None
        if dimension:
            item['by_'+dimension]={key:{'official_rows':sum(r.get(dimension)==key for r in selected),
                'preliminary_unobserved_rows_upper_bound':sum(r.get(dimension)==key for r in available),
                'preliminary_unobserved_groups_upper_bound':len({r['audit_group_id'] for r in available if r.get(dimension)==key})}
                for key in sorted({r[dimension] for r in selected})}
        result[benchmark]=item
    return result
