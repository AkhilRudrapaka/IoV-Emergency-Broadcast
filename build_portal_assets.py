"""Refresh only the static portal's curated research assets and downloads."""
import csv
import json
import math
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORTAL = ROOT / 'portal'
assets = PORTAL / 'assets'
downloads = PORTAL / 'downloads'
assets.mkdir(exist_ok=True)
downloads.mkdir(exist_ok=True)
summary = ROOT / 'results/urban/processed/summary.csv'
rows = []
with summary.open(newline='', encoding='utf-8') as file:
    for row in csv.DictReader(file):
        converted = {}
        for key, value in row.items():
            if key == 'protocol':
                converted[key] = value
            else:
                number = float(value)
                converted[key] = number if math.isfinite(number) else None
        rows.append(converted)
(PORTAL / 'data.js').write_text('window.RESEARCH_DATA = ' + json.dumps(rows, allow_nan=False) + ';\n', encoding='utf-8')
shutil.copy2(summary, assets / 'summary.csv')
for name in ['architecture.png', 'comparison.png', 'incident_map_d200_r02.png']:
    shutil.copy2(ROOT / 'results/urban/figures' / name, assets / name)
for name in ['config.py', 'PROJECT_GUIDE.md', 'Project_Website_Documentation_Portal.docx']:
    shutil.copy2(ROOT / name, downloads / name)
shutil.copy2(ROOT / 'results/urban/summaries/RESULTS.md', downloads / 'RESULTS.md')
revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip() or 'Unavailable'
snapshot = 'Source revision: ' + revision + '\nSnapshot UTC: ' + datetime.now(timezone.utc).isoformat() + '\nSource bundle includes current working files, which may differ from the recorded revision.\n'
(downloads / 'SNAPSHOT.txt').write_text(snapshot, encoding='utf-8')
selected = list(ROOT.glob('*.py')) + [ROOT / n for n in ['requirements.txt', 'pytest.ini', 'README.md', 'PROJECT_GUIDE.md', 'run_demo.sh', 'run_experiment.sh']]
selected += list((ROOT / 'network').glob('*.xml')) + list((ROOT / 'network').glob('*.py')) + list((ROOT / 'validation').glob('test_*.py'))
selected += list((ROOT / 'results/urban/processed').glob('*.csv')) + list((ROOT / 'results/urban/summaries').glob('*.md')) + list((ROOT / 'results/urban/summaries').glob('*.json'))
with zipfile.ZipFile(downloads / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in selected:
        archive.write(path, path.relative_to(ROOT))
    archive.writestr('SNAPSHOT.txt', snapshot)
print(f'Prepared {len(rows)} saved result rows, figures, documentation and source downloads.')
