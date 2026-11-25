"""Policy-phase content-only views; empty-policy inputs match the static pilot.

The static engine is retained unchanged. This subclass changes only policy
injection metadata and exact duplicate routing, never evidence, Actor or scorer.
The legacy model-visible policy_version_hash is fixed to its original empty value;
actual library/version hashes remain in request keys and result metadata. This
prevents an irrelevant changing hash string from acting as a sampling seed.
"""
from concurrent.futures import ThreadPoolExecutor
from qamc.common import ROOT,sha,canonical
from qamc.transport_helpers import atomic_json
from .engine import PreferenceEngine as BaseEngine,prompt
from .core import validate_role,validate_joint,merge,validate_resolution,actor_view,fields,strings
from .policies import validate_library
from .policy_views import content,role_hash,joint_hash


def retrieve_effective(cards,payload,role):
    import re
    terms=set(re.findall(r'\w+',payload['query'].lower()+' '+' '.join(u['exact_text']for u in payload['units']).lower()))
    eligible=[c for c in cards if c['status']=='active'and c['target_role']in {role,'both'}]
    eligible.sort(key=lambda c:(-len(terms&set(re.findall(r'\w+',c['trigger'].lower()))),canonical(content(c))))
    out=[];seen=set()
    for card in eligible:
        value=content(card);key=canonical(value)
        if key not in seen:out.append(value);seen.add(key)
        if len(out)==3:break
    return out


class PolicyEngine(BaseEngine):
    build_actor_view=staticmethod(actor_view)
    def answer(self, bundle, scope, arm, cards, directory):
        validate_library(cards)
        p = bundle['payload']
        policy_hash = sha(cards)
        allow_view=retrieve_effective(cards,p,'allow');deny_view=retrieve_effective(cards,p,'deny')
        inp = {**p, 'scopes':scope['scopes'], 'shared_task_unit_ids':scope['task_unit_ids'],
               'allow_policies':allow_view, 'deny_policies':deny_view,
               'policy_version_hash':sha([])}
        base = arm+'/'+bundle['input_hash']+'/'+policy_hash
        g = self.gateway
        def role(which):
            # Initial roles receive the same evidence but never the other output.
            payload = {k:v for k,v in inp.items() if k not in {'allow_policies','deny_policies'}}
            payload['policy_version_hash']=sha([])
            payload['policies'] = inp[which+'_policies']
            return self.memo(directory/(which+'.json'), lambda: g.object(base+'/'+which,
                prompt('common')+'\n'+prompt(which)+'\n'+prompt('schema'),payload,
                lambda o:validate_role(o,p,scope,which),8192))
        if arm == 'S0':
            def gate_check(o):
                fields(o,'selected_unit_ids material_gaps')
                ids={u['unit_id'] for u in p['units']}
                if not set(strings(o['selected_unit_ids'])) <= ids:
                    raise ValueError('unknown gate unit')
                strings(o['material_gaps'])
            out=self.memo(directory/'gate.json',lambda:g.object(base+'/gate',prompt('common')+'\n'+prompt('gate'),inp,gate_check,8192))
            # No use labels are fabricated for a whole-unit gate baseline.
            frame={**scope,'task_unit_ids':list(set(scope['task_unit_ids'])|set(out['selected_unit_ids']))}
            view=self.build_actor_view(p,frame,[],out['material_gaps'])
        else:
            if arm == 'S2':
                with ThreadPoolExecutor(max_workers=2) as pool:
                    aa,dd=pool.submit(role,'allow'),pool.submit(role,'deny')
                    joint={'allow':aa.result(),'deny':dd.result()}
            elif arm in {'S1','S1+'}:
                joint=self.memo(directory/'joint.json',lambda:g.object(base+'/joint',
                    prompt('common')+'\n'+prompt('allow')+'\n'+prompt('deny')+'\n'+prompt('joint')+'\n'+prompt('schema'),inp,
                    lambda o:validate_joint(o,p,scope),8192))
                if arm=='S1+':
                    joint=self.memo(directory/'recheck.json',lambda:g.object(base+'/recheck',
                        prompt('common')+'\n'+prompt('recheck')+'\n'+prompt('schema'),{**inp,'initial_proposal':joint},
                        lambda o:validate_joint(o,p,scope),8192))
            else:
                raise ValueError('unsupported arm')
            merged=merge(joint['allow'],joint['deny'],scope)
            # Exact same trigger/one-pass merger is used by all bidirectional arms.
            if merged['conflicts'] or merged['material_gaps']:
                resolution=self.memo(directory/'resolution.json',lambda:g.object(base+'/resolve',
                    prompt('common')+'\n'+prompt('resolver')+'\n'+prompt('resolve_schema'),
                    {**p,'scopes':scope['scopes'],'conflicts':merged['conflicts'],'material_gaps':merged['material_gaps']},
                    lambda o:validate_resolution(o,merged,p,scope),8192))
                decisions=merged['decisions']+resolution['decisions']
                gaps=resolution['material_gaps']
            else:
                decisions,gaps=merged['decisions'],[]
            atomic_json(directory/'merge.json',{**merged,'final_decisions':decisions,'final_gaps':gaps})
            view=self.build_actor_view(p,scope,decisions,gaps)
        # This complete view and identical system prompt are used across all arms.
        actor=(ROOT/'prompts/actor_decision_binding.md').read_text()+'\n'+prompt('actor')
        atomic_json(directory/'actor_input.json',view)
        answer=self.memo(directory/'answer.json',lambda:g.complete(base+'/actor',actor,view,4096))
        return {'answer':answer,'input_hash':bundle['input_hash'],'policy_hash':policy_hash,
                'actor_system_hash':sha(actor),'actor_input_hash':sha(view),'effective_policy_views_hash':joint_hash(allow_view,deny_view)}
