# Trust-Aware Vehicular Emergency Alerts

A Python/SUMO research prototype for verified emergency-alert forwarding through vehicle clusters to roadside units (RSUs). It includes signed voting, BLS certificate verification, forwarding comparisons, saved results, a local web application, and a 12-section documentation portal.

The incident is staged in simulation. No real crash detection or live emergency dispatch is enabled by default.

## 1. What to copy to the other computer

Copy the **entire project folder**, including `network/`, `portal/`, `validation/`, and `results/` if you want the existing experiments. Keep the folder structure unchanged.

Do not copy a virtual environment from another computer. Create a fresh one using the steps below. Caches (`__pycache__`, `.pytest_cache`) and diagnostic logs are unnecessary. Create your own `.env` if optional AI explanations are needed; do not share someone else's API credentials.

Run every project command below from the folder containing `run.py` and `requirements.txt`, unless a step explicitly changes directory.

## 2. Prerequisites

- A 64-bit Python installation. Python 3.11 is the version used in the existing development environment; dependency installation must succeed before running the project.
- Internet access for initial dependency installation and optional AI requests.
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
| `http://127.0.0.1:8765/` | Saved simulation results with 12 project-documentation buttons |
| `http://127.0.0.1:8765/index.html` | Full documentation portal |
| `http://127.0.0.1:8765/simulation` | Results workspace, including language selection and explanations |

The documentation buttons cover Home; Introduction and Background; Problem Statement; Objectives and Research Gap; Proposed System and Architecture; Methodology and Algorithms; Implementation and Technologies; Accident Simulation and Emergency Workflow; Results and Performance Evaluation; Source Code and Reproducibility; Research Papers and References; and Limitations and Future Work.

If the copied project has no saved runs, open **terminal 2**, activate the same environment, and generate one:

```bash
python run.py single -d 200 -r 2
```

After it finishes, click **Refresh results** in the browser. The viewer also checks for changed saved runs every five seconds. It displays saved data, not a live simulation-step feed.

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

The GUI presents the configured incident, clusters, corroboration, forwarding comparisons, RSU outcomes, and forged-alert test. Keep the web server running separately if you also want to inspect saved results.

Useful options:

```bash
python run.py demo --scheme proposed
python run.py demo --pace 0.8
python run.py demo --no-wait
python run.py demo --narrate --language ta --offline
```

Running `python run.py` without a subcommand also starts the demo. On a machine without a graphical display, use `single` or `explain` instead.

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

The checked-in quick comparison contains only two scenarios per population. It is preliminary evidence, not the completed 30-seed experiment.

### Bash helper scripts

On Linux, macOS, or a suitable Bash environment, these helpers expect `.venv/bin/python`:

```bash
bash run_demo.sh
SKIP_GUI=1 bash run_experiment.sh
```

`run_experiment.sh` also runs validation and sensitivity sweeps, so it is heavier than the quick experiment above. Some comments and output paths in the helpers reflect older project settings; `config.py` and the Python commands in this README describe the current configuration. On Windows PowerShell, use `python run.py ...` directly.

## 9. Optional AI explanations

Simulation and saved metrics work without an AI key. To enable AI explanations, create `.env` beside `run.py`:

```dotenv
GROQ_API_KEY=replace_with_your_own_key
# Optional: set a model supported by your Groq account
# GROQ_MODEL=your_model_id
```

The project loads `GROQ_API_KEY` and `GROQ_MODEL` from this file. If `GROQ_MODEL` is omitted, it uses the default defined in `narrator.py`; availability depends on the provider and account.

Restart the web server, choose a saved result and language, then click **Explain this result**. The key stays on the Python server. API errors and rate limits are shown in the UI; saved metrics remain accessible.

Terminal explanations:

```bash
python run.py demo --narrate --language ta
python run.py assistant d200_r02 --language en
python run.py assistant d200_r02 --language en --offline
```

The web interface offers more languages than the terminal's `ta` / `en` options. Offline terminal explanations do not require a key. Generated explanations may contain errors; recorded metrics remain authoritative.

## 10. Optional cloud export and test dispatch

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

For example, PowerShell uses `$env:IOV_CLOUD_URL = 'https://your-test-service.example/ingest'`; Bash uses `export IOV_CLOUD_URL='https://your-test-service.example/ingest'`. Replace the example with an endpoint you control. The `.env` loader handles only the Groq variables, not these integration variables.

Receiving services must honor the supplied `Idempotency-Key`. Failed transfers stay queued for retry. No real emergency-service endpoint is bundled.

## 11. Static documentation deployment

The `portal/` directory is a separate, dependency-free HTML/CSS/JavaScript site. To preview it without the Python app:

```bash
cd portal
python -m http.server 3000
```

Open `http://127.0.0.1:3000/`. This serves documentation and the packaged result snapshot; it does not provide the Python results API or AI explanations.

For a static host, publish the contents of `portal/`. For a Vercel import, use `portal` as the project root with a static/Other framework configuration. No frontend dependencies or compilation are required. Do not upload `.env` or the entire research directory as public static files. The SUMO GUI and the long-running Python HTTP server need a separate runtime; deploying the static folder does not deploy those features.

After generating new experiments, refresh the packaged CSV, figures, and source downloads from the **project root**:

```bash
python build_portal_assets.py
```

Optional portal validation, from `portal/`, with Node.js installed:

```bash
node check.mjs
```

The validation currently expects the checked-in 44-row comparison snapshot. A new experiment matrix can change that row count; review the assertion when intentionally publishing a different matrix.

## 12. Troubleshooting

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
| AI explanation unavailable | Check your own key, configured model, network access, and provider quota; honor the retry countdown. |
| Static portal shows older results | Regenerate its assets with `python build_portal_assets.py`. |

## 13. Project map

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
web_results.py              Local HTTP server and results API
results_viewer.html          Results UI and documentation buttons
portal/                     Static project documentation
validation/                 Automated validation suite
results/urban/              Saved research outputs
PROJECT_GUIDE.md             Additional project notes
```

The Word-document generator scripts are optional authoring utilities and require `python-docx`, which is not part of the simulator requirements. Install it separately only if regenerating those documents.
