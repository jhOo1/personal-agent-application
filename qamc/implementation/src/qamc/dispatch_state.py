"""Distinguish an undispatched operation from an uncertain or failed delivery."""
from .api import CallError
from .rate_limit import DispatchStopped


def definitely_undispatched(exc):
    return (isinstance(exc, DispatchStopped) or
            isinstance(exc, CallError) and str(exc) == 'operator_or_quota_stop_no_dispatch')


def record_interruption(row, exc, stage):
    row.setdefault('interruptions', []).append({'stage':stage,'error_type':type(exc).__name__,
                                               'error':str(exc),'definitely_undispatched':definitely_undispatched(exc)})
    row['error_type']=type(exc).__name__
    row['error']=str(exc)
    status='not_dispatched' if definitely_undispatched(exc) else 'failed'
    if stage=='score':row['score_status']=status
    else:row['actor_status']=status
    return row
