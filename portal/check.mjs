import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';
for (const file of ['index.html','styles.css','app.js','data.js','assets/summary.csv','downloads/source.zip']) {
  if (!existsSync(file)) throw new Error(`Missing ${file}`);
}
new vm.Script(readFileSync('app.js','utf8'));
const context = { window: {} }; vm.createContext(context);
vm.runInContext(readFileSync('data.js','utf8'),context);
if (context.window.RESEARCH_DATA.length !== 44) throw new Error('Expected 44 saved comparison rows');
for (const density of [50,100,200,250]) for (const protocol of ['flooding','slotted1p','proposed','ch_route']) {
  if (!context.window.RESEARCH_DATA.some(r=>r.density===density && r.protocol===protocol)) throw new Error('Missing comparison');
}
console.log('Portal checks passed: JavaScript syntax, required assets and saved result comparisons.');
