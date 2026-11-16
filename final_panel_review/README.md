# Final panel review: report and presentation

| File | What it is |
|---|---|
| `Project_Implementation_Report.tex` | Editable report (university template `case_1_research_project/1_report.tex`: Amrita header, team table, Times, 0.8 in margins, maroon headings, IEEE references) |
| `Project_Panel_Presentation.tex` | Editable Beamer presentation (template `1_presentation.tex`: Madrid theme, maroon, logo, Type 1 corner box), titled *Emergency Message Dissemination for Broadcast Storm Mitigation in the Internet of Vehicles* (set in the presentation only; the report keeps the title in `team_details.tex`). Slide 2, *Guide Approval*, shows the guide's reply ("Approved for external review.") as the unmodified screenshot `figures/guide_approval_email.png` |
| `G083_Report.pdf`, `Project_Panel_Presentation.pdf` | Compiled documents (see *Compile* below); `G083_Report.pdf` is the compiled `Project_Implementation_Report.tex`. `G083_Presentation.pdf` is the earlier 26-slide version of the presentation, left as it was |
| `Panel_Review_Presentation.pptx`, `Panel_Review_Presentation.pdf` | The panel deck as an editable PowerPoint (16:9, 25 slides, same structure as the Beamer version, native charts and tables, speaker notes) and its PDF exported by PowerPoint. Built by `scripts/make_pptx.js` from `generated/pptx_data.json` and `generated/pptx_refs.json` (see *PowerPoint version* below) |
| `team_details.tex` | Title, team number, students, guide: fill the bracketed fields once, both documents use them |
| `references.bib` | 19 references, checked against publisher, DBLP, author or ETSI pages on 15 Nov 2026 (fields that could not be confirmed are left out and noted at the top of the file) |
| `generated/` | `numbers.tex` (every number quoted in the text of both documents) and `tab_*.tex` (result tables), written by `scripts/make_figures_and_tables.py` from `results/urban/processed/*.csv` and `results/urban/sensitivity/` |
| `figures/` | Charts from the same CSVs (`rep_*` drawn at print size for the report, `sl_*` for the slides, `chart_*` earlier versions), the workflow diagram, the architecture export, SUMO-GUI captures (`sumo/`, `shot_*`), print-size crops of them (`view_map_*`, `view_status_*`, `dashboard/view_dash_*`) and dashboard captures (`dashboard/`). `FIGURE_SOURCES.json` names the source capture of every screenshot and crop |
| `architecture/` | Presentation architecture (slide 11 of both decks): `architecture_implemented.{png,pdf,svg}`, five stages, implemented functionality only, every box checked against the code (module list at the top of `scripts/make_architecture_final.py`). `future_cloud_integration.{png,pdf,svg}`: cloud trust management, central analytics, historical storage, multi-RSU coordination and traffic intelligence, labelled *Proposed Future Enhancements — Not Yet Implemented* (no cloud service is connected; `run.py sync` only writes a local export unless `IOV_CLOUD_URL` is set). Regenerate both with `python final_panel_review/scripts/make_architecture_final.py`. The report's Eraser.io architecture is unchanged: export (`system_architecture_eraser.png`, also `figures/system_architecture.png`), definition (`system_architecture_freeform.json`, written by `make_architecture_freeform.py`) and the module behind every box (`system_architecture_eraser.txt`) |
| `scripts/` | `make_figures_and_tables.py`, `make_workflow_diagram.py`, `prepare_screenshots.py`, `make_report_views.py` (crops only; no pixel is drawn or edited), `make_slide_assets.py` (slide charts `sl_*`, including `sl_frames_density` and `sl_forgery` used on slides 19 and 20; the slide results table `generated/tab_slide_results.tex`; `generated/slide_numbers.tex`; older slide tables `generated/tab_slide_headline.tex` and `generated/slide_verdict_grid.tex`; dashboard and zoom crops) |
| `logo.png`, `logo_square.png` | University logo from the template folder |

## Compile

Needs a LaTeX distribution (MiKTeX, TeX Live or Tectonic). From this folder:

```bash
pdflatex Project_Implementation_Report && bibtex Project_Implementation_Report && pdflatex Project_Implementation_Report && pdflatex Project_Implementation_Report
pdflatex Project_Panel_Presentation && bibtex Project_Panel_Presentation && pdflatex Project_Panel_Presentation && pdflatex Project_Panel_Presentation
```

or `tectonic Project_Implementation_Report.tex` and `tectonic Project_Panel_Presentation.tex` (Tectonic runs BibTeX itself).

The PDFs in this folder were built with Tectonic 0.17.0 (release asset SHA-256 checked against GitHub's published
digest): report on 15 Nov 2026, 27 pages (A4, page 6 landscape for the architecture; no overfull or underfull boxes,
undefined references or citations; saved as `G083_Report.pdf`); presentation on 16 Nov 2026, 25 slides (16:9: title,
Guide Approval, content slides 3 to 22, two reference slides and the closing slide; no overfull or underfull boxes,
undefined references or citations).
The presentation draws its own simplified architecture and pipeline diagrams in TikZ and reuses the report's genuine
screenshot crops; the detailed Eraser.io architecture and 13-stage workflow stay in the report.

## PowerPoint version

```bash
python final_panel_review/scripts/make_pptx_data.py      # numbers from the CSVs and generated macros, image sizes
NODE_PATH=<node_modules with pptxgenjs 3.12.0> node final_panel_review/scripts/make_pptx.js \
    final_panel_review/Panel_Review_Presentation.pptx <pptx skill>/scripts/apply_theme.js
```

`generated/pptx_refs.json` holds the 19 reference strings taken from the compiled Beamer PDF. The PDF was exported by
PowerPoint itself (File > Save As > PDF), so it shows exactly what the panel will see. Every 100.0 % reach figure in the
deck carries "measured", the run count and "ideal radio model", and is stated as an observation, not a guarantee.

## Regenerate figures and tables

```bash
python final_panel_review/scripts/make_figures_and_tables.py
python final_panel_review/scripts/make_workflow_diagram.py
python final_panel_review/scripts/make_report_views.py
python final_panel_review/scripts/make_slide_assets.py
```

## Team and TEA evidence

`team_details.tex` holds the five members, the guide (Dr. Radhika G, Department of CSE, Amrita Vishwa Vidyapeetham),
the project type and team number 83; both documents read it. The Technical Enrichment table (report section 18,
slide 22) is based on `G083_Project_TEA_Activities.zip`, checked on 15 Nov 2026:

* TEA 1, online course: five Coursera certificates for *Introduction to the Internet of Things and Embedded Systems*
  (University of California, Irvine), one per register number, each confirmed on its Coursera verification page;
  plus `Team_83_IoT_Course_Relevance_Report.docx`.
* TEA 2, research paper: `G083_Paper.pdf`, an 8-page manuscript prepared 17 Oct 2026. The ZIP has no evidence of
  submission, acceptance or publication, so it is described as a manuscript. Five of its references, [13] to [17], are
  marked "to be confirmed"; `research_paper_reference_check.md` gives verified replacements for four of them and flags
  [17] (SAE J2735) for correction by the authors.
* TEA 3, documentation website: https://iov-documentation-portal.vercel.app/ answers (HTTP 200); its `index.html` and
  `data.js` are byte-identical to the project's portal as committed on 27 Oct 2026, so later portal updates are not
  deployed yet.
* Repository: https://github.com/AkhilRudrapaka/IoV-Emergency-Broadcast is public; its last push was 27 Oct 2026.

## Provenance of the evidence

* SUMO walkthrough captures: one complete `python run.py demo --shots` run of the showcase scenario d200_r02 (seed 30002),
  14 Nov 2026, `completed = true`, record fingerprint 397f81ab… (the same as the experiment's record of this seed).
* Baseline-only and proposed-only captures: evidence pair P002 (`results/demo_pairs/P002`, scenario d200_r02).
* Dashboard captures: headless Microsoft Edge on the running dashboard, 15 Nov 2026: evidence pair P002 (d200_r02) after
  both runs, and a live proposed-only run of scenario d200_r25 (seed 30025) in a scratch pairs folder, exit code 0.
* Numbers: `results/urban/processed/summary.csv`, `paired.csv`, `forgery_runs.csv` and the sensitivity sweeps; nothing
  is typed by hand.
