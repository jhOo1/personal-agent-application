"""Bind runtime dependencies and prepared input identities before dispatch."""
import json
from qamc.common import ROOT
from qamc.bace.audit import digest, write_new
from .audit import OUT


def current():
    paths=set()
    for directory,pattern in [('src/qamc','*.py'),('prompts','*.md')]:
        paths.update((ROOT/directory).rglob(pattern))
    for name in ['DATA_MANIFEST_V2.json','SMOKE_INPUTS.json','OPT_INPUTS.json','PROTOCOL.yaml','DISPATCH_LIMITS.json']:
        paths.add(OUT/name)
    paths.add(ROOT/'scripts/run_qamc_bace_v2.sh')
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}


def verify():
    path=OUT/'RUNTIME_FREEZE.json'
    if not path.exists():raise ValueError('Runtime not frozen; no real dispatch')
    previous=json.loads(path.read_text())
    if previous!=current():raise ValueError('Runtime drift; reconcile before further dispatch')


def main():
    path=OUT/'RUNTIME_FREEZE.json'
    if path.exists():verify()
    else:write_new(path,current())
    print('Runtime freeze verified; zero model calls.')


if __name__=='__main__':main()
