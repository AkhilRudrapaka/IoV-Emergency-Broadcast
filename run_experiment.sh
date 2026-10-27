#!/usr/bin/env bash
# Reproduces every result from scratch (about 4 minutes on 16 cores):
#   environment check -> validation suite -> sensitivity sweeps -> SUMO-GUI screenshots -> main experiment
#   -> raw data, metrics, figures, summaries, dashboard under results/
# SKIP_GUI=1 ./run_experiment.sh skips the screenshot step (it opens a SUMO window for a few seconds).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    command -v python3 >/dev/null || { echo "ERROR: python3 is required." >&2; exit 1; }
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
PY=.venv/bin/python

echo "== 1/5 environment check =="
for module in numpy scipy sklearn matplotlib PIL py_ecc sumo sumolib traci pytest; do
    $PY -c "import $module" 2>/dev/null || {
        echo "ERROR: Python module '$module' is missing. Run: .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
done
$PY -c "import os, sumo, sys; sys.exit(not os.access(os.path.join(sumo.SUMO_HOME, 'bin', 'sumo'), os.X_OK))" || {
    echo "ERROR: the SUMO binary is missing from the eclipse-sumo package." >&2; exit 1; }
[ -f network/road.net.xml ] || { echo "ERROR: network/road.net.xml is missing." >&2; exit 1; }
echo "ok"

echo "== 2/5 validation suite =="
$PY -m pytest -q
echo "== 3/5 sensitivity sweeps (radio range, share of misbehaving vehicles) =="
$PY run.py sensitivity
echo "== 4/5 SUMO-GUI screenshots of the demo scenario =="
if [ -n "${SKIP_GUI:-}" ] || [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    echo "skipped (no display or SKIP_GUI set); the dashboard then shows the generated maps only"
else
    $PY run.py demo --pace 0 --no-wait --shots results/figures >/dev/null
    echo "saved to results/figures/sumo_*.png"
fi
echo "== 5/5 main experiment (5 densities x 30 seeds x 10 schemes, plus the forged-alert test) =="
$PY run.py experiment
echo "Done. Open results/dashboard.html   |   live demo: ./run_demo.sh"
