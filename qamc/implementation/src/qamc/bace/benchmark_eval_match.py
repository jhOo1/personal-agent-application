"""Match evaluation rows by query AND source profile, never by labels."""
import re
import unicodedata


def normalized_source(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip()


def benchpres_row(payload,rows):
    sources=[normalized_source(u['exact_text']) for u in payload['units'] if u['unit_id']!='Q0']
    if not sources:raise ValueError('Cannot match BenchPreS without profile evidence')
    matches=[]
    for index,row in enumerate(rows):
        profile,tail=row['prompt'].split('\n\nWrite a complete message to recipient',1)
        if payload['query']!='Write a complete message to recipient'+tail:continue
        profile=normalized_source(profile)
        if all(source in profile for source in sources):matches.append(index)
    if len(matches)!=1:
        raise ValueError('Expected exactly one query-and-profile evaluation row; found '+str(len(matches)))
    return matches[0],rows[matches[0]]
