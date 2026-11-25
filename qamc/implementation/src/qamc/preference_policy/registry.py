"""Benchmark acceptance and usage gates are separate from dataset availability."""

def require(registry, benchmark, purpose='evaluation'):
    entry=registry[benchmark]
    if entry['status'] not in {'published','accepted'} or not entry.get('evidence_url') or not entry['allowed_for_new_runs']:
        raise ValueError('benchmark acceptance unverified or use disabled')
    if entry['track']=='workshop' and purpose!='regression':
        raise ValueError('workshop excluded from main protocol')
    if purpose=='optimization' and not entry.get('allowed_for_policy_adaptation',False):
        raise ValueError('benchmark not admitted for policy adaptation')
    if not entry.get('license_checked') or not entry.get('source_revision'):
        raise ValueError('dataset version/license not checked')
    return entry
