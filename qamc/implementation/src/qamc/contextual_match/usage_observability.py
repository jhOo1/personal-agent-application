"""Safe numeric usage detail capture over an isolated unchanged SSE reader.

Payloads, public answers and the three-field response usage schema stay intact.
Old frozen readers are not patched. No hidden reasoning or arbitrary provider
metadata is saved; older lost detail cannot be reconstructed by this module.
"""
import importlib.util,json,threading
from pathlib import Path
from . import lossless_transport as integrity
from proposals.qamc_protocol_alignment import transport as legacy
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.transport_helpers import atomic_json

VERSION='safe_numeric_usage_details_v1'
_state=threading.local()
FIELDS={'prompt_tokens_details':('cached_tokens','audio_tokens'),
        'completion_tokens_details':('reasoning_tokens','audio_tokens','accepted_prediction_tokens','rejected_prediction_tokens')}
TOP=('reasoning_tokens','thinking_tokens','cached_tokens','input_tokens','output_tokens')


def safe_numeric_details(value):
    if not isinstance(value,dict):return {}
    out={k:value[k] for k in TOP if type(value.get(k)) is int and value[k]>=0}
    for section,keys in FIELDS.items():
        values=value.get(section)
        if isinstance(values,dict):
            kept={k:values[k] for k in keys if type(values.get(k)) is int and values[k]>=0}
            if kept:out[section]=kept
    return out


def capture_usage(value):
    # The last usage chunk wins, exactly as in the original reader. A final
    # chunk without a breakdown must not inherit earlier, possibly stale data.
    _state.details=safe_numeric_details(value)
    return legacy.numeric_usage(value)


def preserve_answer(value,config):
    clean=integrity.public_marker_sanitize(value,config)
    if isinstance(value,dict) and isinstance(value.get('answer'),str):_state.answer_changed=clean.get('answer')!=value['answer']
    return clean


_spec=importlib.util.spec_from_file_location('proposals.qamc_protocol_alignment._usage_observable_reader_v1',Path(legacy.__file__))
_reader=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_reader)
_reader.numeric_usage=capture_usage;_reader.sanitize=preserve_answer


class UsageObservableSampler(_reader.NativeSampler):
    def _send(self,unit,public):
        _state.details={};_state.answer_changed=False
        try:
            result=super()._send(unit,public)
        finally:
            folder=self.root/'visible'/sampling_key(unit);path=folder/'record.json'
            if path.exists():
                record=json.loads(path.read_text());changed=bool(_state.answer_changed)
                record.update(answer_integrity_policy=integrity.POLICY,answer_integrity=integrity.POLICY,
                    answer_text_changed_by_privacy_filter=changed,usage_audit_version=VERSION,
                    usage_numeric_details=dict(_state.details))
                usage=record.get('usage') or {};comp=usage.get('completion_tokens');reason=(_state.details.get('completion_tokens_details') or {}).get('reasoning_tokens')
                record['requested_max_tokens']=public['max_tokens']
                record['reported_completion_over_requested']=comp>public['max_tokens'] if type(comp) is int else None
                record['reported_completion_minus_reasoning_tokens']=comp-reason if type(comp) is int and type(reason) is int and reason<=comp else None
                record['visible_token_cap_enforcement']='NOT_CERTIFIED_BY_USAGE_METADATA'
                if changed and record.get('status')=='OK':record.update(status='ANSWER_REDACTED_NOT_USABLE',error='sensitive_answer_text_redacted_no_semantic_use')
                atomic_json(path,record)
        if _state.answer_changed:raise legacy.SamplingTransportError('sensitive_answer_text_redacted_no_semantic_use')
        return result
