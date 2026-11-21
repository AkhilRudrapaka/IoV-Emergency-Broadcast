"""Block G final: baseline reproduction and the effect of the new defaults (writes only results/hardening/final_checks).

    python -X utf8 results/hardening/analysis/final_baseline_check.py      (run from the project root)

1. ENFORCE_COMMITTEE=0, TRUST_BURST_K=0 must reproduce the tracked results/urban CSVs byte for byte: the default matrix
   (6 densities x 30 runs) and the tracked on-off set (cooperation 0.9, 200 vehicles).
2. The same two experiments with the new defaults (enforcement on): what changes against the tracked files."""
import csv, filecmp, os, subprocess, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join("results", "hardening", "final_checks")   # a fresh folder re-runs
CSVS = ("runs.csv", "summary.csv", "paired.csv", "forgery_runs.csv", "forgery_summary.csv")
CASES = [("baseline_off", {"EXP_ENFORCE_COMMITTEE": "0", "EXP_TRUST_BURST_K": "0"}, [], "results/urban/processed"),
         ("onoff09_off", {"EXP_ENFORCE_COMMITTEE": "0", "EXP_TRUST_BURST_K": "0", "EXP_MALICIOUS_COOPERATION": "0.9"},
          ["--densities", "200"], "results/urban/sensitivity/onoff_0.9/processed"),
         ("default_on", {}, [], "results/urban/processed"),
         ("onoff09_on", {"EXP_MALICIOUS_COOPERATION": "0.9"}, ["--densities", "200"],
          "results/urban/sensitivity/onoff_0.9/processed")]
env0 = {k: v for k, v in os.environ.items() if not k.startswith("EXP_")}
ok = True
for name, overrides, args, ref in CASES:
    folder = os.path.join(OUT, name)
    if not os.path.exists(os.path.join(folder, "summaries", "experiment_config.json")):
        subprocess.run([sys.executable, "run.py", "experiment", *args, "--no-report"], check=True,
                       env={**env0, **overrides, "EXP_RESULTS_DIR": folder}, stdout=subprocess.DEVNULL)
    same = {f: filecmp.cmp(os.path.join(folder, "processed", f), os.path.join(ref, f), shallow=False) for f in CSVS}
    print(f"{name} vs {ref}: " + ", ".join(f"{f} {'identical' if v else 'DIFFERENT'}" for f, v in same.items()))
    if name.endswith("_off"):
        ok &= all(same.values())
    else:                                        # new defaults: genuine dissemination must not change
        ok &= same["runs.csv"] and same["summary.csv"] and same["paired.csv"]
        for path, label in ((os.path.join(ref, "forgery_runs.csv"), "tracked (enforcement off)"),
                            (os.path.join(folder, "processed", "forgery_runs.csv"), "new default (enforcement on)")):
            rows = list(csv.DictReader(open(path, encoding="utf-8")))
            acc = {v: (sum(float(r["accepted_share"]) > 0 for r in rows if r["variant"] == v),
                       sum(r["variant"] == v for r in rows)) for v in sorted({r["variant"] for r in rows})}
            reg = {v: sum(float(r["rsu_registered"]) == 1 for r in rows if r["variant"] == v) for v in acc}
            print(f"   {label}: runs where any vehicle accepted the forgery {acc}; RSU registered it {reg}")
print("BASELINE REPRODUCED AND GENUINE UNCHANGED" if ok else "FAILED")
sys.exit(0 if ok else 1)
