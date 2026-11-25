"""Zero-model baseline inventory. Hash original artifacts without modifying them."""
import argparse
import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'reports/qamc_bace_20261105'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, obj):
    """Never silently replace a freeze."""
    text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    with path.open('x') as stream:
        stream.write(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-api', action='store_true', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = OUT / 'BASELINE_FILES.json'
    if args.verify:
        rows = json.loads(freeze.read_text())
        changed = [r['path'] for r in rows if not (ROOT/r['path']).is_file()
                   or digest(ROOT/r['path']) != r['sha256']]
        print(json.dumps({'checked':len(rows), 'changed':changed}))
        if changed:
            raise SystemExit(1)
        return
    if freeze.exists():
        raise SystemExit('Baseline already frozen; use --verify.')
    rows, ledgers = [], []
    for dirname in ('src', 'prompts', 'configs', 'tests', 'scripts', 'tools', 'reports', 'runs', 'data'):
        for path in sorted((ROOT/dirname).rglob('*')):
            rel = path.relative_to(ROOT).as_posix()
            if not path.is_file() or path.is_symlink() or any(x in rel for x in (
                    '__pycache__', '/qamc_bace_20261105/', '/bace/', 'test_bace', '.pyc')):
                continue
            # Live locks and SQLite shared-memory are not immutable evidence.
            if path.name.endswith(('.lock', '-shm')):
                continue
            stat = path.stat()
            rows.append({'path':rel, 'size':stat.st_size, 'sha256':digest(path)})
            if path.name == 'ledger.sqlite' and path.parent.name == 'api':
                with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
                    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if 'requests' not in tables:
                        continue
                    counts=Counter(); unknown=0; errors=[]
                    for request_id, data in db.execute('SELECT request_id,data FROM requests'):
                        r=json.loads(data); counts[r.get('status','missing')]+=1
                        unknown += r.get('usage') is None
                        if r.get('status') != 'ok':
                            errors.append({'request_id':request_id,'status':r.get('status'),
                                           'error':r.get('error'),'payload_sha':r.get('payload_sha')})
                    ledgers.append({'path':rel,'statuses':dict(counts),'unknown_usage':unknown,'errors':errors})
    write_new(freeze, rows)
    write_new(OUT/'BASELINE_LEDGER_INVENTORY.json', ledgers)
    write_new(OUT/'BASELINE_GIT.json', {
        'utc':datetime.now(timezone.utc).isoformat(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
        'files':len(rows),'bytes':sum(r['size'] for r in rows),
        'new_model_requests':0,'ledger_counts_are_per_file_not_deduplicated_lifetime_total':True})
    print(json.dumps({'frozen_files':len(rows),'ledger_files':len(ledgers),'new_model_requests':0}))


if __name__ == '__main__':
    main()
