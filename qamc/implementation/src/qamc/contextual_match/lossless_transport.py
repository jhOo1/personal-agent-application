"""Versioned answer-integrity policy over the unchanged native HTTP reader.

Conventional public API-key sentinels are not secrets. Genuine configured
credentials still disappear; if that changes answer text, the sample cannot
silently become inference or grading data. Legacy modules/files stay intact.
"""
import importlib.util
import json
from pathlib import Path
import threading

from qamc.transport_helpers import sanitize as legacy_sanitize,atomic_json
from proposals.qamc_protocol_alignment import transport as legacy
from proposals.qamc_protocol_alignment.sampling import sampling_key

POLICY='public_api_sentinel_and_exact_answer_v2'
PUBLIC_API_SENTINELS={'placeholder','EMPTY','empty','dummy','unused','none','None','NO_KEY'}
_observed=threading.local()


def public_marker_sanitize(value,config):
    # Restrict this exception to explicit public sentinels in the API-key slot;
    # real access keys, quota/user IDs, headers and reasoning remain protected.
    protected={k:v for k,v in config.items() if not (k=='api_key' and v in PUBLIC_API_SENTINELS)}
    clean=legacy_sanitize(value,protected)
    if isinstance(value,dict) and isinstance(value.get('answer'),str):
        _observed.answer_changed=(clean.get('answer')!=value['answer'])
    return clean


# The original reader resolves its sanitizer in module globals. Load an isolated
# module instance with the same package for relative imports; never monkeypatch
# the legacy reader used by frozen experiments or copy its network implementation.
_name='proposals.qamc_protocol_alignment._lossless_transport_v2'
_spec=importlib.util.spec_from_file_location(_name,Path(legacy.__file__))
_reader=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reader)
_reader.sanitize=public_marker_sanitize


class LosslessNativeSampler(_reader.NativeSampler):
    def _send(self,unit,public):
        _observed.answer_changed=False
        result=super()._send(unit,public)
        folder=self.root/'visible'/sampling_key(unit)
        record=json.loads((folder/'record.json').read_text())
        changed=bool(_observed.answer_changed)
        record.update(answer_integrity_policy=POLICY,answer_text_changed_by_privacy_filter=changed)
        if changed:
            record.update(status='ANSWER_REDACTED_NOT_USABLE',error='sensitive_answer_text_redacted_no_semantic_use')
            atomic_json(folder/'record.json',record)
            raise legacy.SamplingTransportError('sensitive_answer_text_redacted_no_semantic_use')
        # Keep the strict native response contract unchanged. Integrity belongs
        # to the receipt, not an extra response key rejected by SamplingJournal.
        record['answer_integrity']=POLICY
        atomic_json(folder/'record.json',record)
        return result


def filter_compatible_cache(root,index):
    """Reuse unaltered legacy strings; exclude only completed noncomparable data.

    Failed/unknown attempts remain blockers. No score is inspected. Absence of
    the literal replacement marker proves identity for the retained legacy
    string replacer, but is not model-weight/provider certification.
    """
    root=Path(root);kept=[];excluded=[]
    for row in index['records']:
        if row['status']!='ok' or not row.get('response_path'):
            kept.append(row);continue
        path=Path(row['response_path']);path=path if path.is_absolute() else root/path
        value=json.loads(path.read_text());answer=value.get('answer')
        if not isinstance(answer,str):
            kept.append({**row,'status':'PRIOR_UNVERIFIED_RESPONSE_SCHEMA'});continue
        receipt_path=path.with_name('record.json')
        receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        exact_v2=receipt.get('answer_integrity')==POLICY
        if not exact_v2 and '[REDACTED]' in answer:
            excluded.append({**row,'reason':'completed_legacy_answer_integrity_unknown_cannot_restore_raw'})
        else:kept.append(row)
    return {**index,'records':kept,'noncomparable_completed_records':excluded,
        'answer_integrity_policy':POLICY,'no_failed_or_unknown_retry':True}
