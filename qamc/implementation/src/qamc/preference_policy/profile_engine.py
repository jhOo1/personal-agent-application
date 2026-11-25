"""Corrected input epoch; the four control algorithms remain frozen.
All old scores remain in the parent epoch.
"""
"""Four static controls with shared scope preparation, evidence and Actor."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from qamc.common import ROOT, sha
from qamc.transport_helpers import atomic_json
from .core import (validate_scope, validate_role, validate_joint, merge,
                   validate_resolution, actor_view, strings, fields)
from .policies import validate_library, retrieve
from .profile_input import actor_view

PROMPTS = ROOT / 'prompts/preference_policy'


def prompt(name):
    return (PROMPTS / (name + '.md')).read_text()


class ProfileEngine:
    def __init__(self, gateway):
        self.gateway = gateway

    def memo(self, path, make):
        if path.exists():
            row = json.loads(path.read_text())
            if row['status'] != 'ok':
                raise RuntimeError('retained_terminal_failure: ' + str(path))
            return row['result']
        try:
            result = make()
            atomic_json(path, {'status':'ok', 'result':result})
            return result
        except Exception as exc:
            atomic_json(path, {'status':'failed', 'error_type':type(exc).__name__, 'error':str(exc)})
            raise

    def scope(self, bundle, directory):
        payload = bundle['payload']
        return self.memo(directory/'scope.json', lambda: self.gateway.object(
            'scope/'+bundle['input_hash'], prompt('common')+'\n'+prompt('scope'), payload,
            lambda o: validate_scope(o,payload), 4096))

    def answer(self, bundle, scope, arm, cards, directory):
        validate_library(cards)
        p = bundle['payload']
        policy_hash = sha(cards)
        inp = {**p, 'scopes':scope['scopes'], 'shared_task_unit_ids':scope['task_unit_ids'],
               'allow_policies':retrieve(cards,p,'allow'), 'deny_policies':retrieve(cards,p,'deny'),
               'policy_version_hash':policy_hash}
        base = arm+'/'+bundle['input_hash']+'/'+policy_hash
        g = self.gateway
        def role(which):
            # Initial roles receive the same evidence but never the other output.
            payload = {k:v for k,v in inp.items() if k not in {'allow_policies','deny_policies'}}
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
            view=actor_view(p,frame,[],out['material_gaps'])
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
            view=actor_view(p,scope,decisions,gaps)
        # This complete view and identical system prompt are used across all arms.
        actor=(ROOT/'prompts/actor_decision_binding.md').read_text()+'\n'+prompt('actor')
        atomic_json(directory/'actor_input.json',view)
        answer=self.memo(directory/'answer.json',lambda:g.complete(base+'/actor',actor,view,4096))
        return {'answer':answer,'input_hash':bundle['input_hash'],'policy_hash':policy_hash,
                'actor_system_hash':sha(actor),'actor_input_hash':sha(view)}
