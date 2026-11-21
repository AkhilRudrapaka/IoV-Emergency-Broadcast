# IoV Trust-Aware Clustering Upgrade: 5–7 Day Sprint Plan for Publishable Draft

**Goal:** Transform the current SUMO-based trust-aware clustering + controlled broadcast system into a stronger, ML-augmented research contribution that addresses faculty feedback (real dataset, ML/DL component, publishable quality). Deliver a complete internal draft paper suitable for faculty review and subsequent submission to a reputable venue (IEEE TVT, IEEE T-ITS, Vehicular Communications, or a solid IEEE conference such as VTC / Globecom / TrustCom track).

**Timeline:** 5 core working days + 2 buffer days. No 8–12 week scope. Focus on one solid, reproducible improvement path with honest evaluation.

**Core Improvements (Prioritized):**
1. **Real-world map / traffic realism** — Replace pure synthetic 5×5 grid with OpenStreetMap-derived network (or inD OpenDRIVE if feasible) + calibrated synthetic demand. Document clearly what is real vs synthetic.
2. **ML-based attack detector** — Add a lightweight supervised ML model (Random Forest / XGBoost primary; simple MLP optional) that operates on windowed features (trust trajectory, kinematics, neighbour discrepancy) to detect on-off / intermittent attackers that currently bypass pure Beta-trust (25/30 success rate in existing results).
3. **Expanded rigorous experiments** — Re-run on the new map with the original baselines + new ML detector. Report Precision/Recall/F1, false-positive rate, time-to-detection, frame count, and latency with confidence intervals.
4. **Publishable paper draft** — IEEE-style manuscript with clear contributions, limitations, reproducibility notes, and realistic claims.

**Non-Goals (to protect timeline):**
- Full real trajectory replay from inD (too heavy for 1–2 days; use map geometry + synthetic flows as primary).
- Heavy deep learning (Transformers, large GNNs) or multi-city datasets.
- New cryptographic primitives or hardware radio models.
- Guaranteeing journal acceptance (impossible in any timeline).

---

## Team Roles (5 people, parallel workstreams)

| Role | Primary Owner | Key Responsibilities |
|------|---------------|----------------------|
| Project Lead / Integrator | [Lead] | Schedule, Git freeze, reproducibility, plan execution, final paper assembly |
| Data / Simulation Engineer | [Dev A] | Real map import (OSM or inD), traffic demand calibration, logging of features |
| ML Engineer | [Dev B] | Feature engineering, model training/evaluation, integration into detection pipeline |
| Experimentation Engineer | [Analyst] | Scenario matrix, batch runs, metrics, plots, statistical comparison |
| Writer / Documentation | [Writer] | Paper outline → full draft (Intro, Related Work, Method, Results, Discussion, Limitations) |

Daily 15-min stand-up. Code freeze at end of Day 1. All results reproducible via single command + fixed seeds.

---

## Day-by-Day Plan

### Day 1 — Setup, Baseline Freeze, Real Dataset Selection & Outline
**Outcomes:** Reproducible baseline, chosen real map source, paper skeleton, CLAUDE.md context file.

- Commit and tag current working codebase (`v0.9-baseline`).
- Reproduce key numbers from the existing 180-scenario report (especially the 25/30 on-off failure).
- Dataset decision (priority order):
  1. OpenStreetMap extract of a small urban area (via osmWebWizard / JOSM) → netconvert to SUMO. Fastest and free.
  2. inD dataset OpenDRIVE map (if license and conversion time allow).
  3. Fallback: keep existing grid but document it honestly and still add ML.
- Create `CLAUDE.md` at repo root with project goals, constraints, style (IEEE), metrics, and current weaknesses.
- Paper outline (IEEE 2-column style): Title, Abstract, Intro, Related Work, System Model, Proposed Method (trust + clustering + ML detector + controlled broadcast), Experimental Setup, Results, Discussion/Limitations, Conclusion.
- Assign sections and list 8–12 key references (existing survey papers + inD/OSM/SUMO + recent trust/ML IoV papers).

**Go / No-Go:** Baseline runs cleanly and map source is chosen by EOD.

### Day 2 — Real Map Integration & Feature Logging
**Outcomes:** SUMO scenarios running on realistic topology; feature extraction pipeline ready.

- Import map → SUMO network. Calibrate vehicle demand to produce plausible densities (low/medium/high).
- Update scenario generator to work with new net and produce the same incident + on-off attacker model.
- Extend logging: per-vehicle windowed features (last 5–10 s): Beta trust history, speed/accel statistics, neighbour trust discrepancy, message consistency indicators.
- Sanity runs + visualization in SUMO-GUI.
- The project uses a hand-built synthetic 5×5 grid with synthetic traffic demand. The OSM import was attempted but not completed.

**Go / No-Go:** End-to-end simulation on new map succeeds; feature logs are generated.

### Day 3 — ML Detector Implementation
**Outcomes:** Trained, evaluated lightweight ML model integrated (or ready) into the detection path.

- Feature matrix from Day 2 logs. Labels from scenario ground truth (honest vs on-off attacker windows).
- Train / validate split by scenario seed (no leakage).
- Primary models: Random Forest and XGBoost (scikit-learn / xgboost). Optional: small MLP (PyTorch or sklearn) if time remains.
- Simple baselines for comparison: pure Beta threshold, Isolation Forest.
- Metrics: Precision, Recall, F1, FPR, PR-AUC. Focus on on-off attack case.
- Lightweight hyper-parameter search only. Prefer interpretability and low inference cost.
- Integrate best model into the pipeline so it can flag suspicious vehicles before or alongside committee voting.

**Go / No-Go:** Model trains and produces sensible F1 on held-out scenarios. If ML fails to improve, keep it and report the negative/neutral result honestly.

### Day 4 — Full Experiment Matrix & Analysis
**Outcomes:** Complete comparison tables + figures ready for paper.

- Scenario matrix (bounded): densities × attacker types (always-malicious, always-honest, 90 % on-off, intermittent) × seeds. Prioritize on-off and false-alarm cases.
- Run original baselines + proposed method + ML-augmented variant.
- Compute all metrics with 95 % confidence intervals where multiple seeds exist.
- Ablation: contribution of ML detector vs pure trust/clustering.
- Generate publication-quality plots (frame count, latency, detection F1, ROC/PR curves).
- Honest analysis: where ML helps, where it does not, trade-offs in false positives.

**Go / No-Go:** Core comparisons finished (or prioritised subset complete). Incomplete runs marked as future work.

### Day 5 — Paper Draft Assembly & Internal Submission
**Outcomes:** Complete draft manuscript + all artefacts ready for faculty review.

- Write / polish every section. Emphasise:
  - Clear gap (broadcast suppression + event corroboration + ML detection of intermittent attackers).
  - Honest limitations (simulation, synthetic demand, scale).
  - Reproducibility (seeds, SUMO version, code availability note).
- Insert tables, figures, captions.
- Related Work: position against recent trust, clustering, and ML-based misbehaviour detection papers.
- Venue note: suitable for IEEE Transactions on Vehicular Technology, IEEE T-ITS, Vehicular Communications, or conferences (VTC, Globecom IoT/ITS tracks, TrustCom). State this is a draft for internal review.
- Final checklist: grammar, acronym definitions, consistent notation, all claims backed by data.

### Days 6–7 (Buffer)
- Re-runs, figure polishing, proofreading, address any quick faculty comments, prepare submission packet skeleton (abstract, keywords, cover letter template).

---

## Quality & Reproducibility Checklist

- [ ] Single command reproduces all main results (`python run.py experiment` or equivalent).
- [ ] Fixed random seeds recorded.
- [ ] Real vs synthetic components explicitly stated in paper and README.
- [ ] All metrics defined (Precision = TP/(TP+FP), etc.).
- [ ] Code, configs, and result CSVs version-controlled and tagged.
- [ ] No fabricated numbers; negative or neutral ML results reported if they occur.
- [ ] IEEE-style references and formatting.

---

## Recommended Venues (Realistic for Draft → Submission)

**Journals (longer cycle):**  
- IEEE Transactions on Vehicular Technology  
- IEEE Transactions on Intelligent Transportation Systems  
- Vehicular Communications (Elsevier)  
- IEEE Internet of Things Journal (if security angle strengthened)

**Conferences (faster feedback):**  
- IEEE VTC (Spring/Fall)  
- IEEE Globecom / ICC (IoT & ITS tracks)  
- IEEE TrustCom or CNS  
- IEEE ITSC  

Start with a solid conference submission while polishing for journal.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Map import takes too long | Fall back to OSM with synthetic demand by mid-Day 2; document limitation |
| ML does not beat Beta threshold | Report honest result; still publish the combined pipeline evaluation |
| Experiments overrun | Cut matrix to priority cells (on-off + density variation) |
| Writing quality | Writer works in parallel from Day 1; Lead does final consistency pass |
| Token / time pressure with Claude | Use sub-agents, background tasks, focused prompts, CLAUDE.md |

---

## Success Criteria for Draft

- Real(istic) map used and documented.
- At least one ML model integrated and evaluated against on-off attacks.
- Full comparison tables + figures with statistical care.
- Clear contributions, limitations, and reproducibility statement.
- Draft ready for faculty feedback by end of Day 5 / buffer.

This plan turns the existing strong prototype into a credible, improved research contribution without over-scoping. Execute with daily discipline and honest reporting.
