from __future__ import annotations
import ast,hashlib,json,os,urllib.request,urllib.error
from pathlib import Path
REFERENCE=Path("/Users/haomin/Desktop/code/distill/utils.py")

def read_reference(path=REFERENCE):
    """Read literal annotate_once defaults without executing the source file."""
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'annotate_once')
    values = {a.arg: ast.literal_eval(v) for a, v in zip(fn.args.kwonlyargs, fn.args.kw_defaults)
              if a.arg in ('base_url', 'api_key', 'app', 'quota_id', 'user_id', 'access_key')}
    required = {'base_url', 'api_key', 'app', 'quota_id', 'user_id', 'access_key'}
    if set(values) != required or any(not isinstance(v, str) or not v for v in values.values()):
        raise ValueError('reference_defaults_incomplete')
    if not values['base_url'].startswith('https://'):
        raise ValueError('https_endpoint_required')
    return values, hashlib.sha256(source.encode()).hexdigest()

def sanitize(value, config):
    """Remove authentication data and returned private reasoning from saved data."""
    secrets = [v for k, v in config.items() if len(v) >= 4]
    private = {'authorization', 'api_key', 'access_key', 'quota_id', 'user_id',
               'reasoning_content', 'reasoning', 'thinking', 'headers'}
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key.lower() in private:
                out[key] = '[REDACTED]' if item is not None else None
            else:
                out[key] = sanitize(item, config)
        return out
    if isinstance(value, list):
        return [sanitize(item, config) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, '[REDACTED]')
    return value

def atomic_json(path, value):
    """Commit each ledger change before the next network or tool operation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    tmp.replace(path)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'redirect_not_allowed', headers, fp)