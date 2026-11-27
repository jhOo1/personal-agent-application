#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/../../.."
b=reports/qamc_contextual_match_v2_20261112
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="src:.:scripts:$b/authority_compilation_v1:$b/decision_visibility_v42:$b/counterfactual_decision_v41:$b/decision_edit_preflight:$(find "$b" -mindepth 1 -maxdepth 1 -type d | sort | paste -s -d : -)"
exec ../qamc/.venv/bin/python "$b/spanish_app_joint_diagnostic_v1/run.py" "$@"
