"""Independent sparse proposals followed by explicit union-aligned scoring."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from qamc.common import sha
from qamc.preference_policy.profile_input import wire
from .audit import ROOT
from .contract import generation_input
from .inventory import union_inventory
from .schemas import key_from,validate_inventory,validate_assessments


class ScoreEngine:
    def __init__(self,gateway,steps):self.gateway=gateway;self.steps=steps

    def score(self,uid,bundle,scopes,directory):
        p=generation_input(bundle['payload']);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        # Character counts aid exact full-unit references without changing R.
        p={**p,'units':[{**u,'char_length':len(u['exact_text'])} for u in p['units']]}
        compact=wire(p)
        for unit in compact['units']:unit['char_length']=len(unit['exact_text'])
        initial={'input':compact,'scopes':scopes}
        prompt_dir=ROOT/'prompts/bace'
        def proposal(role):
            text=(prompt_dir/'propose.md').read_text()
            request={**initial,'ROLE':role.upper()}
            return self.steps.run(uid+'/proposal/'+role,{'prompt':text,'request':request},
                lambda:self.gateway.object(uid+'/proposal/'+role,text,request,
                    lambda o:validate_inventory(o,p,scopes),8192))
        with ThreadPoolExecutor(max_workers=2) as pool:
            aa=pool.submit(proposal,'allow');dd=pool.submit(proposal,'deny')
            proposed={'allow':aa.result(),'deny':dd.result()}
        required=[]
        scope_map={s['scope_id']:s for s in scopes}
        for role in ('allow','deny'):
            for fact in proposed[role]['necessary_facts']:
                if fact['source_span']['unit_id']=='Q0':continue
                item={'unit_id':fact['source_span']['unit_id'],'scope_id':fact['scope_id'],
                      'use_kind':'USER_HISTORY' if fact['kind']=='HISTORICAL_BACKGROUND' else 'FACT_EVIDENCE',
                      'source_span':fact['source_span'],
                      'query_anchor':scope_map[fact['scope_id']]['query_anchor']}
                if item not in required:required.append(item)
        union=union_inventory([key_from(x) for x in proposed['allow']['uses']],
                              [key_from(x) for x in proposed['deny']['uses']],
                              [key_from(x) for x in required])
        uses=[]
        for key in union['selected']:
            variants=[x for role in ('allow','deny') for x in proposed[role]['uses'] if key_from(x)==key]
            variants += [x for x in required if key_from(x)==key]
            # No role opinions/scores are revealed to the other side. Distinct
            # exact spans for the SAME use are kept as source alternatives.
            spans=[]
            for x in variants:
                if x['source_span'] not in spans:spans.append(x['source_span'])
            uses.append({**asdict(key),'source_spans':spans,'query_anchor':variants[0]['query_anchor']})
        def assess(role):
            text=(prompt_dir/(role+'.md')).read_text();request={**initial,'use_inventory':uses}
            return self.steps.run(uid+'/assessment/'+role,{'prompt':text,'request':request},
                lambda:self.gateway.object(uid+'/assessment/'+role,text,request,
                    lambda o:validate_assessments(o,role,p,scopes,uses),8192))
        with ThreadPoolExecutor(max_workers=2) as pool:
            aa=pool.submit(assess,'allow');dd=pool.submit(assess,'deny')
            assessed={'allow':aa.result(),'deny':dd.result()}
        result={'uid':uid,'input_hash':bundle.get('input_hash',sha(p)),
                'proposals':proposed,'inventory':uses,
                'unassessed_overflow':[asdict(k) for k in union['unassessed_overflow']],
                'required_overflow':[asdict(k) for k in union['required_overflow']],
                'assessment':assessed,'model_alias':self.gateway.model,'temperature':0,
                'score_semantics':'uncalibrated support and risk, not complementary probabilities',
                'prompt_hashes':{f.name:sha(f.read_bytes()) for f in prompt_dir.glob('*.md')},
                'semantic_correctness_verified':False}
        from qamc.transport_helpers import atomic_json
        atomic_json(directory/'scores.json',result)
        return result
