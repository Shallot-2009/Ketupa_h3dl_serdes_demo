#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/script/run_python.sh" "$ROOT/script/01_Netlist.py" "$@"
