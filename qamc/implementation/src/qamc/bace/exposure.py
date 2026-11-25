"""Read-only exact public-text exposure scan over frozen historical requests."""
import json
import re
from collections import Counter, defaultdict
from .audit import ROOT, OUT, write_new, digest


def normalize(text):
    return re.sub(r'\s+',' ',text).strip().lower()


def strings(obj):
    if isinstance(obj,str):yield obj
    elif isinstance(obj,dict):
        for value in obj.values():yield from strings(value)
    elif isinstance(obj,list):
        for value in obj:yield from strings(value)


def main():
    import ahocorasick
    split=json.loads((OUT/'SPLITS_MANIFEST_V2.json').read_text())
    automaton=ahocorasick.Automaton();phrases=defaultdict(set)
    base=ROOT/'vendor/PrefEval/benchmark_dataset'
    for row in split['prefeval']:
        for folder in ('explicit_preference','implicit_preference/choice-based',
                       'implicit_preference/persona-driven','mcq_options'):
            item=json.loads((base/folder/(row['topic']+'.json')).read_text())[row['index']]
            for field in ('preference','question'):
                phrases[normalize(item[field])].add((row['root_group'],field))
    for phrase,groups in phrases.items():automaton.add_word(phrase,tuple(sorted(groups)))
    automaton.make_automaton()
    manifest=json.loads((OUT/'BASELINE_FILES.json').read_text())
    requests=[r for r in manifest if r['path'].endswith('_request.json') and '/raw/' in r['path']]
    hits=[];errors=[]
    for row in requests:
        try:
            obj=json.loads((ROOT/row['path']).read_text())
            matched=set()
            for text in strings(obj):
                for _,groups in automaton.iter(normalize(text)):matched.update(groups)
            if matched:hits.append({'request':row['path'],'request_sha256':row['sha256'],
                'matched': [{'root_group':g,'field':f} for g,f in sorted(matched)]})
        except (ValueError,OSError) as exc:errors.append({'path':row['path'],'error':type(exc).__name__})
    exposed={x['root_group'] for h in hits for x in h['matched']}
    # HF viewer excerpts in this audit were visible to the implementing model.
    # Conservatively quarantine the entire two displayed education topics.
    visible_topics={'education_learning_styles','education_resources'}
    exposed.update(r['root_group'] for r in split['prefeval'] if r['topic'] in visible_topics)
    for row in split['prefeval']:
        if row['root_group'] in exposed:
            row['previous_split']=row['split'];row['split']='cal'
            row['exposure_status']='EXPOSED_PUBLIC_TEXT_OR_CURRENT_PROTOCOL_AUDIT'
        else:row['exposure_status']='NO_EXACT_SAVED_REQUEST_MATCH_NOT_SEMANTIC_PROOF'
    split['version']='bace-internal-group-split-v3'
    split['supersedes']=digest(OUT/'SPLITS_MANIFEST_V2.json')
    split['exposure_scan_errors']=len(errors)
    split['test_dispatch_authorized']=False
    report={'scanned_public_requests':len(requests),'matched_requests':hits,'errors':errors,
            'implementing_model_viewer_topics_quarantined':sorted(visible_topics),
            'exposed_roots':len(exposed),'counts':dict(Counter(r['split'] for r in split['prefeval'])),
            'limitation':'Exact string matching cannot detect paraphrased or unrecorded exposure.',
            'no_model_requests':True}
    write_new(OUT/'PREFEVAL_EXPOSURE_SCAN.json',report)
    write_new(OUT/'SPLITS_MANIFEST_V3.json',split)
    print(json.dumps({k:v for k,v in report.items() if k not in {'matched_requests','errors'}}))


if __name__=='__main__':main()
