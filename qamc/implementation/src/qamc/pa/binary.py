"""Second and final prompt revision: whole-source binary selection only."""
from .engine import Engine,ROOT
from .core import compile_view
from qamc.common import sha


def expand_actions(task,selection,arm):
    # The model cannot create source spans or silently default an influence level.
    if not isinstance(selection,dict) or set(selection)!={'preference_actions','unresolved_ids'}:
        raise ValueError('Binary selector fields')
    sources={m.memory_id:m for m in task.memories}
    expanded=[]
    if not isinstance(selection['preference_actions'],list):raise ValueError('Actions list')
    for row in selection['preference_actions']:
        required={'memory_id','decision'}|({'influence'} if arm=='V2' else set())
        if set(row)!=required or row['decision'] not in {'APPLY','DROP'}:
            raise ValueError('Only whole-source APPLY/DROP is supported')
        if row['memory_id'] not in sources:raise ValueError('Unknown source')
        expanded.append({**row,'keep_span_ids':list(sources[row['memory_id']].spans()) if row['decision']=='APPLY' else []})
    result={**selection,'preference_actions':expanded}
    compile_view(task,result,arm)
    return result


class BinaryEngine(Engine):
    def select(self,task,arm):
        if arm not in ('V0','V2'):return super().select(task,arm)
        # V0 is named V0 only for report compatibility; provenance explicitly says
        # V1 judgment criteria with a new binary output contract, not old V0.
        system=(ROOT/'prompts/qamc_pa_v2'/('strength.md' if arm=='V2' else 'binary.md')).read_text()
        payload=task.payload()
        for memory in payload['memories']:memory.pop('spans')
        selection=self.g.object('pa-v2/select/'+sha([task.uid,arm,system,payload]),system,payload,
                                lambda x:expand_actions(task,x,arm),8192)
        expanded=expand_actions(task,selection,arm)
        return compile_view(task,expanded,arm),expanded
