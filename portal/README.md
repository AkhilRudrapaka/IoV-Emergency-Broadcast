# Relay research documentation portal

A static, dependency-free HTML/CSS/JavaScript web application covering all 12 project documentation sections. Includes searchable navigation, saved-result density comparisons, a staged workflow walkthrough, printable documentation, and curated downloads.

## Run locally

From this directory:

```powershell
python -m http.server 3000
```

Open http://localhost:3000. No dependency installation or compilation is needed. Run `npm run check` to validate scripts and required result assets.

## Deploy on Vercel

Import your repository, choose `portal` as Root Directory and `Other` as Framework Preset. Leave Build Command and Output Directory unset (serve the project root). No environment variables are required. Alternatively, upload this directory to any static host.

## Data and downloads

`data.js` is a static snapshot of `results/urban/processed/summary.csv`. `assets/` includes the original CSV and selected project-generated figures. `downloads/source.zip` contains an explicitly selected source bundle, excluding secrets and local databases. See `downloads/SNAPSHOT.txt` for source revision and time. Regenerate these files with `python build_portal_assets.py` from the parent project directory after new research results are saved.

The portal does not run Python, query a database, call AI APIs, or transfer emergency alerts. The separate local simulation and results server remain documented in PROJECT_GUIDE.md.
