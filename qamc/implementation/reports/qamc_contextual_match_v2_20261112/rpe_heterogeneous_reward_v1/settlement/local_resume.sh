#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
name=rpe_heterogeneous_reward_v1
namespace=qamc_contextual_match_v2_20261112
workdir="runs/$namespace/$name"
revision=853c9e6e0f71862785dd0b8eefca9609f8e720cb
snapshot="${QAMC_REWARD_SNAPSHOT:-${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}/models--internlm--internlm2-7b-reward/snapshots/$revision}"
runtime="${QAMC_REWARD_PYTHON:-$HOME/.cache/qamc/internlm2-reward-reuse-torch/bin/python}"
experiment="reports/$namespace/$name"
export PYTHONPATH="$experiment" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
exec "$runtime" -u "$experiment/settlement/run_reward_mps.py" "$workdir" "$snapshot"
