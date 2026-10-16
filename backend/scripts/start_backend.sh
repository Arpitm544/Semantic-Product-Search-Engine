#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
exec .venv/bin/python -u api/main.py
