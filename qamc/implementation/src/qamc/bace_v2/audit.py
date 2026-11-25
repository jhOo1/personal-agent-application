"""Snapshot pre-existing project files without changing their contents."""
import argparse
import json
from pathlib import Path
from qamc.bace.audit import digest, write_new
from qamc.common import ROOT

OUT = ROOT / 'reports/qamc_bace_v2'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--verify', action='store_true')
    args = parser.parse_args(); OUT.mkdir(exist_ok=True)
    path = OUT / 'BASELINE_FILES.json'
    if args.verify or path.exists():
        rows = json.loads(path.read_text())
        changed = [r['path'] for r in rows if not (ROOT/r['path']).is_file() or digest(ROOT/r['path']) != r['sha256']]
        print(json.dumps({'checked': len(rows), 'changed': changed, 'new_model_calls': 0}))
        if changed: raise SystemExit(1)
        return
    rows = []
    for dirname in ('src','prompts','configs','tests','scripts','tools','reports','runs','data'):
        for p in sorted((ROOT/dirname).rglob('*')):
            rel = p.relative_to(ROOT).as_posix()
            if not p.is_file() or p.is_symlink(): continue
            if any(x in rel for x in ('/bace_v2/', '/qamc_bace_v2/', 'test_bace_v2', 'run_qamc_bace_v2', '__pycache__')): continue
            if p.name.endswith(('.pyc', '.lock', '-shm')): continue
            rows.append({'path': rel, 'size': p.stat().st_size, 'sha256': digest(p)})
    write_new(path, rows)
    print(json.dumps({'frozen_files': len(rows), 'new_model_calls': 0}))


if __name__ == '__main__': main()
