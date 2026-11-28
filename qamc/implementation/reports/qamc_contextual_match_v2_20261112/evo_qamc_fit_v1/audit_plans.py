"""Summarize completed plan exposure and cost without reading gold or Judge output."""
from collections import Counter, defaultdict
from statistics import median
import json
import sys

from trial import RUN, POLICIES, sha


def read(path):
    return json.loads(path.read_text())


def audit(run):
    panel = read(run/'private/FROZEN.json')
    planned = {row['uid']: row for row in panel['rows']}
    records = {}
    answers = {}
    totals = defaultdict(Counter)
    lengths = defaultdict(list)
    for path in (run/'Plan/visible').glob('*/record.json'):
        receipt = read(path)
        unit = receipt['unit']
        uid, arm = unit['root_id'], unit['method']
        key = uid, arm
        card = planned[uid]
        wire = read(path.with_name('request.json'))
        assert sha(wire) == receipt['request_sha256'] == card['plan_request_hashes'][arm]
        assert key not in records
        records[key] = receipt
        public = json.loads(wire['messages'][1]['content'])
        assert public == card['payload']
        assert receipt['automatic_retries'] == 0
        stats = totals[(card['domain'], arm)]
        stats[receipt['status']] += 1
        usage = (receipt.get('usage') or {}).get('total_tokens')
        stats['reported_tokens'] += usage or 0
        stats['unknown_usage'] += usage is None
        if receipt['status'] == 'OK':
            text = read(path.with_name('response.json'))['answer']
            answers[key] = sha(text)
            lengths[(card['domain'], arm)].append(len(text))
    paired = defaultdict(Counter)
    left, right = POLICIES
    for uid, card in planned.items():
        if (uid,left) in answers and (uid,right) in answers:
            counter = paired[card['domain']]
            counter['valid_pairs'] += 1
            counter['identical_plan_text'] += answers[uid,left] == answers[uid,right]
    assigned = len(planned)*len(POLICIES)
    pending = sum(r['status']=='PENDING_DELIVERY_UNKNOWN' for r in records.values())
    return dict(assigned=assigned, registered=len(records), pending=pending,
                published_terminal=assigned==len(records) and pending==0,
                paired={k:dict(v) for k,v in sorted(paired.items())},
                arms={'/'.join(key):dict(counts, median_plan_characters=median(lengths[key]) if lengths[key] else None)
                      for key,counts in sorted(totals.items())})


if __name__ == '__main__':
    result = audit(RUN)
    if '--completed' in sys.argv and not result['published_terminal']:
        raise SystemExit('Plan stage is still live')
    print(json.dumps(result,indent=2))
