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
entry=trial.py
case "${1:-}" in
  summarize) entry=summarize.py; shift ;;
  feedback) entry=feedback.py; shift ;;
  audit-plans) entry=audit_plans.py; shift ;;
  rpe-stage) entry=rpe_stage.py; shift ;;
  external-rpe-stage) entry=external_rpe_stage.py; shift ;;
  external-delivery-stage) entry=external_delivery_stage.py; shift ;;
  self-recheck) entry=self_recheck.py; shift ;;
  task-only) entry=task_only.py; shift ;;
  task-only-audit) entry=task_only_audit.py; shift ;;
  crossover) entry=crossover.py; shift ;;
  crossover-audit) entry=crossover_audit.py; shift ;;
  selected-planning) entry=selected_planning.py; shift ;;
  selected-planning-audit) entry=selected_planning_audit.py; shift ;;
  selected-rpe-stage) entry=selected_rpe_stage.py; shift ;;
  factorial) entry=factorial.py; shift ;;
  expansion-audit) entry=expansion_inventory.py; shift ;;
  expansion-run) entry=expansion_run.py; shift ;;
  expansion-summary) entry=expansion_summary.py; shift ;;
  expansion-persist-peer) entry=expansion_persist_peer.py; shift ;;
  exposure-controls) entry=exposure_controls.py; shift ;;
  joint-context) entry=joint_context.py; shift ;;
  joint-context-headroom) entry=joint_context_headroom.py; shift ;;
  pinned-actor-transfer) entry=pinned_actor_transfer.py; shift ;;
  pinned-transfer-readout) entry=pinned_transfer_readout.py; shift ;;
  first-pass-inventory) entry=first_pass_inputs.py; shift ;;
  first-pass-fit) entry=first_pass_fit.py; shift ;;
  first-pass-readout) entry=first_pass_readout.py; shift ;;
  first-pass-iteration) entry=first_pass_iteration.py; shift ;;








  exposure-summary) entry=exposure_summary.py; shift ;;
  expansion-audit-requests) entry=expansion_audit.py; shift ;;
  evolution-feedback) entry=evolution_feedback.py; shift ;;
  actor-mutation) entry=mutate_actor.py; shift ;;
  mutation-audit) entry=mutation_audit.py; shift ;;
  mutation-stage) entry=mutation_stage.py; shift ;;
  source-sensitivity) entry=source_group_sensitivity.py; shift ;;
esac
exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/evo_qamc_fit_v1/$entry" "$@"
