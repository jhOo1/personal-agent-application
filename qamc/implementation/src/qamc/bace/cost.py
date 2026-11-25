"""Read-only physical-request accounting, including failures and repairs."""
import json
import sqlite3
from collections import Counter,defaultdict
from datetime import datetime,timezone
from .audit import OUT
from .prepare import RUN
from qamc.transport_helpers import atomic_json


def summarize(rows,events,cap):
    pending=[r for r in rows if r['status']=='pending_delivery_unknown']
    terminal=[r for r in rows if r['status']!='pending_delivery_unknown']
    tokens={}
    for field in ('prompt_tokens','completion_tokens','total_tokens'):
        values=[(r.get('usage') or {}).get(field) for r in terminal]
        known=[v for v in values if type(v) is int and v>=0]
        tokens[field]={'known_sum':sum(known),'known_terminal_requests':len(known),
                       'unknown_terminal_requests':len(values)-len(known)}
    groups=defaultdict(list)
    for row in rows:
        key=row.get('key','')
        stage='assessment' if '/assessment/' in key else 'proposal' if '/proposal/' in key else 'other'
        role='allow' if '/allow' in key else 'deny' if '/deny' in key else 'other'
        groups[stage+'/'+role].append(row)
    parts={}
    for name,part in sorted(groups.items()):
        latency=[r['latency_seconds'] for r in part
                 if r['status']!='pending_delivery_unknown' and isinstance(r.get('latency_seconds'),(int,float))]
        parts[name]={'requests':len(part),'statuses':dict(Counter(r['status'] for r in part)),
                     'contract_repair_requests':sum('/contract_repair' in r.get('key','') for r in part),
                     'latency_seconds_sum':sum(latency),'latency_known_requests':len(latency)}
    return {'physical_requests':len(rows),'pending_requests':len(pending),
            'terminal_statuses':dict(Counter(r['status'] for r in terminal)),
            'request_cap':cap,'remaining_dispatch_slots':max(0,cap-len(rows)),
            'tokens':tokens,'groups':parts,'event_statuses':dict(Counter(e['status'] for e in events)),
            'transport_success_is_not_contract_or_semantic_success':True,
            'latency_sum_is_not_wall_time':True,'pending_rows_do_not_prove_liveness':True}


def main():
    path=RUN/'api/ledger.sqlite'
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        # One consistent SQLite read transaction, without touching live request state.
        db.execute('BEGIN')
        rows=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
        events=[json.loads(r[0]) for r in db.execute('SELECT data FROM events ORDER BY id')]
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text())
    result=summarize(rows,events,plan['request_cap'])
    result['observed_utc']=datetime.now(timezone.utc).isoformat()
    result['new_model_requests_by_report']=0
    atomic_json(OUT/'COST_LEDGER_LIVE.json',result)
    lines=['# BACE 请求成本快照','',f"观察时间：{result['observed_utc']}",'',
           f"物理请求 {len(rows)}；待定 {result['pending_requests']}；有限 Pilot 上限 {plan['request_cap']}。",
           '缓存不计新请求；失败与结构修复计入物理请求。待定记录不证明进程存活。','',
           '|类别|请求数|结构修复请求|已知请求延迟之和（秒）|','|---|---:|---:|---:|']
    for key,value in result['groups'].items():
        lines.append(f"|{key}|{value['requests']}|{value['contract_repair_requests']}|{value['latency_seconds_sum']:.3f}|")
    lines+=['','请求延迟之和不是并行墙钟耗时。传输成功不代表结构校验通过，更不代表语义正确。','',
            '|服务返回的 Token 字段|已知合计|已结束但该字段未知的请求|','|---|---:|---:|']
    for key,value in result['tokens'].items():
        lines.append(f"|{key}|{value['known_sum']}|{value['unknown_terminal_requests']}|")
    lines+=['','未对待定请求估算 Token，也不把未知用量记成零。服务返回的 usage 不等于可见答案字符数。',
            '模型身份仅记录所请求及返回的别名，不认证后端权重。完整账本包含原始请求参数和返回别名。',
            '本快照可更新；原始记录及阶段归档保留。']
    (OUT/'COST_LEDGER_LIVE.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'requests':len(rows),'pending':result['pending_requests'],'new_model_requests':0}))


if __name__=='__main__':main()
