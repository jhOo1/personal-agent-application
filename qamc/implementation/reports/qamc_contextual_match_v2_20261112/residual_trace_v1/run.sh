#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
base=reports/qamc_contextual_match_v2_20261112
export PYTHONPATH="src:.:scripts"
for d in residual_trace_v1 decision_release_v1 downstream_memory_utility_v1 transactional_reassembly_v1 execution_feedback_policy_v1 strong_actor_boundary_audit_v1 anchored_decision_patch_v1 ipe_c_full_exposed_panel_v1 decision_visibility_v42 counterfactual_decision_v41 decision_edit_preflight; do
  PYTHONPATH="$PYTHONPATH:$base/$d"
done
PYTHONPATH="$PYTHONPATH:$(find "$base" -mindepth 1 -maxdepth 1 -type d | sort | paste -s -d : -)"
export PYTHONDONTWRITEBYTECODE=1
case "${1:-}" in
  audit) exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/residual_trace_v1/audit.py" ;;
  recover|replay) exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/residual_trace_v1/recover_bench_grading.py" "$@" ;;
esac
exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/residual_trace_v1/run_bench_add.py" "$@"
