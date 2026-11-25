"""Score-only overlay contracts; original answers and valid scores are immutable."""
from copy import deepcopy
from qamc.common import sha
from .evaluation import unique_index
from .score_refresh import SCORING_FIELDS
from .phase_runtime import model_block
from proposals.qamc_protocol_alignment.sampling import sampling_key


def verify_completion(original,updated,eligible_pairs):
    before,after=unique_index(original['rows']),unique_index(updated['rows'])
    if before.keys()!=after.keys():raise ValueError('Score completion changed row coverage')
    if {k:v for k,v in original.items() if k!='rows'}!={k:v for k,v in updated.items() if k!='rows'}:
        raise ValueError('Score completion changed wave metadata')
    for key,old in before.items():
        new=after[key]
        if {k:v for k,v in old.items() if k not in SCORING_FIELDS}!={k:v for k,v in new.items() if k not in SCORING_FIELDS}:
            raise ValueError('Score completion changed Actor input, answer or availability')
        changed=any(old.get(k)!=new.get(k) for k in SCORING_FIELDS)
        if changed and (key not in eligible_pairs or old.get('score') is not None
                        or old.get('actor_status')!='OK' or key[1]=='ORIGINAL'):
            raise ValueError('Score completion replaced an existing or ineligible grade')
    return deepcopy(updated)


class CompletionOverlay:
    """Read original Actors and noneligible grades; use new outputs only for declared work."""
    def __init__(self,source_plan,completion_plan,source_runtimes,new_runtimes,unit_builder):
        self.source_plan,self.plan=source_plan,completion_plan
        self.source,self.new=source_runtimes,new_runtimes;self.unit_builder=unit_builder
        self.allowed=set(completion_plan['allowed_unit_keys'])

    def output(self,unit):
        block=model_block(unit['stage'])
        if sampling_key(unit) in self.allowed:return self.new[block].output(unit)
        original=self.unit_builder(self.source_plan,unit['root_id'],unit['method'],unit['stage'])
        return self.source[block].output(original)


def completion_jobs(source_jobs,protocols,unit_builder):
    """A new namespace, exact public bodies, one-to-one old unissued identities."""
    target={'protocols':protocols};result=[];seen=set()
    for old in source_jobs:
        unit=old['unit'];key=sampling_key(unit)
        if key in seen:raise ValueError('Duplicate recovery source identity')
        if unit['method']=='ORIGINAL' or unit['stage'] not in ('RPEvalJudge','PersistJudge'):
            raise ValueError('Only unissued nonbaseline GPT grades may be completed')
        seen.add(key)
        new=unit_builder(target,unit['root_id'],unit['method'],unit['stage'])
        result.append({'unit':new,'request':deepcopy(old['request']),
                       'source_unit':deepcopy(unit),'source_request_sha256':sha(old['request'])})
    return result
