"""Fingerprint the revised selection and common actor implementation."""
import hashlib
from .common import ROOT

PATHS=('src/qamc/decision_controller.py','src/qamc/decision_binding.py','src/qamc/candidate_ids.py',
       'src/qamc/actor.py','src/qamc/api.py','src/qamc/pilot_scoring.py','src/qamc/scoring.py',
       'src/qamc/memsyco_official_bridge.py','prompts/semantic_gate.md','prompts/unified_binder.md',
       'prompts/actor_decision_binding.md')

def fingerprint(root=ROOT):
    h=hashlib.sha256()
    for name in PATHS:
        data=(root/name).read_bytes()
        h.update(name.encode());h.update(b'\0');h.update(hashlib.sha256(data).digest())
    return h.hexdigest()
