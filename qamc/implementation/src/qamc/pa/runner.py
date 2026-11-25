"""Offline audit entrypoint. Live stages are gated until protocol lock is complete."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from .core import rpeval_public, digest
from .rpeval_scoring import load_rubrics

ROOT = Path(__file__).resolve().parents[3]


def audit():
    upstream = ROOT/'literature/qamc_pa_v1/RPEval'
    output = ROOT/'reports/qamc_pa_v1'
    output.mkdir(exist_ok=True)
    datasets = {}; questions = {}; payloads = 0
    for path in sorted((upstream/'benchmark_dataset').glob('*/*.json')):
        rows = json.loads(path.read_text()); key = str(path.relative_to(upstream))
        hashes = []
        for index, row in enumerate(rows):
            public = rpeval_public(row, f'{key}:{index}', implicit='implicit_preference' in key)
            hashes.append(digest(public.payload())); payloads += 1
            questions.setdefault(' '.join(row['question'].split()), []).append(f'{key}:{index}')
        datasets[key] = {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'rows':len(rows),
                         'public_payload_hashes':hashes}
    rubrics = load_rubrics(upstream/'prompts/prompts_715.py')
    for name, text in rubrics.items(): (output/(name+'.txt')).write_text(text)
    report = {'upstream_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip(),
              'datasets':datasets,'public_inputs_validated':payloads,
              'exact_question_groups':len(questions),'lineage_status':'EXACT_ONLY_NOT_SEMANTICALLY_CERTIFIED',
              'rubric_hashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in rubrics.items()},
              'protocol_status':'ADAPTED_PENDING_FULL_LOCK','new_model_calls':0,
              'legacy_stop_present':(ROOT/'runs/qamc_bace_v2/api/STOP').exists()}
    (output/'RPEVAL_OFFLINE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in {'datasets','rubric_hashes'}}))


def main():
    parser = argparse.ArgumentParser();parser.add_argument('stage',choices=['audit'])
    parser.parse_args();audit()

if __name__ == '__main__': main()
