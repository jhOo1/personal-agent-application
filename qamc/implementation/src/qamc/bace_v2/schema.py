"""Sparse organizer contract, supplied without any benchmark reference."""
ORGANIZER_SCHEMA = {
    'task_frame': {'goal': 'current requested task, not an answer', 'requester': 'user or unknown',
        'beneficiary': 'supported target or unknown', 'recipient': 'supported recipient or unknown',
        'output_parts': [{'part_id': 'part1', 'scope_id': 'scope1', 'description': 'requested part',
                          'query_refs': ['provided query span ID']}],
        'requirements': [{'text': 'requirement', 'basis': 'EXPLICIT|CONTEXT_INFERENCE',
                          'query_refs': ['provided query span ID']}]},
    'preferences': [{'preference_id': 'local alias P1', 'source_ids': ['provided historical span ID'],
        'subject': 'source-supported subject', 'kind': 'preference type',
        'status': 'EXPLICIT|SUPPORTED_IMPLICIT|UNCERTAIN', 'scope_note': 'source-supported scope',
        'uncertainty': 'uncertainty or empty string'}],
    'fact_candidates': [{'source_ids': ['provided historical span ID'], 'task_relation': 'concrete relevance'}],
    'uncertain_source_ids': [], 'unreviewed_source_ids': [],
    'proposed_uses': [{'preference_id': 'local alias P1', 'source_ids': ['same preference evidence ID'],
        'scope_id': 'scope1', 'part_id': 'part1', 'target': 'affected subject',
        'effect': 'concrete influence, never the final answer or option ranking',
        'role': 'PERSONAL_RANKING|PLAN_ADAPTATION|STYLE_ADAPTATION|USER_HISTORY|FACT_EVIDENCE',
        'conditions': [], 'query_refs': ['provided query span ID']}],
    'no_use': [{'preference_id': 'alias without proposed use', 'reason': 'why no concrete use can be proposed'}]
}
