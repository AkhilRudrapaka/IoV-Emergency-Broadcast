"""
Entry point.

  python run.py experiment            full matrix -> results/ (raw, processed, figures, summaries, dashboard)
  python run.py single -d 200 -r 7    one scenario, every scheme: the event monitor (--debug: full timeline)
  python run.py explain d200_r07      chronological story of a saved run (--scheme flooding for a baseline,
                                      --forged voting_reputation for the forged-alert test)
  python run.py sensitivity           range and misbehaviour sweeps at 200 vehicles
  python run.py demo                  the fixed demo scenario in SUMO-GUI: clusters, voting, flooding, the
                                      proposed scheme, RSU reception, and a forged alert being rejected
  python run.py incident -d 200 -r 2  headless incident response: staged stop -> detection from live telemetry ->
                                      verified alert -> TraCI rerouting -> results/incident/ (--runs N: seeds 0..N-1)
  python run.py incident-compare      routing comparison on seeds 0..29: no incident / no rerouting / shortest path /
                                      route-preserving detour -> results/incident_routing/
"""
import argparse
import glob
import os
import re
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
    rows, forged = experiment.run_matrix(densities, runs, first=a.first_run)
    summary, forgery = experiment.write_outputs(rows, forged)
    report.save_config({"densities": densities, "runs": runs, **({"first_run": a.first_run} if a.first_run else {})})
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
    report._write("RESULTS.md", report.results_md(summary, forgery, experiment.paired(rows)))
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
              "malicious": ("MALICIOUS_RATIO", [0.0, 0.1, 0.2, 0.3], "share of misbehaving vehicles"),
              # on-off attacker: behaves well while watched, so its reputation is no longer an oracle (audit SCE-2/3)
              "onoff": ("MALICIOUS_COOPERATION", [0.0, 0.5, 0.9], "share of watched relays a misbehaving vehicle performs")}
    if a.only:
        sweeps = {a.only: sweeps[a.only]}
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
            print(figures.sensitivity(forged, f"forgery_{name}", label, list(config.FORGERY), ["accepted_share", "rsu_registered"],
                                      group="variant", labels=config.FORGERY))


def cmd_demo(a):
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        sys.exit("SUMO-GUI needs a graphical display (DISPLAY is not set). Use `python run.py explain` instead.")
    if a.pair or a.approach:
        return pair_demo(a)
    import demo
    demo.run(a.density, a.run, a.scheme, a.pace, a.shots, wait=not a.no_wait, forged=not a.no_forged,
             **({"reroute": True} if a.reroute else {}))          # without --reroute: the earlier call, unchanged


def pair_demo(a):
    """ONE separated run of a comparison pair (demo_pairs.py): only this approach's schemes, on the pair's scenario,
    one run at a time, every write in this approach's own folder <pair>/<approach>/ (re-executed with EXP_RESULTS_DIR
    when needed), so the two runs of a pair never share or overwrite a file."""
    import shutil
    import demo_pairs
    if not (a.pair and a.approach):
        sys.exit("--pair and --approach go together. Create a pair first: python run.py pair new")
    pair = demo_pairs.load(a.pair)
    folder = demo_pairs.approach_dir(a.pair, a.approach)
    if os.path.abspath(config.RESULTS_DIR) != os.path.abspath(folder):
        env = {**os.environ, "EXP_RESULTS_DIR": folder, "DEMO_PAIRS_DIR": demo_pairs.ROOT}
        sys.exit(subprocess.run([sys.executable, os.path.abspath(__file__), *sys.argv[1:]], env=env).returncode)
    import demo
    sc, run = pair["scenario"], pair["runs"][a.approach]
    schemes = demo_pairs.schemes_for(a.approach, pair["baseline"])
    demo_pairs.acquire(a.pair, a.approach)
    try:
        demo_pairs.update_run(a.pair, a.approach, status="running", pid=os.getpid(), started=demo_pairs.now(),
                              finished=None, message=None, fingerprint=None)
        demo.LIVE.update(pair_id=a.pair, approach=a.approach, algorithm=run["algorithm"], schemes=schemes,
                         scenario_id=sc["scenario_id"], seed=sc["seed"], incident=sc["incident"])
        shutil.rmtree(folder, ignore_errors=True)                     # a re-run replaces this approach's outputs only
        raw = demo.run(sc["density"], sc["run"], schemes, a.pace, wait=False,
                       forged=a.approach == "proposed" and not a.no_forged, approach=a.approach, archive=False,
                       check=lambda record: demo_pairs.check_record(pair, record), capture_dir=folder)
        demo_pairs.update_run(a.pair, a.approach, status="finished", finished=demo_pairs.now(),
                              fingerprint=demo.record_fingerprint(raw),
                              record=os.path.join(a.approach, "raw", sc["scenario_id"] + ".json.gz"))
        print(f"\nPair {a.pair}: {a.approach}-only run finished ({run['algorithm']}; scenario {sc['scenario_id']}, "
              f"seed {sc['seed']}). Records: {folder}")
    except BaseException as exc:
        message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        demo.live_feed(done=True, failed=True, workflow_stage="failed", status=f"Run failed: {message}", stage="failed")
        demo_pairs.update_run(a.pair, a.approach, status="failed", finished=demo_pairs.now(), message=message)
        raise
    finally:
        demo_pairs.release()


def cmd_incident(a):
    import incident_response
    if not a.runs:
        print(incident_response.describe(incident_response.run(a.density, a.run, method=a.method)))
        return
    rows, path = incident_response.run_many(a.density, a.runs, method=a.method)
    for r in rows:
        print("  ".join(f"{k}={r[k]}" for k in ("run_id", "speed_before_mps", "detected", "rerouted", "no_alternative",
                                                "unavoidable", "rerouted_entries", "forged_routes_changed")))
    print(f"detected {sum(r['detected'] for r in rows)}/{len(rows)}; rerouted {sum(r['rerouted'] for r in rows)}; "
          f"entries by rerouted vehicles {sum(r['rerouted_entries'] for r in rows)}; forged-alert route changes "
          f"{sum(r['forged_routes_changed'] or 0 for r in rows)}\nsummary: {path}")


def cmd_incident_compare(a):
    import incident_routing
    print(incident_routing.main(a.density, a.runs, a.end, simulate=not a.analyse_only))


def cmd_adversarial(a):
    import adversarial
    print(adversarial.main(a.sweep, a.densities, a.runs, summarise_only=a.summarise_only))


def cmd_pair(a):
    import demo_pairs
    if a.action == "new":
        run = None
        if a.scenario is not None:
            m = re.fullmatch(rf"(?:d{demo_pairs.DENSITY}_r)?(\d+)", a.scenario)
            if not m:
                sys.exit(f"--scenario: give d{demo_pairs.DENSITY}_rNN or NN")
            run = int(m.group(1))
        pair = demo_pairs.new_pair(a.baseline, run)
        print(describe_pair(pair))
        print(f"\nNext, one at a time:\n  python run.py demo --pair {pair['pair_id']} --approach baseline\n"
              f"  python run.py demo --pair {pair['pair_id']} --approach proposed")
        return
    demo_pairs.reconcile()
    if a.action == "list":
        for p in demo_pairs.pairs():
            s = p["scenario"]
            print(f"{p['pair_id']}  {s['scenario_id']} (seed {s['seed']})  incident {s['incident']['vehicle']} at "
                  f"({s['incident']['x']:.0f}, {s['incident']['y']:.0f}) m, t = {s['incident']['time_s']:.0f} s  |  "
                  + "  |  ".join(f"{r['approach']}: {r['status']}" for r in p["runs"].values()))
        return
    pair = demo_pairs.load(a.pair_id)
    print(describe_pair(pair))
    raw, reason = demo_pairs.comparison(pair)
    if raw is None:
        print(f"\nComparison: {reason}")
        return
    print(f"\nComparison (one run: scenario {pair['scenario']['scenario_id']}, seed {pair['scenario']['seed']}; "
          f"not a multi-seed result):")
    for row in demo_pairs.comparison_rows(pair, raw):
        values = "  ".join(f"{c['label']}: {c['text']}" for c in row["cells"])
        print(f"  {row['label']:<44} {values}")


def describe_pair(pair):
    s, inc = pair["scenario"], pair["scenario"]["incident"]
    sel = s["selection"]
    lines = [f"Pair {pair['pair_id']} (created {pair['created']})",
             f"  scenario {s['scenario_id']}  seed {s['seed']}  network {s['network']}  {s['density']} vehicles",
             f"  incident: {inc['vehicle']} at ({inc['x']:.1f}, {inc['y']:.1f}) m on lane {inc['lane']}, "
             f"t = {inc['time_s']:.0f} s, event {inc['event_id']}",
             f"  selection: {sel['method']}" + (f"; REPEATS {sel['repeat_of']}" if sel["repeat_of"] else "")]
    for r in pair["runs"].values():
        lines.append(f"  {r['approach']:<8} run: {r['algorithm']} -> {r['status']}"
                     + (f" ({r['message']})" if r.get("message") else ""))
    return "\n".join(lines)


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
    w = sub.add_parser('web', help='local saved-results viewer (separate terminal)')
    w.add_argument('--port', type=int, default=8765)
    e = sub.add_parser("experiment")
    e.add_argument("--densities", type=int, nargs="+")
    e.add_argument("--runs", type=int)
    e.add_argument("--no-report", action="store_true")
    e.add_argument("--first-run", type=int, default=0, help="first run index (>= 30: held-out seeds, e.g. for calibration)")
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
    v.add_argument("--only", choices=["range", "malicious", "onoff"], help="run one sweep only")
    g = sub.add_parser("demo")
    g.add_argument("-d", "--density", type=int, default=config.DEMO_DENSITY)
    g.add_argument("-r", "--run", type=int, default=config.DEMO_RUN)
    g.add_argument("--scheme", nargs="+", default=["flooding", "proposed", "ch_route"], choices=config.PROTOCOLS)
    g.add_argument("--pace", type=float, default=0.35, help="seconds per animation frame")
    g.add_argument("--shots", help="directory for stage snapshots of the live SUMO window + snapshots.json/.js "
                                   "(Windows; e.g. portal/assets/sumo for the portal's SUMO Demonstration section)")
    g.add_argument("--no-wait", action="store_true", help="close SUMO-GUI when the replay ends")
    g.add_argument("--no-forged", action="store_true", help="skip the forged-alert part")
    g.add_argument("--reroute", action="store_true", help="end with the telemetry detection of the stop and TraCI "
                                                          "rerouting of the verified alert holders (run.py incident)")
    g.add_argument("--pair", help="a comparison pair (python run.py pair new): replay its scenario, one approach only")
    g.add_argument("--approach", choices=["baseline", "proposed"],
                   help="with --pair: the baseline only, or the proposed method only (its CH-to-CH route stage included)")
    q = sub.add_parser("pair", help="comparison pairs: one incident scenario, a baseline-only and a proposed-only run")
    q.add_argument("action", choices=["new", "list", "show"])
    q.add_argument("pair_id", nargs="?", help="for show")
    q.add_argument("--baseline", default="flooding", choices=["flooding", "flooding_rad", "slotted1p", "slotted1p_rad"])
    q.add_argument("--scenario", help="new: this scenario (d200_rNN or NN) instead of the next reproducible one")
    n = sub.add_parser("incident", help="headless incident response: detection, verified alert, TraCI rerouting")
    n.add_argument("-d", "--density", type=int, default=config.DEMO_DENSITY)
    n.add_argument("-r", "--run", type=int, default=config.DEMO_RUN)
    n.add_argument("--runs", type=int, help="seeds 0..N-1 in parallel, plus results/incident/summary_d<density>.csv")
    n.add_argument("--method", choices=["detour", "shortest"], default=config.REROUTE_METHOD,
                   help="detour: bypass the incident edge and rejoin the original route (default); shortest: the "
                        "earlier travel-time shortest path to the destination (comparison baseline)")
    c = sub.add_parser("incident-compare", help="A no incident / B no rerouting / C shortest / D detour, same demand")
    c.add_argument("-d", "--density", type=int, default=config.DEMO_DENSITY)
    c.add_argument("--runs", type=int, default=config.RUNS_PER_DENSITY, help="seeds 0..N-1")
    c.add_argument("--end", type=int, default=config.ROUTING_EVAL_END_S, help="every session ends at this time (s)")
    c.add_argument("--analyse-only", action="store_true", help="re-derive the tables and figures from per_vehicle.csv")
    v2 = sub.add_parser("adversarial", help="Block F attack sweeps -> results/adversarial/ (see adversarial.py)")
    v2.add_argument("sweep", choices=["A", "B", "C_calibration", "C", "C_gate", "G1", "G2", "G3a", "G3b", "G3b_gate",
                                         "G4"],
                    help="A-C_gate: Block F (results/adversarial); G1-G4: Block G (results/hardening)")
    v2.add_argument("--densities", type=int, nargs="+", default=[100, 200, 300])
    v2.add_argument("--runs", type=int, default=30)
    v2.add_argument("--summarise-only", action="store_true", help="re-read finished settings without running any")
    a = ap.parse_args()
    {"experiment": cmd_experiment, "single": cmd_single, "explain": cmd_explain,
     "sensitivity": cmd_sensitivity, "demo": cmd_demo,
     "sync": lambda _: print(infrastructure.sync_cloud(config.RESULTS_DIR)),
     "dashboard": cmd_dashboard, "pair": cmd_pair, "incident": cmd_incident,
     "incident-compare": cmd_incident_compare, "adversarial": cmd_adversarial,
     "web": lambda a: __import__('web_results').serve(a.port),
     "dispatch": lambda _: print(infrastructure.dispatch_pending(config.RESULTS_DIR))}[a.cmd](a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\nDemo stopped by user.')
