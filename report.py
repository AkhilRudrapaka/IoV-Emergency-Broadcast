"""
Text outputs: the event monitor panel, the chronological one-run explainer, the
results tables, the saved experiment configuration, and the HTML dashboard.
Every number is read from saved results.
"""
import base64
import datetime
import json
import os
import platform
import subprocess

import config
import presentation
from scenario import SUMO_BIN

SUMMARIES = os.path.join(config.RESULTS_DIR, "summaries")


def _write(name, text):
    os.makedirs(SUMMARIES, exist_ok=True)
    path = os.path.join(SUMMARIES, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_config(extra=None):
    params = {k: getattr(config, k) for k in dir(config) if k.isupper()}
    sumo_version = subprocess.run([SUMO_BIN, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    record = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
              "python": platform.python_version(), "sumo": sumo_version,
              "overrides": {k: v for k, v in os.environ.items() if k.startswith("EXP_")},
              "parameters": params, **(extra or {})}
    return _write("experiment_config.json", json.dumps(record, indent=2, default=str))


# ------------------------------------------------------------------ event monitor panel
def panel(d):
    """The monitor shown for a finished run (run_block) and, with partial counts, live by the demo."""
    bar = "=" * 64
    return "\n".join([
        bar, f" EMERGENCY DISSEMINATION MONITOR | {d['scheme'].upper()}", bar,
        f"Event        : {d['event_id']} ({d['type']})",
        f"Status       : {d['status']}",
        f"Source       : Vehicle {d['source']}   (run {d['run_id']}, seed {d['seed']})",
        f"Location     : {tuple(d['position'])} at t = {d['time_s']:.0f} s",
        "", "Corroboration", "-------------",
        f"Committee    : {d['committee']}",
        f"Votes        : {d['votes']}",
        f"Certificate  : {d['certificate']}",
        "", "Vehicles", "--------",
        f"Total        : {d['total']}",
        f"Accepted     : {d['reached']} / {d['total']}{d.get('reached_note', '')}",
        "", "Forwarding", "----------",
        f"Forwarded    : {d['forwarded']}",
        f"Suppressed   : {d['suppressed']}",
        f"Misbehaving  : {d['dropped']} received but never relay",
        "", "Network", "-------",
        f"Transmissions: {d['transmissions']}{d.get('tx_note', '')}",
        f"Collisions   : {d['collisions']} receptions lost{d.get('collision_note', '')}",
        "", "RSU", "---",
        f"Status       : {d['rsu_status']}",
        f"Delay        : {d['rsu_delay']}",
        f"Duplicates   : {d['rsu_dups']}",
        bar])


def rsu_lines(event, reachable=True, rejected=False):
    if event:
        return (f"ALERT RECEIVED, validation passed, registered by {event['receiving_rsu']}",
                f"{event['delay_ms']:.2f} ms after the alert was created ({event['hops']} hop(s), "
                f"{event['transmissions_before_reception']} transmission(s))",
                f"{event['duplicate_copies']} further copies ignored (decoded by {', '.join(event['rsus_that_received'])})")
    if rejected:
        return ("ALERT REJECTED by plausibility validation: not corroborated", "-", "-")
    return ("NO ALERT RECEIVED" if reachable else "no RSU within reach of this vehicle network", "-", "-")


def corroboration_lines(c):
    """(committee, votes, certificate) lines of the monitor."""
    if c is None:
        return "none (voting and BLS switched off)", "-", "not required: every copy is accepted"
    gate = "reputable " if c["use_reputation"] else ""
    cert = c["certificate"]
    return (f"{', '.join(c['committee']) or 'nobody eligible'}  ({config.COMMITTEE_SIZE} nearest {gate}neighbours)",
            f"{len(c['votes'])} cast ({', '.join(v['voter'] for v in c['votes']) or '-'}"
            + (", colluders outside the committee" if c["votes"] and not {v["voter"] for v in c["votes"]} & set(c["committee"]) else "")
            + f"); {config.QUORUM} of {config.COMMITTEE_SIZE} needed",
            (f"BLS aggregate of {len(cert['signers'])} signatures in {config.SIGNATURE_BYTES} bytes: "
             f"{'ACCEPTED' if c['accepted'] else 'REJECTED'} ({c['reason']})") if cert else f"none ({c['reason']})")


def pick(raw, proto="proposed", forged=None):
    """(record, alert, label) of one simulation in a raw file: a scheme on the genuine
    accident, or one protection level of the forged-alert test."""
    if forged:
        return raw["forgery"]["variants"][forged], raw["forgery"]["alert"], "FORGED ALERT | " + config.FORGERY[forged]
    return raw["protocols"][proto], raw["scenario"]["alert"], config.LABELS[proto]


def run_block(raw, proto="proposed", forged=None):
    sc = raw["scenario"]
    P, alert, label = pick(raw, proto, forged)
    m = P["metrics"]
    decisions = [v["decision"] for v in P["vehicles"]]
    rejected = decisions.count("REJECT")
    status, delay, dups = rsu_lines(P["rsu_event"], m["rsu_reachable"], bool(P["rsu_receptions"]) and not P["rsu_event"])
    committee, votes, cert = corroboration_lines(P["corroboration"])
    t90 = f", 90 % within {m['t90_ms']:.1f} ms" if m["t90_ms"] == m["t90_ms"] else ""
    return panel({
        "scheme": label, "event_id": alert["event_id"], "type": alert["message_type"],
        "status": "COMPLETE", "source": alert["source_vehicle"], "run_id": sc["run_id"], "seed": sc["seed"],
        "position": alert["incident_position"], "time_s": alert["incident_time_s"],
        "committee": committee, "votes": votes, "certificate": cert,
        "total": m["honest_reachable"] if forged else m["vehicles"],
        "reached": m["honest_reached"] if forged else m["received"],
        "reached_note": (" honest vehicles" if forged else f"  ({100 * m['reachability']:.1f} %{t90})")
        + (f"; {rejected} received it and rejected it" if rejected else ""),
        "forwarded": decisions.count("FORWARD"), "suppressed": decisions.count("SUPPRESS"),
        "dropped": decisions.count("DROP"),
        "transmissions": m["transmissions"],
        "tx_note": f"  ({sum(t['kind'] == 'PROPOSAL' or t['kind'].startswith('CPROPOSAL:') for t in P['transmissions'])} proposals, {m['vote_tx']} votes, {m['alert_tx']} certified alerts; {m['redundant_tx']} reached nobody new)"
        if P["corroboration"] else f"  ({m['redundant_tx']} reached nobody new)",
        "collisions": m["collision_losses"], "collision_note": f"  ({100 * m['collision_ratio']:.1f} % of receptions)",
        "rsu_status": status, "rsu_delay": delay, "rsu_dups": dups})


# ------------------------------------------------------------------ chronological explainer
def timeline_events(raw, proto="proposed", forged=None):
    """[(ms after the alert was created, kind, text)] for one simulation, in time order."""
    sc = raw["scenario"]
    P, alert, _ = pick(raw, proto, forged)
    by_id = {v["id"]: v for v in P["vehicles"]}
    trust = {v["id"]: v["trust"] for v in sc["vehicles"]}
    c, src = P["corroboration"], alert["source_vehicle"]
    who = "the forger: no accident happened" if forged else "the crashed vehicle"
    events = []
    for tx in P["transmissions"]:
        heard = tx["new"] + tx["dup"] + tx["other"]
        if tx["kind"] == "PROPOSAL":
            text = (f"**{src}** ({who}) broadcasts the PROPOSAL: the alert with its own BLS signature. "
                    f"Decoded by {heard} nodes. The signature proves who sent it, not that the event is real.")
        elif tx['kind'].startswith('CPROPOSAL:'):
            text = f"**{tx['sender']}** collects signed votes from its cluster members. Decoded by {heard} nodes."
        elif tx['kind'].startswith('CVOTE:'):
            text = f"**{tx['sender']}** signs a local cluster vote. Decoded by {heard} nodes."
        elif tx["kind"] == "VOTE":
            text = (f"**{tx['sender']}** VOTES yes (reputation {trust[tx['sender']]:.2f}): it "
                    + ("colludes and signs the false claim" if forged else "observes the crash and signs the event digest")
                    + ". One BLS signature, one vote.")
        elif tx["sender"] == src:
            text = (f"**{src}** broadcasts the alert" if c is None else
                    f"**{src}** has {len(c['votes_counted'])} votes, a majority of the committee of {config.COMMITTEE_SIZE}. "
                    f"It aggregates {len(c['certificate']['signers'])} signatures into one BLS signature and broadcasts "
                    f"the CERTIFIED ALERT") + f". Decoded by {heard} nodes ({tx['new']} accept it)."
        else:
            v = by_id[tx["sender"]]
            role = f"{v['role']}, tier {v['tier']}, reputation {v['trust']:.2f}; " if v["role"] != "-" else ""
            text = (f"**{tx['sender']}** FORWARDS ({role}accepted the copy from {v['from']} {v['dist_m']:.0f} m away, "
                    f"hop {v['hop']}): {v['reason']}. Frame decoded by {heard} nodes ({tx['new']} new, "
                    f"{tx['dup']} already had it), lost at {tx['lost']}.")
        events.append((tx["start_ms"], "tx", text))
    for v in P["vehicles"]:
        if v["decision"] == "SUPPRESS":
            events.append((v["decided_ms"], "suppress", f"**{v['id']}** SUPPRESSES: {v['reason']}."))
    rejecting = [v for v in P["vehicles"] if v["decision"] == "REJECT"]
    if rejecting:
        events.append((min(v["decided_ms"] for v in rejecting), "reject",
                       f"**{len(rejecting)} vehicles** verify the certificate and REJECT the alert: "
                       f"{rejecting[0]['reason']}. Nobody forwards it."))
    seen = set()
    for rx in sorted(P["rsu_receptions"], key=lambda r: r["delay_ms"]):
        if rx["rsu"] not in seen:
            first = not seen
            seen.add(rx["rsu"])
            if not P["rsu_event"]:
                outcome = "plausibility validation FAILS (not corroborated). The event is not recorded."
            elif first:
                outcome = (f"plausibility validation passes; event **{alert['event_id']} REGISTERED** after "
                           f"{rx['transmissions_before']} transmission(s); {rx['vehicles_reached']} vehicles had the alert by then.")
            else:
                outcome = "same event ID, already registered, counted as a duplicate."
            events.append((rx["delay_ms"], "rsu", f"**{rx['rsu']}** decodes the alert from {rx['sender']} (hop {rx['hop']}): {outcome}"))
    return sorted(events, key=lambda e: (e[0], e[1] != "tx"))


def explain(raw, proto="proposed", forged=None, max_suppress=8):
    sc = raw["scenario"]
    P, alert, label = pick(raw, proto, forged)
    roles = [v["role"] for v in sc["vehicles"]]
    events = timeline_events(raw, proto, forged)
    n_sup = sum(k == "suppress" for _, k, _ in events)
    c = P["corroboration"]
    lines = [
        f"# One-run explainer: {sc['run_id']} ({label})", "",
        f"Seed {sc['seed']} | {len(sc['vehicles'])} vehicles | {sum(v['malicious'] for v in sc['vehicles'])} misbehaving "
        f"(never relay) | RSUs: " + ", ".join(f"{u['id']} at ({u['x']:.0f}, {u['y']:.0f})" for u in sc["rsus"]), "",
        "## The emergency packet", "", "```json", json.dumps(alert, indent=2), "```", "",
        "## Timeline", "",
        "Traffic time is in seconds. The radio events take milliseconds, so they are given as time after the alert was created.", "",
        "| Time | Event |", "|---|---|",
        (f"| {alert['incident_time_s']:.3f} s | **{alert['source_vehicle']}** claims an accident at "
         f"{tuple(alert['incident_position'])}. **No accident happened**: this is the forged-alert test. |" if forged else
         f"| {alert['incident_time_s']:.3f} s | **{alert['source_vehicle']}** has the accident at "
         f"{tuple(alert['incident_position'])} on lane `{sc['incident_lane']}`. This is the only incident of the run. |"),
        f"| +0.000 ms | Alert **{alert['event_id']}** is created (type {alert['message_type']}, hop limit "
        f"{alert['hop_limit']}). From earlier beacons every vehicle knows its neighbours and their reputation; DBSCAN "
        f"gave {len({v['dbscan'] for v in sc['vehicles']} - {-1})} clusters with {roles.count('CH')} representatives, "
        f"{roles.count('BRIDGE')} isolated vehicles (bridges) and {roles.count('MEMBER')} members."
        + (f" Committee: {', '.join(c['committee']) or 'nobody'}." if c else "") + " |",
    ]
    shown = 0
    for ms, kind, text in events:
        if kind == "suppress":
            shown += 1
            if shown > max_suppress:
                continue
        lines.append(f"| +{ms:.3f} ms | {text} |")
    if n_sup > max_suppress:
        lines.append(f"| | ... and {n_sup - max_suppress} more vehicles suppress for the same kind of reason "
                     "(all listed in the decision table below). |")
    lines += ["", "## Final", "", "```", run_block(raw, proto, forged), "```", ""]
    if c and c["certificate"]:
        lines += ["## The certificate", "", "```json", json.dumps(c["certificate"], indent=2), "```", ""]
    if not forged:
        lines += ["## Same incident, same vehicles, every scheme", "",
                  "| Scheme | Frames on air | Certified alerts | Redundant | Receptions lost to collisions | Reachability | 90 % reached (ms) | RSU registered at (ms) |",
                  "|---|---|---|---|---|---|---|---|"]
        for p in config.PROTOCOLS:
            x, ev = raw["protocols"][p]["metrics"], raw["protocols"][p]["rsu_event"]
            lines.append(f"| {config.LABELS[p]} | {x['transmissions']} | {x['alert_tx']} | {x['redundant_tx']} | "
                         f"{x['collision_losses']} | {100 * x['reachability']:.1f} % | {x['t90_ms']:.1f} | "
                         + (f"{ev['delay_ms']:.2f} ({ev['receiving_rsu']}) |" if ev else "not received |"))
        if raw.get("forgery"):
            lines += ["", "## Forged-alert test on the same traffic", "",
                      f"Forger {raw['forgery']['forger']} claims an accident that did not happen "
                      f"(`python run.py explain {sc['run_id']} --forged voting_reputation`).", "",
                      "| Protection | Certificate | Honest vehicles that accepted it | RSU registered it |", "|---|---|---|---|"]
            for k, label_ in config.FORGERY.items():
                r = raw["forgery"]["variants"][k]
                cc, mm = r["corroboration"], r["metrics"]
                lines.append(f"| {label_} | {'not required' if cc is None else ('formed, ' + ('accepted' if cc['accepted'] else 'rejected: ' + cc['reason'])) if cc['certificate'] else cc['reason']} | "
                             f"{mm['honest_reached']} of {mm['honest_reachable']} | {'yes' if r['rsu_event'] else 'no'} |")
    lines += ["", f"## Every vehicle's message state and decision ({label})", "",
              "| Vehicle | Accepted (ms) | Hop | From | Distance (m) | Neighbours | Role | Tier | Reputation | Copies heard | Uncovered | Decision | Reason |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in sorted(P["vehicles"], key=lambda v: v["rx_ms"] if v["rx_ms"] is not None else v["decided_ms"] or 0):
        lines.append(f"| {v['id']} | {'-' if v['rx_ms'] is None else format(v['rx_ms'], '.2f')} | {v['hop']} | {v['from'] or '-'} | "
                     f"{v['dist_m']:.0f} | {v['neighbors']} | {v['role']} | {v['tier']} | {v['trust']:.2f} | {v['copies_heard']} | "
                     f"{'-' if v['uncovered'] is None else v['uncovered']} | {v['decision']} | {v['reason']} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ results tables
def _fmt(r, k, pct=False, dec=1):
    s = 100 if pct else 1
    return f"{s * r[k]:.{dec}f} ± {s * r[k + '_ci95']:.{dec}f}"


def results_md(summary, forgery):
    densities = sorted({r["density"] for r in summary})
    row = lambda d, p: next((x for x in summary if x["density"] == d and x["protocol"] == p), None)
    lines = [f"# Results: {config.TITLE}", "",
             f"Generated {datetime.date.today().isoformat()} by `python run.py experiment` from "
             "`results/processed/`. Values: mean ± 95 % CI over "
             f"{summary[0]['runs']:.0f} independent scenarios per density, one alert each. "
             "Nothing in this file is typed by hand.", "",
             "\"Frames on air\" counts everything transmitted for one alert: the proposal, the votes and every "
             "certified alert. All schemes in the headline comparison use the same corroboration (voting + BLS); "
             "only the forwarding rule differs.", ""]
    head = ("| Vehicles | Scheme | Frames on air | Certified alerts | Redundant alerts | Receptions lost | Reachability (%) | "
            "90 % reached (ms) | Last reached (ms) | CBR 100 ms (%) | Suppression (%) |")
    for title, protos in (("Headline comparison", config.BASELINES),
                          ("Ablations: the full method with one component removed", ["proposed"] + config.ABLATIONS)):
        lines += [f"## {title}", "", head, "|---|---|---|---|---|---|---|---|---|---|---|"]
        for d in densities:
            for p in protos:
                r = row(d, p)
                if r:
                    lines.append(f"| {d:.0f} | {config.LABELS[p]} | {_fmt(r, 'transmissions')} | {_fmt(r, 'alert_tx')} | "
                                 f"{_fmt(r, 'redundant_tx')} | {_fmt(r, 'collision_losses', dec=0)} | {_fmt(r, 'reachability', True)} | "
                                 f"{_fmt(r, 't90_ms')} | {_fmt(r, 't_last_ms')} | {_fmt(r, 'cbr_100ms', True)} | "
                                 f"{_fmt(r, 'suppression_ratio', True)} |")
        lines.append("")
    lines += ["## Corroboration: cost for a genuine alert", "",
              "| Vehicles | Genuine alerts that obtained a quorum (%) | Certified alert released at (ms) | Vote frames | Extra frames vs no voting | Extra time to 90 % vs no voting (ms) |",
              "|---|---|---|---|---|---|"]
    for d in densities:
        r, off = row(d, "proposed"), row(d, "no_security")
        if r and off:
            lines.append(f"| {d:.0f} | {_fmt(r, 'accepted', True)} | {_fmt(r, 'quorum_ms')} | {_fmt(r, 'vote_tx')} | "
                         f"{r['transmissions'] - off['transmissions']:+.1f} | {r['t90_ms'] - off['t90_ms']:+.1f} |")
    if forgery:
        lines += ["", "## Corroboration: the forged-alert test", "",
                  "On the same traffic, a misbehaving vehicle claims an accident that did not happen and its misbehaving "
                  "neighbours endorse it. \"Certificate formed\" = the forger found at least "
                  f"{config.QUORUM} colluders in range.", "",
                  "| Vehicles | Protection | Runs | Certificate formed (%) | Honest vehicles accepting the forged alert (%) | Forged event registered by an RSU (%) |",
                  "|---|---|---|---|---|---|"]
        for r in forgery:
            lines.append(f"| {r['density']:.0f} | {config.FORGERY[r['variant']]} | {r['runs']:.0f} | {_fmt(r, 'certificate_formed', True)} | "
                         f"{_fmt(r, 'accepted_share', True)} | {_fmt(r, 'rsu_registered', True)} |")
    lines += ["", "## RSU delivery", "",
              "All alerts: every incident where an RSU was reachable. Relayed alerts: incidents outside the direct "
              "range of both RSUs, which need vehicle relays (n = number of such incidents out of the runs).", "",
              "| Vehicles | Scheme | RSU success, all (%) | RSU delay, all (ms) | Relayed: n | Relayed: success (%) | Relayed: delay (ms) | Relayed: frames until RSU | Duplicate copies at RSUs |",
              "|---|---|---|---|---|---|---|---|---|"]
    for d in densities:
        for p in config.BASELINES:
            r = row(d, p)
            if r:
                lines.append(f"| {d:.0f} | {config.LABELS[p]} | {_fmt(r, 'rsu_received', True)} | {_fmt(r, 'rsu_delay_ms', dec=2)} | "
                             f"{r['rsu_relay_received_n']:.0f} | {_fmt(r, 'rsu_relay_received', True)} | "
                             f"{_fmt(r, 'rsu_relay_delay_ms', dec=2)} | {_fmt(r, 'rsu_relay_tx_before')} | "
                             f"{_fmt(r, 'rsu_dup_copies')} |")
    lines += ["", "## Change relative to the baselines (means)", "",
              "| Vehicles | Frames vs flooding | vs slotted 1-p | Collision losses vs flooding | vs slotted 1-p | t90 vs slotted 1-p |",
              "|---|---|---|---|---|---|"]
    for d in densities:
        g = {x["protocol"]: x for x in summary if x["density"] == d}
        if not {"flooding", "slotted1p", "proposed"} <= set(g):
            continue
        ch = lambda k, b: 100 * (g["proposed"][k] - g[b][k]) / g[b][k]
        lines.append(f"| {d:.0f} | {ch('transmissions', 'flooding'):+.0f} % | {ch('transmissions', 'slotted1p'):+.0f} % | "
                     f"{ch('collision_losses', 'flooding'):+.0f} % | {ch('collision_losses', 'slotted1p'):+.0f} % | "
                     f"{g['proposed']['t90_ms'] - g['slotted1p']['t90_ms']:+.1f} ms |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ dashboard
def dashboard(summary, forgery, sections, raw):
    """sections: [(heading, [(image path, caption)], optional preformatted text)]."""
    def img(path, alt):
        mime = "image/gif" if path.endswith(".gif") else "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<figure><img src="data:{mime};base64,{b64}" alt="{alt}"><figcaption>{alt}</figcaption></figure>'

    top = max(x["density"] for x in summary)
    g = {x["protocol"]: x for x in summary if x["density"] == top}
    cmp_ = lambda k, f: f"flooding {f(g['flooding'][k])} · slotted 1-p {f(g['slotted1p'][k])}"
    num, pct, ms = (lambda v: f"{v:.0f}"), (lambda v: f"{100 * v:.1f} %"), (lambda v: f"{v:.1f} ms")
    tiles = [(num(g["proposed"]["transmissions"]), f"frames on air per alert at {top:.0f} vehicles", cmp_("transmissions", num)),
             (num(g["proposed"]["collision_losses"]), "receptions lost to collisions", cmp_("collision_losses", num)),
             (pct(g["proposed"]["reachability"]), "vehicles reached", cmp_("reachability", pct)),
             (ms(g["proposed"]["t90_ms"]), "to reach 90 % of vehicles", cmp_("t90_ms", ms)),
             (pct(g["proposed"]["rsu_relay_received"]), "relayed alerts registered by an RSU", cmp_("rsu_relay_received", pct)),
             (ms(g["proposed"]["rsu_relay_delay_ms"]), "crash to RSU, relayed alerts", cmp_("rsu_relay_delay_ms", ms))]
    f = {x["variant"]: x for x in forgery if x["density"] == top}
    if f:
        tiles.append((pct(f["voting_reputation"]["accepted_share"]), "of honest vehicles accept a forged alert",
                      f"no reputation gate {pct(f['voting_only']['accepted_share'])} · no voting {pct(f['no_voting']['accepted_share'])}"))
        tiles.append((f"+{g['proposed']['transmissions'] - g['no_security']['transmissions']:.1f} frames, "
                      f"+{g['proposed']['t90_ms'] - g['no_security']['t90_ms']:.0f} ms", "cost of voting + BLS per alert",
                      "against the same scheme without corroboration"))
    tile_html = "".join(f'<div class="tile"><div class="big">{a}</div><div class="lbl">{b}</div>'
                        f'<div class="cmp">{c}</div></div>' for a, b, c in tiles)
    body = ""
    for heading, figs, text in sections:
        body += f"<h2>{heading}</h2>" + (f"<pre>{text}</pre>" if text else "") + "".join(img(p, alt) for p, alt in figs)
    sc = raw["scenario"]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Broadcast Storm Dashboard</title>
<style>
:root {{ --bg:#f9f9f7; --card:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --line:#e1e0d9; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0d0d0d; --card:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --line:#2c2c2a; }} }}
:root[data-theme="dark"] {{ --bg:#0d0d0d; --card:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --line:#2c2c2a; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 "Segoe UI",Arial,sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:32px; line-height:1.2; letter-spacing:-0.5px; margin:0 0 12px; }} h2 {{ font-size:23px; margin:36px 0 16px; }} .sub {{ color:var(--ink2); margin:0 0 24px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:20px; box-shadow:0 4px 18px #18354a08; }}
.big {{ font-size:28px; font-weight:700; }} .lbl {{ color:var(--ink2); }} .cmp {{ color:var(--ink2); font-size:13px; margin-top:6px; }}
figure {{ background:#fcfcfb; border:1px solid var(--line); border-radius:10px; margin:0 0 16px; padding:12px; }}
img {{ width:100%; height:auto; display:block; }} figcaption {{ color:#52514e; font-size:13px; padding-top:6px; }}
pre {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; overflow-x:auto; font-size:12.5px; line-height:1.4; }}
:root {{ --bg:#f3f6fb; --card:#ffffff; --ink:#17283f; --ink2:#64748b; --line:#dde6f1; }}
body {{ background:radial-gradient(ellipse at top left,#e5eafe,transparent 60%),var(--bg); }}
main {{ max-width:1280px; padding:48px 24px 80px; }}
h1 {{ max-width:1000px; font-size:clamp(28px,4vw,48px); letter-spacing:-1.5px; }}
.eyebrow {{ color:#7259d6; font-size:12px; font-weight:800; letter-spacing:2px; margin:12px 0; }}
.hero {{ background:linear-gradient(120deg,#172b48,#354b79); color:white; padding:36px; border-radius:28px; margin-bottom:28px; box-shadow:0 16px 48px #263b6b18; }}
.hero .sub {{ color:#c6d4ee; margin-bottom:0; }} .hero .eyebrow {{ color:#b8b0ff; }}
.tile {{ border-radius:20px; padding:24px; border-top:3px solid #8973e8; }} .big {{ color:#644fc1; font-size:30px; }}
figure {{ border-radius:20px; padding:20px; box-shadow:0 8px 24px #263b6b08; }}
.infrastructure {{ margin:36px 0; padding:28px; background:var(--card); border:1px solid var(--line); border-radius:24px; }}
.pipeline {{ display:flex; flex-wrap:wrap; gap:10px; margin:20px 0; }} .pipeline span {{ background:#edf0fc; color:#4a4382; border-radius:30px; padding:9px 18px; font-weight:600; }}
.route {{ background:#f3f5fc; border-left:4px solid #8973e8; border-radius:12px; padding:20px; margin-bottom:20px; }}
.route p {{ overflow-wrap:anywhere; }} .route small {{ color:#64748b; }}
.table-wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th,td {{ text-align:left; padding:13px; border-bottom:1px solid var(--line); }} th {{ color:#64559d; background:#f5f6fc; }}
</style></head><body><main>
<div class="hero"><div class="eyebrow">CONNECTED CITY · EMERGENCY INTELLIGENCE</div>
<h1>{config.TITLE}</h1>
<p class="sub">SUMO road network with two road-side units, IEEE 802.11p channel model, {summary[0]['runs']:.0f} scenarios per density,
exactly one incident per scenario. Showcase run: {sc['run_id']} (event {sc['alert']['event_id']}), the fixed demo scenario.
Every value is read from results/processed and results/raw.</p></div>
<div class="tiles">{tile_html}</div>{presentation.infrastructure_panel(raw)}{body}
</main></body></html>"""
    path = os.path.join(config.RESULTS_DIR, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
