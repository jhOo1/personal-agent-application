"""Finite cached cells with explicit normal/fallback/scoring failure separation."""
from pathlib import Path
import json
from qamc.common import sha
from qamc.transport_helpers import atomic_json
from qamc.pa.core import PublicTask,Memory,digest
from .engine import FusedEngine
from qamc.pa.evaluate import Evaluator


def load_task(root,item):
    public=json.loads((root/item['public_path']).read_text())
    if digest(public)!=item['public_hash']:raise ValueError('Public input changed')
    task=PublicTask(public['uid'],public['query'],tuple(Memory(m['memory_id'],m['text'],tuple(tuple(v) for v in m['ranges'])) for m in public['memories']),public['current_context'],tuple(public['fixed_facts']))
    return task


class FusedExperiment:
    def __init__(self,gateway,root,run):
        self.g=gateway;self.root=root;self.run=run
        self.engine=FusedEngine(gateway,run);self.evaluator=Evaluator(gateway,run)

    def stopped(self):return self.g.disabled or (self.g.root/'STOP').exists()

    def score_saved(self,item,task,row):
        if row.get('answer_status')!='OK' or row.get('score_status')!='NOT_RUN' or self.stopped():return row
        reference=json.loads((self.root/item['evaluation_path']).read_text())
        if digest(reference)!=item['evaluation_hash']:raise ValueError('Reference changed')
        try:
            row['score']=self.evaluator.score(item['benchmark'],task.uid,task.query,reference,row['answer'])
            row['score_status']='OK'
        except Exception as exc:
            row.update(score_status='FAILED',score=None,score_error_type=type(exc).__name__,score_error=str(exc))
        return row

    def case(self,item):
        task=load_task(self.root,item);directory=self.run/'outcomes'/sha(task.uid)[:24]
        directory.mkdir(parents=True,exist_ok=True)
        gate=None
        # Frozen order obtains the actual matched Gate once for disclosed fallback.
        for arm in ('G0','R0','S0','V0','F0'):
            path=directory/(arm+'.json')
            if path.exists():
                row=json.loads(path.read_text())
                if row.get('answer_status')=='OK' and row.get('score_status')=='NOT_RUN' and not self.stopped():
                    row=self.score_saved(item,task,row);atomic_json(path,row)
                if arm=='G0' and row.get('answer_status')=='OK':gate=row
                continue
            if self.stopped():return
            row={'uid':task.uid,'benchmark':item['benchmark'],'arm':arm,'public_hash':item['public_hash'],
                 'pipeline_status':'OK','fallback':False,'score_status':'NOT_RUN','answer_status':'NOT_RUN'}
            try:
                result=self.engine.run(task,arm)
                row.update(result,answer_status='OK')
            except Exception as exc:
                row.update(pipeline_status='FAILED',answer_status='FAILED',error_type=type(exc).__name__,error=str(exc))
                if arm not in {'G0','R0'} and gate:
                    row.update(answer=gate['answer'],actor_request_hash=gate['actor_request_hash'],answer_status='OK',fallback=True,
                               fallback_source='matched_G0_saved_answer')
            # Persist completed generation before any evaluator work. The private
            # reference is loaded only after the Actor returned a final answer.
            atomic_json(directory/(arm+'.generation.json'),row)
            row=self.score_saved(item,task,row)
            atomic_json(path,row)
            if arm=='G0' and row.get('answer_status')=='OK':gate=row
