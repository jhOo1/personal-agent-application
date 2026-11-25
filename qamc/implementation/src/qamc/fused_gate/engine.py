"""Use one joint admission call with the original shared Actor."""
from qamc.pa.binary import BinaryEngine
from qamc.pa.engine import ROOT
from qamc.common import sha
from .core import public_payload,compile_selected

class FusedEngine(BinaryEngine):
    def select(self,task,arm):
        if arm!='F0':return super().select(task,arm)
        payload=public_payload(task)
        system=(ROOT/'prompts/preference_policy/common.md').read_text()+'\n'+(ROOT/'prompts/qamc_fused_gate/selector.md').read_text()
        selection=self.g.object('pa-fused/select/'+sha([task.uid,system,payload]),system,payload,
                                lambda x:compile_selected(task,payload,x),8192)
        return compile_selected(task,payload,selection),selection
