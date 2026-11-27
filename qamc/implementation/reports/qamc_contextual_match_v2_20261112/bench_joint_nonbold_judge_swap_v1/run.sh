#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
base=reports/qamc_contextual_match_v2_20261112
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="src:.:scripts:$base/benchpres_repeat_matched_v1"
exec "${QAMC_PYTHON:-../qamc/.venv/bin/python}" "$base/bench_joint_nonbold_judge_swap_v1/swap.py"
