#!/usr/bin/env bash
# Quick visual demonstration (about 2 minutes, no statistics): the fixed demo scenario in SUMO-GUI.
# Traffic with live DBSCAN clusters -> one accident -> committee vote and BLS certificate -> flooding (the
# storm) -> the proposed scheme -> RSU validation -> a forged alert being rejected.
# Usage: ./run_demo.sh                 both schemes, presentation pace
#        ./run_demo.sh --pace 0.8      slower;   --scheme proposed   one scheme only;   --no-forged
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || { echo "ERROR: SUMO-GUI needs a graphical display (DISPLAY is not set)." >&2; exit 1; }
$PY -c "import sumo, traci" 2>/dev/null || { echo "ERROR: SUMO is not installed in .venv. Run: .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
exec $PY run.py demo --shots results/figures "$@"
