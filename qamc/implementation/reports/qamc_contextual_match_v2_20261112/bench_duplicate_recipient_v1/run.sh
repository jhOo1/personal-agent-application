#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
base=reports/qamc_contextual_match_v2_20261112
export PYTHONPATH="src:.:scripts"
for name in native_residual_v1 source_local_reentry_v1 rpe_constraint_veto_v1 rpe_heterogeneous_reward_v1 rpe_heterogeneous_reward_v1/settlement rpe_single_endpoint_bridge_v1 bench_expression_realization_v1 decision_release_v1 downstream_memory_utility_v1 transactional_reassembly_v1 execution_feedback_policy_v1 strong_actor_boundary_audit_v1 anchored_decision_patch_v1 ipe_c_full_exposed_panel_v1 decision_visibility_v42 counterfactual_decision_v41 decision_edit_preflight; do
  PYTHONPATH="$PYTHONPATH:$base/$name"
done
PYTHONPATH="$PYTHONPATH:$(find "$base" -mindepth 1 -maxdepth 1 -type d | sort | paste -s -d : -)"
export PYTHONPATH="$base/bench_gate_gepa_feedback_v1:literature/qamc_gepa_optimizer/wheel_0_1_4:$PYTHONPATH"
export PYTHONDONTWRITEBYTECODE=1
exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/bench_duplicate_recipient_v1/trial.py" "$@"
