"""Verify applied instruction changes against every inherited generation wire."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from mutate_actor import inherited_wires
from mutation_contract import MODES, candidate_hash
from trial import sha


def read(path):
    return json.loads(path.read_text())


def audit(run):
    pin=read(run/'private/FROZEN.json')
    inherited=inherited_wires(pin['parent'])
    assert sha(inherited)==pin['wires_sha']
    spec=read(run/'private/INSTRUCTIONS.json')
    assert set(spec)==set(MODES)
    for key,record in spec.items():
        assert record['sha256']==candidate_hash(pin['parent'],record['instruction'],key)
    manifest=read(run/'private/Actor_MANIFEST.json')
    requests={}
    for entry in manifest['units']:
        uid,method=(entry['unit'][k] for k in ('root_id','method'))
        arm=method.removeprefix('MUTATE_')
        request=entry['request']
        parent=inherited[uid]
        expected_messages=[dict(parent['messages'][0],content=parent['messages'][0]['content']+
                      '\n\n'+spec[arm]['instruction']),*parent['messages'][1:]]
        assert request==dict(parent,messages=expected_messages)
        assert (uid,method) not in requests
        requests[uid,method]=request
    assert len(requests)==len(inherited)*len(MODES)
    receipt_status=Counter()
    for path in (run/'Actor/visible').glob('*/record.json'):
        rec=read(path)
        key=tuple(rec['unit'][x] for x in ('root_id','method'))
        assert rec['request_sha256']==sha(requests[key])
        assert rec['automatic_retries']==0
        receipt_status[rec['status']]+=1
    return dict(parent=pin['parent'],inherited_tasks=len(inherited),physical_actor_plan=len(requests),
                added_instructions=spec,receipt_status=receipt_status)


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('directory',type=Path)
    print(json.dumps(audit(cli.parse_args().directory),indent=2))
