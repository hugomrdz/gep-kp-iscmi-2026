#!/bin/sh
set -eu
V3_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$V3_ROOT"
export PYTHONPATH="$V3_ROOT"
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1 MPLBACKEND=Agg
export MPLCONFIGDIR="$V3_ROOT/tmp/matplotlib" NUMBA_CACHE_DIR="$V3_ROOT/tmp/numba"
export IPYTHONDIR="$V3_ROOT/tmp/ipython" JUPYTER_CONFIG_DIR="$V3_ROOT/tmp/jupyter-config"
export JUPYTER_PATH="$V3_ROOT/jupyter/share/jupyter"
mkdir -p "$MPLCONFIGDIR" "$NUMBA_CACHE_DIR" "$IPYTHONDIR" "$JUPYTER_CONFIG_DIR"
case "${1:-help}" in
  test) shift; exec .venv/bin/python -m pytest -q tests revision_comparison/tests "$@" ;;
  kernel)
    .venv/bin/python -m ipykernel install --prefix "$V3_ROOT/jupyter" --name iscmi2026-v3 --display-name 'Python (ISCMI 2026 V3)'
    exec .venv/bin/python -m ipykernel install --prefix "$V3_ROOT/jupyter" --name iscmi2026-v2 --display-name 'Python (historical V2 notebook, V3 environment)' ;;
  paper) exec ./iscmi2026_submission_HugoMoreno/build.sh ;;
  prepare|freeze|run|verify|table|verify-inherited|verify-v2)
    exec .venv/bin/python -m revision_comparison.study "$@" ;;
  *) echo 'Usage: ./v3.sh {test|kernel|paper|prepare|freeze|run|verify|table|verify-inherited|verify-v2 --v2 PATH}' ;;
esac
