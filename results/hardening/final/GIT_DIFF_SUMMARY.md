# Git diff summary (working tree vs HEAD 107f1b4; nothing committed)

Generated 2026-11-21 with `git diff --stat` and `git status --short` (repository setting core.autocrlf=true: line endings normalised, as a commit would record them). Tracked files modified, including the Blocks A–F changes made earlier in the sprint:

```
 CLAUDE.md                                          |  23 +++++++-
 PROJECT_GUIDE.md                                   |   3 +
 README.md                                          |   2 +
 build_portal_assets.py                             |   1 +
 config.py                                          |  36 ++++++++++++
 corroboration.py                                   |  26 ++++++---
 demo.py                                            |  37 ++++++++++--
 docs/SYSTEM_DESIGN.md                              |   2 +
 .../portal/downloads/PROJECT_GUIDE.md              |   3 +
 experiment.py                                      |  62 +++++++++++++++------
 figures.py                                         |   3 +-
 infrastructure.py                                  |  12 ++--
 portal/app.js                                      |  10 ++--
 portal/downloads/PROJECT_GUIDE.md                  |   3 +
 portal/downloads/SNAPSHOT.txt                      |   4 +-
 portal/downloads/config.py                         |  36 ++++++++++++
 portal/downloads/source.zip                        | Bin 490262 -> 585909 bytes
 protocols.py                                       |  15 +++--
 run.py                                             |  60 ++++++++++++++++++--
 scenario.py                                        |  38 ++++++++++++-
 20 files changed, 321 insertions(+), 55 deletions(-)
```

Block G share of these changes: see CHANGED_FILES.md. Untracked (new) files and folders:

```
?? BLOCK_D_INTEGRATION_REPORT.md
?? BLOCK_F_ADVERSARIAL_REPORT.md
?? BLOCK_G_FINAL_REPORT.md
?? BLOCK_G_SECURITY_HARDENING_PLAN.md
?? DATASET_ACQUISITION_REPORT.md
?? DATASET_MANIFEST_InTAS_highway_2.json
?? DATASET_TRACKS_MANIFEST.json
?? DAY1_PROJECT_AND_DATASET_AUDIT.md
?? INCIDENT_RESPONSE_MILESTONE_REPORT.md
?? PREPROCESSING_REPORT.md
?? ROUTING_COMPARISON_REPORT.md
?? VEREMI_GENERATOR_LABEL_INVESTIGATION.md
?? adversarial.py
?? incident_response.py
?? incident_routing.py
?? ml_trust.py
?? results/adversarial/
?? results/hardening/
?? results/incident/
?? results/incident_routing/
?? validation/test_adversarial.py
?? validation/test_hardening.py
?? validation/test_incident_response.py
?? validation/test_incident_routing.py
?? validation/test_ml_trust.py
?? veremi/
```

Branch: akhil; HEAD: 107f1b4 docs: add sprint plan, master prompt and CLAUDE.md for ML + real-map upgrade. Nothing staged, committed or pushed.
