"""
Entry point.

  python run.py experiment            full matrix -> results/ (raw, processed, figures, summaries, dashboard)
  python run.py single -d 200 -r 7    one scenario, every scheme: the event monitor (--debug: full timeline)
  python run.py explain d200_r07      chronological story of a saved run (--scheme flooding for a baseline,
                                      --forged voting_reputation for the forged-alert test)
  python run.py sensitivity           range and misbehaviour sweeps at 200 vehicles
  python run.py demo                  the fixed demo scenario in SUMO-GUI: clusters, voting, flooding, the
                                      proposed scheme, RSU reception, and a forged alert being rejected
"""
import argparse
import glob
import os
import subprocess
import sys

import config
import experiment
import figures
import report
import infrastructure


def cmd_experiment(a):
    densities = a.densities or config.DENSITIES
    runs = a.runs or config.RUNS_PER_DENSITY
    print(f"{config.TITLE}\n{len(densities)} densities x {runs} runs x {len(config.PROTOCOLS)} schemes, one incident per run\n")
    rows, forged = experiment.run_matrix(densities, runs)
    summary, forgery = experiment.write_outputs(rows, forged)
    report.save_config({"densities": densities, "runs": runs})
    if a.no_report:
        return
    # The showcase is the fixed demo scenario, so the explainer, the figures and the
    # SUMO-GUI demo all describe the same event.
    experiment.run_one(config.DEMO_DENSITY, config.DEMO_RUN)
    showcase = f"d{config.DEMO_DENSITY}_r{config.DEMO_RUN:02d}"
    raw = experiment.load_raw(showcase)
    fig_dir = os.path.join(config.RESULTS_DIR, "figures")
    existing = lambda pattern, caption: [(p, caption(p)) for p in sorted(glob.glob(os.path.join(fig_dir, pattern)))]
    relay_note = "Relayed alerts = incidents outside the direct range of both RSUs."
    sections = [
        ("1. System architecture", [(figures.architecture(), "Pipeline and the code that owns each stage"),
                                    (figures.flow(), "One run, step by step")], None),
        ("2. One-run explanation", [(figures.decision_map(raw), "Proposed scheme: who voted, who rebroadcast, who suppressed, and why")],
         "\n\n".join(report.run_block(raw, p) for p in config.BASELINES)),
        ("3. Topology, clusters and SUMO view",
         [(figures.topology(raw), "Road network, RSU sites and their radio coverage"),
          (figures.clusters(raw), "DBSCAN clusters and elected representatives at the incident second")]
         + existing("sumo_*.png", lambda p: "SUMO-GUI screenshot: " + os.path.basename(p)[7:-4].replace("_", " ")), None),
        ("4. Broadcast propagation", [(figures.propagation(raw), "Animated replay: flooding vs proposed on the same accident"),
                                      (figures.incident_maps(raw), "One incident, three schemes: who rebroadcast"),
                                      (figures.timeline(raw), "Propagation timeline")], None),
        ("5. Baselines vs proposed: transmissions, collisions, delivery, coverage time",
         [(figures.comparison(summary, config.BASELINES, "comparison.png",
                              "Blind flooding vs slotted 1-persistence vs proposed"), "Headline comparison across densities")], None),
        ("6. RSU reception and incident-to-RSU delay",
         [(figures.comparison(summary, config.BASELINES, "rsu.png", "Delivery to the road-side units",
                              figures.RSU_PANELS, relay_note), "RSU metrics across densities")], None),
        ("7. Ablations: the full method with one component removed",
         [(figures.ablation(summary), "Ablations at 200 and 500 vehicles")], None),
        ("8. Corroboration: voting + BLS + reputation against a forged alert",
         [(figures.forgery(forgery), "Forged-alert test across densities")] if forgery else [],
         report.run_block(raw, forged="voting_reputation") if raw.get("forgery") else None),
        ("9. Sensitivity analysis", existing("sensitivity_*.png", lambda p: "Sensitivity: " + os.path.basename(p)[12:-4]), None),
        ("10. Cluster-head route delivery", [(figures.comparison(summary, config.BASELINES + ['ch_route'], 'ch_route.png',
             'Broadcast methods vs CH shortest-path routing', figures.RSU_PANELS),
             'RSU delivery and overhead: the routing scheme includes per-head voting frames')], None),
    ]
    report._write("RESULTS.md", report.results_md(summary, forgery))
    report._write(f"explain_{showcase}.md", report.explain(raw))
    if raw.get("forgery"):
        report._write(f"explain_{showcase}_forged.md", report.explain(raw, forged="voting_reputation"))
    dash = report.dashboard(summary, forgery, sections, raw)
    print("\n" + headline(summary))
    print(f"\nShowcase run {showcase}: python run.py explain {showcase}\nDashboard: {dash}")


def headline(summary):
    out = [f"{'vehicles':>8} | {'scheme':<22} | {'frames':>6} | {'lost rx':>8} | {'reach %':>7} | {'t90 ms':>6} | "
           f"{'RSU %':>6} | {'RSU ms':>6}   (RSU columns: relayed alerts)"]
    for r in summary:
        if r["protocol"] in config.BASELINES:
            out.append(f"{r['density']:>8} | {config.LABELS[r['protocol']]:<22} | {r['transmissions']:>6.1f} | "
                       f"{r['collision_losses']:>8.0f} | {100 * r['reachability']:>7.1f} | {r['t90_ms']:>6.1f} | "
                       f"{100 * r['rsu_relay_received']:>6.1f} | {r['rsu_relay_delay_ms']:>6.1f}")
    return "\n".join(out)


def cmd_single(a):
    rows, _ = experiment.run_one(a.density, a.run)
    raw = experiment.load_raw(rows[0]["run_id"])
    for p in config.PROTOCOLS if a.all else config.BASELINES:
        print(report.run_block(raw, p) + "\n")
    if raw.get("forgery"):
        for variant in config.FORGERY if a.all else ["voting_reputation"]:
            print(report.run_block(raw, forged=variant) + "\n")
    if a.debug:
        print(report.explain(raw))


def cmd_explain(a):
    raw = experiment.load_raw(a.run_id)
    text = report.explain(raw, a.scheme, a.forged)
    print(text)
    filename = f"explain_{a.run_id}{'_forged' if a.forged else ''}.md"
    print(f"saved: {report._write(filename, text)}")
    print(f"figures: {figures.incident_maps(raw)}, {figures.decision_map(raw)}, {figures.clusters(raw)}, "
          f"{figures.timeline(raw)}, {figures.propagation(raw)}")


def cmd_sensitivity(a):
    sweeps = {"range": ("COMM_RANGE_M", [150.0, 300.0, 450.0], "radio range (m)"),
              "malicious": ("MALICIOUS_RATIO", [0.0, 0.1, 0.2, 0.3], "share of misbehaving vehicles")}
    for name, (param, values, label) in sweeps.items():
        rows, forged = [], []
        for v in values:
            out = os.path.join(config.RESULTS_DIR, "sensitivity", f"{name}_{v:g}")
            env = {**os.environ, f"EXP_{param}": str(v), "EXP_RESULTS_DIR": out}
            print(f"sensitivity: {param} = {v}")
            subprocess.run([sys.executable, "run.py", "experiment", "--densities", str(a.density), "--no-report"],
                           env=env, check=True, stdout=subprocess.DEVNULL)
            rows.append((v, figures._read(os.path.join(out, "processed", "summary.csv"))))
            path = os.path.join(out, "processed", "forgery_summary.csv")
            if os.path.exists(path):                      # absent when no vehicle misbehaves
                forged.append((v, figures._read(path)))
        if name == "range":
            print(figures.sensitivity(rows, name, label, config.BASELINES, ["transmissions", "reachability", "t90_ms"]))
        else:
            print(figures.sensitivity(rows, name, label, ["slotted1p", "proposed", "no_reputation"],
                                      ["transmissions", "t90_ms", "t_last_ms"]))
            print(figures.sensitivity(forged, "forgery", label, list(config.FORGERY), ["accepted_share", "rsu_registered"],
                                      group="variant", labels=config.FORGERY))


def cmd_demo(a):
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        sys.exit("SUMO-GUI needs a graphical display (DISPLAY is not set). Use `python run.py explain` instead.")
    import demo
    demo.run(a.density, a.run, a.scheme, a.pace, a.shots, wait=not a.no_wait, forged=not a.no_forged,
             narration=a.narrate, language=a.language, offline=a.offline)


def cmd_assistant(a):
    import narrator
    raw = experiment.load_raw(a.run_id)
    if a.question:
        print(narrator.answer(raw, a.scheme, a.question, a.language, a.offline))
    else:
        notes, source = narrator.prepare(raw, a.scheme, a.language, offline=a.offline)
        print(f"Simulation explanation ({source})")
        for stage, text in notes.items():
            print(f"\n{stage.upper()}\n{text}")


def cmd_dashboard(a):
    summary = figures._read(os.path.join(config.RESULTS_DIR, 'processed', 'summary.csv'))
    forgery_path = os.path.join(config.RESULTS_DIR, 'processed', 'forgery_summary.csv')
    forgery = figures._read(forgery_path) if os.path.exists(forgery_path) else []
    raw = experiment.load_raw(f'd{config.DEMO_DENSITY}_r{config.DEMO_RUN:02d}')
    paths = sorted(glob.glob(os.path.join(config.RESULTS_DIR, 'figures', '*.png')))
    paths += sorted(glob.glob(os.path.join(config.RESULTS_DIR, 'figures', '*.gif')))
    sections = [('Research results and SUMO views', [(path, os.path.basename(path).replace('_', ' ')) for path in paths], None)]
    print(report.dashboard(summary, forgery, sections, raw))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if len(sys.argv) == 1:
        sys.argv.append('demo')
    ap = argparse.ArgumentParser(description=config.TITLE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser('sync', help='export local backhaul; upload only when IOV_CLOUD_URL is configured')
    sub.add_parser('dispatch', help='send queued validated records only to a configured IOV_EMERGENCY_URL')
    sub.add_parser('dashboard', help='rebuild the dashboard from existing experiment files')
    w = sub.add_parser('web', help='local multilingual results application (separate terminal)')
    w.add_argument('--port', type=int, default=8765)
    n = sub.add_parser('assistant', help='explain a saved simulation or ask a question')
    n.add_argument('run_id')
    n.add_argument('--scheme', default='proposed', choices=config.PROTOCOLS)
    n.add_argument('--language', choices=['ta', 'en'], default='ta')
    n.add_argument('--question')
    n.add_argument('--offline', action='store_true')
    e = sub.add_parser("experiment")
    e.add_argument("--densities", type=int, nargs="+")
    e.add_argument("--runs", type=int)
    e.add_argument("--no-report", action="store_true")
    s = sub.add_parser("single")
    s.add_argument("-d", "--density", type=int, default=config.DEMO_DENSITY)
    s.add_argument("-r", "--run", type=int, default=config.DEMO_RUN)
    s.add_argument("--all", action="store_true", help="also show the ablation variants")
    s.add_argument("--debug", action="store_true", help="also print the full chronological timeline")
    x = sub.add_parser("explain")
    x.add_argument("run_id")
    x.add_argument("--scheme", default="proposed", choices=config.PROTOCOLS)
    x.add_argument("--forged", choices=list(config.FORGERY), help="explain the forged-alert test instead")
    v = sub.add_parser("sensitivity")
    v.add_argument("--density", type=int, default=200)
    g = sub.add_parser("demo")
    g.add_argument("-d", "--density", type=int, default=config.DEMO_DENSITY)
    g.add_argument("-r", "--run", type=int, default=config.DEMO_RUN)
    g.add_argument("--scheme", nargs="+", default=["flooding", "proposed", "ch_route"], choices=config.PROTOCOLS)
    g.add_argument("--pace", type=float, default=0.35, help="seconds per animation frame")
    g.add_argument("--shots", help="directory for SUMO-GUI screenshots")
    g.add_argument("--no-wait", action="store_true", help="close SUMO-GUI when the replay ends")
    g.add_argument("--no-forged", action="store_true", help="skip the forged-alert part")
    g.add_argument('--narrate', action='store_true', help='show cached AI explanations in the terminal')
    g.add_argument('--language', choices=['ta', 'en'], default='ta')
    g.add_argument('--offline', action='store_true', help='use basic explanations without API requests')
    a = ap.parse_args()
    {"experiment": cmd_experiment, "single": cmd_single, "explain": cmd_explain,
     "sensitivity": cmd_sensitivity, "demo": cmd_demo,
     "sync": lambda _: print(infrastructure.sync_cloud(config.RESULTS_DIR)),
     "dashboard": cmd_dashboard, "assistant": cmd_assistant,
     "web": lambda a: __import__('web_results').serve(a.port),
     "dispatch": lambda _: print(infrastructure.dispatch_pending(config.RESULTS_DIR))}[a.cmd](a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\nDemo stopped by user.')
