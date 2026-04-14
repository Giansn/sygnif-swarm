#!/usr/bin/env bash
set -euo pipefail
_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export SYGNIF_REPO_ROOT="${SYGNIF_REPO_ROOT:-$_REPO_ROOT/BTC_Prediction}"
export PYTHONPATH="${SYGNIF_REPO_ROOT}/prediction_agent:${SYGNIF_REPO_ROOT}/finance_agent:${SYGNIF_REPO_ROOT}/trade_overseer${PYTHONPATH:+:${PYTHONPATH}}"
echo "SYGNIF_REPO_ROOT=$SYGNIF_REPO_ROOT"
