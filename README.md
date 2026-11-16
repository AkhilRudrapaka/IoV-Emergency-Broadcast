# Trust-Aware Vehicular Emergency Alerts

A Python/SUMO research prototype for verified emergency-alert forwarding through vehicle clusters to roadside units (RSUs). It includes signed voting, BLS certificate verification, forwarding comparisons, saved results, a local web application, and a 12-section documentation portal.

The incident is staged in simulation. No real crash detection or live emergency dispatch is enabled by default.

**Final project report:** [`docs/Final_Project_Report.pdf`](docs/Final_Project_Report.pdf) — the complete workflow, every implemented algorithm, the comparison pairs replayed in SUMO-GUI, the multi-seed evaluation, genuine screenshots and the limitations. It is rebuilt from the project's own records with `python docs/final_report/build_final_report.py`.

## 1. What to copy to the other computer

Copy the **entire project folder**, including `network/`, `portal/`, `validation/`, and `results/` if you want the existing experiments. Keep the folder structure unchanged.

Do not copy a virtual environment from another computer. Create a fresh one using the steps below. Caches (`__pycache__`, `.pytest_cache`) and diagnostic logs are unnecessary.

Run every project command below from the folder containing `run.py` and `requirements.txt`, unless a step explicitly changes directory.

## 2. Prerequisites

- A 64-bit Python installation. Python 3.11 is the version used in the existing development environment; dependency installation must succeed before running the project.
- Internet access for initial dependency installation.
- A graphical desktop for the animated SUMO demo. The web application and headless experiments do not require a GUI.
- A modern web browser.
- Node.js is optional, used only for the static portal's JavaScript validation command.

The exact dependency pins are in `requirements.txt`, including Python-version-specific SciPy entries. SUMO, TraCI, and sumolib are installed through those requirements. The code locates SUMO through the Python `sumo` package, so a separate system-wide SUMO installation or manually configured `SUMO_HOME` is normally unnecessary.

## 3. Windows setup (PowerShell)

Install Python, then open PowerShell in the copied project folder. Replace the example path with the folder on your new computer:

```powershell
cd "C:\Projects\vehicular-emergency-alerts"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

If the Python launcher `py` is unavailable, use `python -m venv .venv` after checking `python --version`.

If PowerShell blocks activation, activation is optional. Run the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py web
```

For later commands, either activate the environment or replace `python` with `.\.venv\Scripts\python.exe`.

## 4. Linux / macOS setup

Use an installed Python interpreter compatible with the pinned dependencies:

```bash
cd /path/to/vehicular-emergency-alerts
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

On Linux, if virtual-environment creation reports that `venv` is missing, install your distribution's Python venv package first. If SUMO-GUI reports missing native libraries, install the libraries named in that error using your operating system's package manager. A desktop session is required for GUI commands; a headless server can run the CLI experiments and web app.

## 5. Verify the installation

With the virtual environment active, run:

```bash
python -c "import numpy, scipy, sklearn, matplotlib, py_ecc, sumo, sumolib, traci; print('Python dependencies OK'); print('SUMO package location:', sumo.SUMO_HOME)"
python -c "import os, subprocess, sumo; subprocess.run([os.path.join(sumo.SUMO_HOME, 'bin', 'sumo.exe' if os.name == 'nt' else 'sumo'), '--version'], check=True)"
python run.py --help
python -m pytest validation -q
```

The dependency check should print `Python dependencies OK`; the binary check should print a SUMO version. Tests exercise the simulator and web integration and can take some time.

## 6. Start the web application

In terminal 1, activate the environment and run:

```bash
python run.py web
```

Keep the terminal open and visit **http://127.0.0.1:8765/**.

| URL | What it shows |
| --- | --- |
| `http://127.0.0.1:8765/` | Faculty-demo dashboard (comparison pairs, separated runs, live view, outcome, comparison; section 7), the historical saved-results explorer and 12 project-documentation buttons |
| `http://127.0.0.1:8765/index.html` | Full documentation portal |
| `http://127.0.0.1:8765/simulation` | Standalone saved-results workspace |

The documentation buttons cover Home; Introduction and Background; Problem Statement; Objectives and Research Gap; Proposed System and Architecture; Methodology and Algorithms; Implementation and Technologies; Accident Simulation and Emergency Workflow; Results and Performance Evaluation; Source Code and Reproducibility; Research Papers and References; and Limitations and Future Work.

If the copied project has no saved runs, open **terminal 2**, activate the same environment, and generate one:

```bash
python run.py single -d 200 -r 2
```

After it finishes, open **Historical saved runs** at the bottom of the page and click **Refresh results**. While that section is open it checks for changed saved runs every five seconds and shows, for the selected run, every scheme side by side (frames, reach, t90, losses, suppression, RSU arrival and registration). While `python run.py demo` runs, a yellow **LIVE SUMO DEMO** strip in that section mirrors the replay's counters once per second (`/api/live`, read from the recorded channel log).

Stop the server with **Ctrl+C**. After changes to `web_results.py`, stop and restart it. If port 8765 is occupied:

```bash
python run.py web --port 8766
```

Then open `http://127.0.0.1:8766/`. The server binds to localhost; it is intended for use on the same computer.

## 7. Run the visual SUMO demo

In a separate terminal with the environment active:

```bash
python run.py demo
```

A workflow indicator at the top highlights the active stage (Incident → Alert → Cluster / CH → Votes → Certificate → Forwarding / Route → RSU) with a one-line factual status read from the run record; ordinary traffic stays grey and only the incident, cluster heads, what was on air in the 0.5 ms of radio time each frame shows, the traversed CH route and RSU outcomes are coloured (legend on the right). To refresh the portal's SUMO Demonstration snapshots, run `python run.py demo --shots portal/assets/sumo` on a Windows desktop (it captures the SUMO window at each stage and writes `snapshots.json`/`snapshots.js`). The GUI shows: live SUMO traffic; the committee vote; the same alert under blind flooding, the proposed scheme and the CH-to-CH route (planned route drawn in purple); RSU decode/validation; and a forged alert being rejected. The radio events last tens of milliseconds, so **SUMO's clock is paused at the incident second** while they are replayed in slow motion (the GUI is repainted without simulation steps; no vehicle is stopped artificially). Afterwards the clock resumes: the crashed vehicle stays stopped and every other vehicle continues from its own speed. The heading states that the radio is a **simulated 802.11p model**. Every link, ring and counter comes from the recorded channel log, and the demo asserts that the GUI state and the final counters equal the recorded run. Keep `python run.py web` running in another terminal to watch the live counters in the browser.

Useful options:

```bash
python run.py demo --scheme proposed
python run.py demo --pace 0.8
python run.py demo --no-wait
```

Running `python run.py` without a subcommand also starts the demo. On a machine without a graphical display, use `single` or `explain` instead.

The demo first re-simulates its seed and saves that run: `results/urban/raw/d200_r02.json.gz` is rewritten (the same run, with a new `recorded_at`), a timestamped copy is added, the local dispatch outbox `results/urban/infrastructure/backhaul.sqlite3` is updated, SUMO-GUI's error log `results/urban/sumo_gui_errors.log` is rewritten and the live feed `results/urban/live_demo.json` is written. To watch it without touching these files, set `EXP_RESULTS_DIR` to another folder first.

**Which incident the demo shows.** `python run.py demo` always replays one showcase scenario, `d200_r02` (vehicle v164 at t = 114 s), set by `config.DEMO_DENSITY` and `DEMO_RUN` and chosen once by the rule in `config.py`; the SUMO window labels it *fixed showcase scenario*. `python run.py demo -r 7` replays seed 7 instead, with its own incident. Every seed has its own incident, drawn from that seed in `scenario.build`: a random honest vehicle at a random second between 60 and 120 s. The same seed always gives the same incident, different seeds give different ones (the 180 runs of the experiment matrix have 30 different incidents per density), and every run writes its own record. Comparison pairs (below) draw their scenarios from these seeds.

### Faculty demo: the baseline only, then the proposed method only

For a presentation, use a **comparison pair**: one incident scenario replayed twice in SUMO-GUI, one approach per run and never both on one map, then compared on the identical run record.

1. Start `python run.py web` and open `http://127.0.0.1:8765/`. In section 2 (*Scenario & approach*), **New pair** takes the next scenario in this pairs folder's own order, whose incident lies on the road network and at least 50 m from every incident already used (a reused location is labelled as a repeat). The order is shuffled by the folder's selection seed, drawn at random when its first pair is made and kept in `results/demo_pairs/selection.json`, so a new folder offers a different sequence of incidents and every pair records how it was chosen (selection seed and rank). **Run baseline only** and **Run proposed only** each open SUMO-GUI and play start to finish (about 1 minute for a baseline-only run, about 2 minutes for a proposed-only run). Only one run can be active at a time; pause/resume is not offered.
2. Section 3 shows the selected run live (stage indicator, SUMO and radio time, window captures of that run only), section 4 its outcome with units and definitions, and section 5 the side-by-side comparison once both runs have finished and their two records have the same fingerprint. The multi-seed experiment results are shown separately.
3. If a SUMO-GUI window ever stops responding (Windows marks it "Not Responding"; seen once in about 15 runs), close it: the run is then marked failed with the reason, and **Run proposed only again** (or baseline) repeats it on the same record. A window capture never waits more than 10 s for SUMO-GUI, so a frozen window cannot hold up a run through a capture.

The same from a terminal:

```bash
python run.py pair new                    # next scenario of this folder's order; options --baseline slotted1p, --scenario d200_r07
python run.py demo --pair P001 --approach baseline
python run.py demo --pair P001 --approach proposed
python run.py pair show P001              # scenario, run status and the comparison
```

The baselines are blind flooding (default), flooding + random delay, slotted 1-persistence and slotted 1-p + random delay. The proposed run replays the proposed scheme, then its CH-to-CH route stage (a stage of the proposed method, not a separate algorithm), then the forged-alert test. A scenario is one of the experiment's 30 seeds at 200 vehicles (`d200_rNN`, seed = 10000 + 100 × 200 + NN), so every scheme of a pair runs on the same network, traffic, incident and parameters. A pair writes only to `results/demo_pairs/<pair>/` (or `$DEMO_PAIRS_DIR`), never to the tracked results: `pair.json`, one console log per run, and one folder per run, `<pair>/baseline/` and `<pair>/proposed/`, each holding that run's own record (`raw/`), live feed, SUMO log, outbox and window captures, so the second run never overwrites the first. Pairs whose runs predate these per-run folders share one record in `<pair>/raw/`, which is still read. `python run.py demo` without `--pair` still runs the full walkthrough described above.

## 8. Generate research results

Start with a small experiment:

```bash
python run.py experiment --densities 50 100 200 250 --runs 3
```

For the complete configuration:

```bash
python run.py experiment
```

The current configuration uses populations 50, 100, 200, 250, 300, and 500 with 30 independent seeds per population. Full experiments and sensitivity sweeps can take substantially longer than a single run; there is no fixed runtime guarantee.

Outputs are written under `results/urban/`:

| Path | Contents |
| --- | --- |
| `raw/` | Saved compressed scenario records and historical runs |
| `processed/` | Per-run CSV data and aggregated comparisons |
| `figures/` | Charts, maps, and animations |
| `summaries/` | Result reports, explanations, and configuration metadata |
| `dashboard.html` | Generated experiment dashboard |
| `infrastructure/` | Local event database and export data |

Rebuild the dashboard from existing results:

```bash
python run.py dashboard
```

Open `results/urban/dashboard.html` in a browser. This command expects processed results and the configured demo record; run an experiment first on a clean copy.

Explain a saved record or inspect all schemes:

```bash
python run.py single -d 200 -r 2 --all
python run.py explain d200_r02 --scheme proposed
python run.py explain d200_r02 --forged voting_reputation
```

Experiments can replace aggregate CSVs and generated figures. Keep a backup of an earlier result set if it must be preserved. The seed rule is `BASE_SEED + 100 * density + run_index`; parameters live in `config.py`.

The checked-in `results/urban` set is the full 30-seed matrix generated on 2026-11-03 with the current network (RSUs at B3 (160, 590) and D1 (610, 170)); `summaries/experiment_config.json` records the git commit and a hash of the network file. Headline schemes: blind flooding, flooding + random delay, slotted 1-persistence, slotted 1-p + random delay, and the proposed scheme. `summaries/RESULTS.md` includes **paired** proposed-minus-baseline differences. Bulk per-scenario raw records are regenerated rather than versioned (see `.gitignore`); only the demo scenario `d200_r02` is kept. The earlier 2-seed set (old network, 7 Oct) remains in git history only. Design and audit: `docs/SYSTEM_DESIGN.md`, `docs/AUDIT.md`. The on-off attacker sweep alone: `python run.py sensitivity --only onoff`.

### Bash helper scripts

On Linux, macOS, or a suitable Bash environment, these helpers expect `.venv/bin/python`:

```bash
bash run_demo.sh
SKIP_GUI=1 bash run_experiment.sh
```

`run_experiment.sh` also runs validation and sensitivity sweeps, so it is heavier than the quick experiment above. Some comments and output paths in the helpers reflect older project settings; `config.py` and the Python commands in this README describe the current configuration. On Windows PowerShell, use `python run.py ...` directly.

## 9. Optional cloud export and test dispatch

Without external endpoint configuration, events remain local. These commands do not need a cloud account to export or retain local data:

```bash
python run.py sync
python run.py dispatch
```

To enable external integrations, set these **environment variables in the terminal running the command**:

| Variable | Purpose |
| --- | --- |
| `IOV_CLOUD_URL` | HTTPS JSON ingestion endpoint |
| `IOV_CLOUD_TOKEN` | Optional cloud bearer token |
| `IOV_EMERGENCY_URL` | Explicitly configured HTTPS test/service endpoint |
| `IOV_EMERGENCY_TOKEN` | Optional dispatch bearer token |

For example, PowerShell uses `$env:IOV_CLOUD_URL = 'https://your-test-service.example/ingest'`; Bash uses `export IOV_CLOUD_URL='https://your-test-service.example/ingest'`. Replace the example with an endpoint you control.

Receiving services must honor the supplied `Idempotency-Key`. Failed transfers stay queued for retry. No real emergency-service endpoint is bundled.

## 10. Static documentation deployment

The `portal/` directory is a separate, dependency-free HTML/CSS/JavaScript site. To preview it without the Python app:

```bash
cd portal
python -m http.server 3000
```

Open `http://127.0.0.1:3000/`. This serves documentation and the packaged result snapshot; it does not provide the Python results API.

For a static host, publish the contents of `portal/`. For a Vercel import, use `portal` as the project root with a static/Other framework configuration. No frontend dependencies or compilation are required. Do not upload `.env` or the entire research directory as public static files. The SUMO GUI and the long-running Python HTTP server need a separate runtime; deploying the static folder does not deploy those features.

After generating new experiments, refresh the packaged CSV, figures, and source downloads from the **project root**:

```bash
python build_portal_assets.py
```

Optional portal validation, from `portal/`, with Node.js installed:

```bash
node check.mjs
```

The validation currently expects the checked-in 78-row comparison snapshot (6 densities x 13 schemes). A new experiment matrix can change that row count; review the assertion when intentionally publishing a different matrix.

## 11. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `python` / `py` not found | Install Python and reopen the terminal; verify the selected interpreter. |
| `ModuleNotFoundError` | Activate `.venv` and install requirements with that environment's `python -m pip`. |
| No matching dependency distribution | Check the named package, Python version, OS, and architecture. Use a compatible interpreter with available distributions. Preserve the original pins; record any intentional compatibility changes. |
| Installation cannot reach the package index | Check internet/proxy settings and retry; an incomplete install is not a working environment. |
| SUMO binary missing | Reinstall `eclipse-sumo` in the active environment, then rerun the binary version check. |
| SUMO-GUI cannot open | Use a graphical desktop and resolve any reported native-library error; use CLI experiments on headless machines. |
| Missing network or result file | Run from the project root and copy the full `network/` directory. Generate missing results with `single` or `experiment`. |
| Web page cannot connect | Keep `python run.py web` running, check its terminal, and use its configured port. |
| Documentation content returns 404 | Restart the Python server after updating its source, then refresh the browser. |
| Empty result list | Run `python run.py single -d 200 -r 2`, wait for completion, and refresh results. |
| Static portal shows older results | Regenerate its assets with `python build_portal_assets.py`. |

## 12. Project map

```text
run.py                       Command-line entry point
config.py                    Experiment parameters and defaults
scenario.py / network/       SUMO mobility and road network
clustering.py                Clustering and representative selection
corroboration.py              Voting and BLS certificates
protocols.py / channel.py    Forwarding schemes and radio model
rsu.py / infrastructure.py   RSU acceptance, persistence, and outbox
experiment.py / metrics.py   Evaluation pipeline
figures.py / report.py       Charts, reports, and dashboard
web_results.py              Local HTTP server, results API and faculty-demo dashboard API
results_viewer.html          Faculty-demo dashboard, saved-results UI and documentation buttons
demo.py / demo_pairs.py      SUMO-GUI replay; comparison pairs (separated baseline / proposed runs)
portal/                     Static project documentation
validation/                 Automated validation suite
results/urban/              Saved research outputs
PROJECT_GUIDE.md             Additional project notes
docs/SYSTEM_DESIGN.md        Algorithms, parameters, failure behaviour, evaluation protocol
docs/AUDIT.md                Evidence-based audit and the decisions taken
docs/Final_Project_Report.pdf  Final project report (docs/final_report/build_final_report.py)
```

The Word-document generator scripts are optional authoring utilities and require `python-docx`, which is not part of the simulator requirements. Install it separately only if regenerating those documents.
