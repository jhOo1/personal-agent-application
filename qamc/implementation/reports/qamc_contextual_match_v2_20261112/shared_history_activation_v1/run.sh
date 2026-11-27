#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
base=reports/qamc_contextual_match_v2_20261112
export PYTHONPATH="src:.:scripts"
for name in persist_selected_gepa_completion_v1 persist_equal_cap_safety_v1 persist_repeated_deployment_v1 native_residual_v1 matched_alternative_rpeval_v1 candidate_distribution_rpeval_v1 operand_generation_v1 bench_relation_compiler_v1 benchpres_repeat_matched_v1 rpe_decision_delta_v21 rpe_protected_repair_v2 rpe_constraint_veto_v1 rpe_heterogeneous_reward_v1 rpe_heterogeneous_reward_v1/settlement rpe_single_endpoint_bridge_v1 bench_expression_realization_v1 decision_release_v1 downstream_memory_utility_v1 transactional_reassembly_v1 execution_feedback_policy_v1 strong_actor_boundary_audit_v1 anchored_decision_patch_v1 ipe_c_full_exposed_panel_v1 decision_visibility_v42 counterfactual_decision_v41 decision_edit_preflight; do
  PYTHONPATH="$PYTHONPATH:$base/$name"
done
PYTHONPATH="$PYTHONPATH:$(find "$base" -mindepth 1 -maxdepth 1 -type d | sort | paste -s -d : -)"
export PYTHONDONTWRITEBYTECODE=1
exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/shared_history_activation_v1/bridge.py" "$@"
