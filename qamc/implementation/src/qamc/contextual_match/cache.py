"""Service-aware filtering layered on the existing exact-wire inventory."""
import json
from pathlib import Path


def service_filtered(root, index, wanted, reference_sha256):
    result={**index,"records":[],"other_service_records":[],"unknown_service_records":[]}
    for row in index["records"]:
        if row["body_sha256"] not in wanted:continue
        path=Path(row["request_path"]) if row.get("request_path") else None
        if path is not None and not path.is_absolute():path=Path(root)/path
        record=path.with_name("record.json") if path is not None else None
        service=None
        if record is not None and record.exists():
            service=json.loads(record.read_text()).get("reference_config_sha256")
        if service==reference_sha256:
            result["records"].append(row)
        elif service is not None:
            # A different service configuration is a different experiment block.
            result["other_service_records"].append(row)
        else:
            # Do not reuse unverifiable outputs, or blindly resend ambiguous work.
            blocked={**row,"status":"PRIOR_METADATA_ONLY_DELIVERY_UNRESOLVED"}
            result["unknown_service_records"].append(row)
            result["records"].append(blocked)
    result["service_reference_sha256"]=reference_sha256
    return result
