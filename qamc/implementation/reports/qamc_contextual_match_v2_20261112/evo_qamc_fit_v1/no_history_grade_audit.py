"""Quantify native rubric errors on verified no-history Actor requests."""
from collections import Counter, defaultdict
import json

from exposure_summary import collect
from expansion_audit import manifest
from exposure_controls import OUT, assemble
from trial import sha


def audit():
    batches, _, _ = assemble()
    _, settled, groups, _, _, _ = collect()
    if settled != [1, 2, 3]:
        raise ValueError('Need all fixed-exposure batches')
    requests = {bundle['card']['uid']:bundle['actors'].get('OFF')
                for batch in batches for bundle in batch}
    attempted = {key:wire for i in settled for key,wire in
                 manifest(OUT/f'batch_{i}','Actor').items()}
    counts = defaultdict(Counter)
    sources = defaultdict(set)
    for card, cells, values in groups['RPEval']:
        uid, stratum = card['uid'], card['stratum']
        receipt, value, request = cells['OFF'], values['OFF'], requests[uid]
        labels = ('all_RPEval',stratum)
        for label in labels:
            counts[label]['assigned'] += 1
        if value is None:
            continue
        envelope = json.loads(request['messages'][1]['content'])
        if (set(envelope) != {'task','plan','source_evidence'} or envelope['source_evidence']
                or sha(request) != receipt['actor_request_sha256']
                or ((uid,'OFF') in attempted and attempted[uid,'OFF'] != request)):
            raise ValueError('No-history receipt does not match the verified no-history request')
        for label in labels:
            count = counts[label]
            count['graded'] += 1
            count['graded_positions'] += value['positions']
            count['match_positions'] += value['primary']
            count['not_perfect_match'] += value['primary'] != value['positions']
            count['positive_opb'] += value['OPB'] > 0
            count['positive_upb'] += value['UPB'] > 0
            no_current_facts = not envelope['task'].get('facts') and not envelope['task'].get('current_context')
            count['no_current_facts_or_context'] += no_current_facts
            count['positive_opb_no_current_facts_or_context'] += no_current_facts and value['OPB'] > 0
            count['known_score_flags'] += receipt.get('score_flags') != []
            if receipt.get('score_flags') == []:
                count['unflagged_graded'] += 1
                count['unflagged_positive_opb'] += value['OPB'] > 0
                count['unflagged_not_perfect_match'] += value['primary'] != value['positions']
            if value['OPB'] > 0:
                sources[label].add(card['group'])
    return {name:dict(values,positive_opb_source_groups=len(sources[name]))
            for name,values in counts.items()}


if __name__ == '__main__':
    print(json.dumps(audit(),indent=2))
