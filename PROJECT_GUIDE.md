# Emergency alert project

## AI explanations (Groq)

### Local multilingual web application

In terminal 1 run `python run.py web`, then open `http://127.0.0.1:8765`.
The home URL keeps the simulation results workspace and adds 12 documentation
buttons above its controls. Each button opens the corresponding project content
inside the page. Full documentation is available at
`http://127.0.0.1:8765/index.html`; the standalone results workspace also remains
available at `http://127.0.0.1:8765/simulation`.
The static `portal` folder remains independently deployable; its local Python
results integration is enabled only when served by `python run.py web`.
In terminal 2 run `python run.py demo` to keep all simulation output in that terminal.
The web app reads saved results; click Refresh results after a new run is recorded.
Select the simulation run, click a genuine or forged-alert result, choose a language,
and click Explain this result. Tamil, Hindi, Telugu, Kannada, Malayalam, Bengali,
Marathi, Gujarati, Punjabi and Odia are supported. The full recorded report is
expandable. The server loads the key from `.env`; the browser never receives it.
AI explanations are cached per event, scheme, language, evidence and model. API
failures are shown explicitly without presenting English fallback text as a translation.
The app binds to localhost and is intended for local use beside SUMO.
New runs preserve a separate historical record with their system start date/time.
The browser formats this timestamp in your system timezone and checks for new
results every five seconds. Results appear after simulation data has been saved;
this is not a live step-by-step feed. Older files use their last save time, marked
as older files. Main demo results are shown by default; choose All research
comparisons to see the additional ablations and security variants.

Keep your key out of source code. In PowerShell set `$env:GROQ_API_KEY = 'YOUR_NEW_KEY'`.
The posted key should be replaced. Optional `GROQ_MODEL` selects a supported Groq model;
the default is `qwen/qwen3.8-27b`. No extra Python dependency is required.

Run `python run.py demo --narrate --language ta` for Tamil explanations in the
terminal beside SUMO; use `--language en` for English. On Bash, the same options
can be passed to `./run_demo.sh`. Explanations are prepared before SUMO opens,
so API calls do not pause animation. Relevant recorded run evidence is sent to
Groq. Generated stage explanations are cached locally by evidence, language and
model. They are AI summaries and can contain errors; recorded metrics remain authoritative.

For a saved run, use `python run.py assistant d200_r02 --language ta`, or ask
`python run.py assistant d200_r02 --language en --question "Why are cars frozen?"`.
Run the demo or `python run.py single` first if the saved run does not exist.
Use `--offline` to disable API calls and show basic explanations. Missing keys,
timeouts, API errors and invalid narration responses also fall back automatically.
Offline Q&A prints recorded evidence rather than pretending to answer the question.

Run `python run.py` for the SUMO presentation. Run `python run.py single --all`
for every scheme's terminal results. A quick dashboard uses
`python run.py experiment --densities 50 100 200 250 --runs 3`.
The full experiment uses `python run.py experiment` (30 seeds per population).
Open `results/urban/dashboard.html` afterwards.
Use `python run.py dashboard` to refresh an existing dashboard without rerunning
the experiments. On Windows, optional SUMO screenshots capture the introductory
map and incident; overlay-heavy replay captures are skipped to avoid a SUMO
OpenGL capture stall. Live replay still shows every stage.

## Architecture and algorithms

SUMO mobility → generated vehicle dataset → DBSCAN clusters → trust-gated
representatives → randomized incident → distinct signed votes → BLS aggregate
certificate → radio dissemination → RSU validation → local storage and outbox.

* Clustering uses DBSCAN on coordinates (40 m, minimum 3 vehicles). Cluster
  representatives greedily cover members; relative speed breaks coverage ties.
  Trust must meet 0.7. Roles change with vehicle positions during the live demo.
* Beta trust is `(successes + 1)/(successes + failures + 2)` from simulated
  watchdog observations. Post-event updates use an explicitly defined effective
  prior of weight 20: `(20 * previous_trust + 1)/21` for observed forwarding.
  Unobserved vehicles receive no update; no inference of guilt from silence.
* `proposed` prioritizes reputable heads/bridges with distance slots and random
  delay, then suppresses transmissions when neighbours are already covered.
* `ch_route` computes a shortest total-distance route to an available RSU with
  Dijkstra over the source, reputable non-malicious heads, and RSUs. Each
  intermediate head collects radio-delivered signed member votes before it
  forwards. Three distinct endorsements, including the head, are required.
  A missing route or lost quorum prevents forwarding; there is no hidden fallback.
* Receivers verify real BLS signatures using `py_ecc`. Keys are deterministically
  generated simulation identities, not a deployed vehicular PKI.
* Batch authentication processes multiple certificates and deduplicates event
  IDs. It performs per-event aggregate verification, not a faster multi-message
  pairing algorithm. Duplicate alerts are registered once per run/event.

## Infrastructure integration

SQLite at `results/urban/infrastructure/backhaul.sqlite3` stores accepted events,
trust observations, and a durable dispatch outbox. `python run.py sync` exports
JSON. With `IOV_CLOUD_URL` set to an HTTPS JSON ingestion API, that same command
uploads the export. Optional authentication uses `IOV_CLOUD_TOKEN`.

`python run.py dispatch` forwards queued accepted events only when
`IOV_EMERGENCY_URL` is configured. Optional authentication uses
`IOV_EMERGENCY_TOKEN`. Use a test endpoint for this research simulation.
Responses must be HTTP 2xx. The receiving APIs must honour the supplied
Idempotency-Key; retries otherwise may repeat requests. Failed transfers remain
local and queued. No cloud account or live emergency-service endpoint is bundled.
Keep credentials in environment variables, outside source control.

## Evaluation and practical limits

Compare flooding, slotted 1-persistence, proposed suppression and CH routing on
identical seeds and vehicle snapshots. Report RSU success, delay, hops and
transmissions separately from vehicle-wide reachability: unicast-style routing
does not aim to reach every vehicle. Figures include means and Student-t 95%
confidence intervals, ablations, and forged-alert tests. Low-sample quick runs
are smoke checks, not evidence of statistical improvement or novelty.

The incident is injected at a random vehicle/time/location; it is a staged
accident, not a physics collision detector. Radio dissemination uses the incident
snapshot while SUMO is frozen for presentation. Honest voters observe simulation
ground truth, trust is shared, and radio propagation is a unit-disk approximation.
There are two configurable RSU sites; coverage adequacy is measured, not assumed.
Backhaul latency, a physical LAN, real sensor truth, cloud uptime and real dispatch
are outside the radio model. A cloud/service endpoint is required for deployment.

The original source papers have not been provided in this session. References
already present in code need verification against those papers before claiming
paper-specific improvements. A valid motivating scenario is an accident outside
direct RSU range: trusted relay heads attempt to reach infrastructure while
limiting duplicate broadcasts. Future evaluation should include fading, real
sensor errors, mobility during routing, larger networks and deployed PKI.
