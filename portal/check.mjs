import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';
for (const file of ['index.html','styles.css','app.js','data.js','assets/summary.csv','downloads/source.zip']) {
  if (!existsSync(file)) throw new Error(`Missing ${file}`);
}
new vm.Script(readFileSync('app.js','utf8'));
const context = { window: {} }; vm.createContext(context);
vm.runInContext(readFileSync('data.js','utf8'),context);
if (context.window.RESEARCH_DATA.length !== 78) throw new Error('Expected 78 saved comparison rows (6 densities x 13 schemes)');
for (const density of [50,100,200,250]) for (const protocol of ['flooding','slotted1p','proposed','ch_route']) {
  if (!context.window.RESEARCH_DATA.some(r=>r.density===density && r.protocol===protocol)) throw new Error('Missing comparison');
}
// Snapshots of a verified SUMO run are optional; when a manifest is installed, every file it names must exist.
if (existsSync('assets/sumo/snapshots.js')) {
  const snap = { window: {} }; vm.createContext(snap);
  vm.runInContext(readFileSync('assets/sumo/snapshots.js','utf8'), snap);
  for (const s of snap.window.SUMO_SNAPSHOTS.snapshots) {
    if (!s.stage || !s.run_id || s.sim_time_s == null || !s.caption) throw new Error('Incomplete snapshot entry');
    if (s.file && !existsSync(`assets/sumo/${s.file}`)) throw new Error(`Missing snapshot assets/sumo/${s.file}`);
  }
}
console.log('Portal checks passed: JavaScript syntax, required assets, saved result comparisons and SUMO snapshots.');
