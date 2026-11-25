"""Missing-aware physical cost and latency summaries, separate from scores."""
from collections import Counter,defaultdict
import json
import math
from .evaluation import percentile


TOKEN_FIELDS=('prompt_tokens','completion_tokens','total_tokens')
PENDING='PENDING_DELIVERY_UNKNOWN'


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def unit_key(record):
    return json.dumps(record['unit'],sort_keys=True,ensure_ascii=False)


def summarize_records(records):
    terminal=[r for r in records if r['status']!=PENDING]
    successful=[r for r in terminal if r['status']=='OK']
    elapsed=[r['elapsed_seconds'] for r in terminal if number(r.get('elapsed_seconds'))]
    success_elapsed=[r['elapsed_seconds'] for r in successful if number(r.get('elapsed_seconds'))]
    tokens={}
    for field in TOKEN_FIELDS:
        known=[(r.get('usage') or {}).get(field) for r in records]
        known=[n for n in known if number(n)]
        tokens[field]={'reported_sum':sum(known),'reporting_requests':len(known),
            'finished_unknown_requests':sum(not number((r.get('usage') or {}).get(field)) for r in terminal),
            'pending_unknown_requests':sum(r['status']==PENDING and not number((r.get('usage') or {}).get(field)) for r in records),
            'is_complete':len(known)==len(records)}
    return {'physical_requests':len(records),'terminal_requests':len(terminal),'pending_requests':len(records)-len(terminal),
        'statuses':dict(Counter(r['status'] for r in records)),'tokens':tokens,
        'terminal_latency_seconds':{'observed_requests':len(elapsed),'p50':percentile(elapsed,.5),
            'p95':percentile(elapsed,.95),'max':max(elapsed) if elapsed else None,'sum':sum(elapsed)},
        'successful_latency_seconds':{'observed_requests':len(success_elapsed),
            'p50':percentile(success_elapsed,.5),'p95':percentile(success_elapsed,.95)},
        'automatic_retries_reported':sum(r.get('automatic_retries',0) for r in records),
        'latency_sum_is_not_wall_time':True,'currency_cost':None}


def account(records,logical_outputs=()):
    keys=[unit_key(r) for r in records]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate physical sampling units in cost ledger')
    logical_keys=[unit_key(r) for r in logical_outputs]
    if len(set(logical_keys))!=len(logical_keys):raise ValueError('Duplicate logical outputs in cost ledger')
    groups=defaultdict(list)
    for r in records:groups[(r.get('model_block','UNKNOWN'),r['unit']['stage'])].append(r)
    return {'physical':summarize_records(records),
        'by_model_stage':[{'model_block':model,'stage':stage,**summarize_records(rows)}
            for (model,stage),rows in sorted(groups.items())],
        'logical_outputs':len(logical_outputs),'logical_origins':dict(Counter(r.get('origin','UNKNOWN') for r in logical_outputs)),
        'repeated_identical_wire_physical_calls':len(records)-len({r['request_sha256'] for r in records}),
        'identical_wire_is_not_assumed_independent_or_free':True,
        'slowest_terminal_requests':[{'unit':r['unit'],'status':r['status'],'elapsed_seconds':r['elapsed_seconds']}
            for r in sorted((r for r in records if r['status']!=PENDING and number(r.get('elapsed_seconds'))),
                key=lambda r:r['elapsed_seconds'],reverse=True)[:10]],
        'cache_tokens_not_counted_as_new_physical_tokens':True,
        'unit_prices_available':False,'unknown_usage_is_not_zero':True,
        'configured_caps_are_not_billing_token_limits':True}
