"""
Build docs/End_to_End_Workflow_Verified_SUMO_Snapshots.pdf: the end-to-end workflow explained with the 11 genuine
SUMO-GUI snapshots of the final verified demonstration (portal/assets/sumo/, run d200_r02).

Read-only with respect to the project: it reads the snapshot manifest, the snapshots and the recorded run, and writes
only docs/workflow_pdf/workflow_document.html and the PDF. Before writing anything it checks every snapshot's stage,
caption, run ID and SUMO time against the recorded run, and every number in the text is read from that record (or from
config.py for design parameters).

    python docs/workflow_pdf/build_workflow_pdf.py

Needs: Microsoft Edge or Google Chrome (headless printing) and pypdfium2 (pip install pypdfium2), used to read back the
page on which each section starts, for the table of contents.
"""
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)                                    # config / experiment resolve paths from the project root

import config        # noqa: E402
import demo          # noqa: E402  (display helpers only: stage_state, route_progress, counters, final_screen, colours)
import experiment    # noqa: E402
import rsu           # noqa: E402

SNAP_DIR = ROOT / "portal" / "assets" / "sumo"
MIRROR_DIR = ROOT / "documentation_website" / "portal" / "assets" / "sumo"
HTML_OUT = HERE / "workflow_document.html"
PDF_OUT = ROOT / "docs" / "End_to_End_Workflow_Verified_SUMO_Snapshots.pdf"
TITLE = "Trust-Aware Vehicular Emergency Alerts"
SUBTITLE = "End-to-End Workflow Explained with Verified SUMO Snapshots"
# snapshot key -> (scheme, forged variant) of the replay it was taken in; rsu / forged were taken after it finished
REPLAYS = {"votes": ("proposed", None), "certificate": ("proposed", None), "forwarding": ("proposed", None),
           "duplicates": ("proposed", None), "flooding": ("flooding", None), "route": ("ch_route", None),
           "rsu": ("proposed", None), "forged": ("proposed", "voting_reputation")}
LEAD_STATUS = "Live SUMO traffic: vehicles drive normally; no alert exists yet"
FINISHED = ("rsu", "forged")
STAGE_TITLES = [(1, "SUMO initialisation and normal traffic"), (2, "Incident"), (3, "Alert creation"),
                (4, "Clustering and cluster-head election"), (5, "Committee vote collection"),
                (6, "Certificate creation and verification"), (7, "Forwarding and route formation"),
                (8, "RSU receipt and registration"), (9, "Duplicate copies and their outcomes"),
                (10, "Forged-alert rejection"), (11, "Final traffic state and end-to-end outcome")]
FIGURE_ORDER = [(1, "traffic"), (2, "incident"), (3, "alert"), (4, "clusters"), (5, "votes"), (6, "certificate"),
                (7, "forwarding"), (8, "route"), (9, "flooding"), (10, "rsu"), (11, "duplicates"), (12, "forged"),
                (13, "final")]
FIG = {k: n for n, k in FIGURE_ORDER}
FIG_W = 156                     # mm: snapshot width on the page (A4 text width is 176 mm), original aspect ratio
BAND = (326, 251, 1190, 326)    # px: indicator boxes and both status lines, the same in every snapshot (measured)


# ---------------------------------------------------------------------------------------------- evidence checks
def bin_end(radio_ms):
    """The replay shows radio time min(bin end, last event); its status line was computed at the bin end."""
    return math.ceil(radio_ms / demo.BIN_MS - 1e-9) * demo.BIN_MS


def at(raw, key, entries):
    """(record, alert, radio time hi) a replay snapshot was computed at."""
    proto, forged = REPLAYS[key]
    P, a, _ = demo.report.pick(raw, proto, forged)
    return P, a, (math.inf if key in FINISHED else bin_end(entries[key]["radio_ms"]))


def check_snapshots(manifest, raw):
    """Every snapshot's stage and caption must be what the recorded run gives at its radio time; same run, same
    SUMO time, original pixels. Returns {key: entry}."""
    sc, alert = raw["scenario"], raw["scenario"]["alert"]
    assert manifest["run_id"] == sc["run_id"] and manifest["seed"] == sc["seed"], "manifest and record differ"
    assert manifest["event_id"] == alert["event_id"]
    entries = {e["key"]: e for e in manifest["snapshots"]}
    assert set(entries) == {k for _, k in FIGURE_ORDER} and all(e["file"] for e in entries.values()), \
        "one captured snapshot per figure expected"
    # the durable facts the demo stores with the snapshots: the run completed (every replay check passed), its
    # record is byte-for-byte the tracked one, and SUMO's own log
    assert manifest.get("completed") is True, "the demo run that captured the snapshots did not complete"
    assert manifest["record_fingerprint"] == demo.record_fingerprint(raw), "snapshots are from a different record"
    assert "sumo_log" in manifest and manifest["lead_in_s"][1] == sc["incident_time_s"]
    total = len(sc["vehicles"])
    x, y = sc["incident_xy"]
    roles = [v["role"] for v in sc["vehicles"]]
    labels = [v["dbscan"] for v in sc["vehicles"]]
    expected = {
        "traffic": ("Live traffic", LEAD_STATUS),
        "incident": ("Incident", f"Incident: {sc['source_id']} crashes at ({x:.0f}, {y:.0f}) m at t = "
                                 f"{sc['incident_time_s']:.0f} s (staged incident)"),
        "alert": ("Alert", f"Alert {alert['event_id']} created by {alert['source_vehicle']}: type "
                           f"{alert['message_type']}, hop limit {alert['hop_limit']}"),
        "clusters": ("Cluster / CH", f"Cluster / CH: {len(set(labels) - {-1})} clusters (DBSCAN "
                                     f"{config.DBSCAN_EPS_M:.0f} m), {roles.count('CH')} cluster heads (trust >= "
                                     f"{config.TRUST_CH_THRESHOLD}), {labels.count(-1)} isolated"),
        "final": ("RSU", demo.final_screen(raw)["banner"][0]),
    }
    for key, (proto, forged) in REPLAYS.items():
        P, a, hi = at(raw, key, entries)
        index, line, _ = demo.stage_state(P, a, hi, finished=key in FINISHED, forged=bool(forged), total=total)
        if key == "route":                                             # the CH-route status names the hops
            hops = demo.route_progress(P, raw["infrastructure"]["route"]["vehicle_ids"], hi)
            line = (f"Route: {' -> '.join(hops)}" + ("" if hops[-1].startswith("RSU") else " ...")
                    + f"  |  {demo.counters(P, a, hi)['reached']}/{total} hold the alert")
        expected[key] = (demo.STAGES[index], line)
    for key, e in entries.items():
        stage, caption = expected[key]
        assert e["stage"] == stage, (key, e["stage"], stage)
        assert e["caption"] == caption, (key, e["caption"], caption)
        assert e["run_id"] == sc["run_id"], key
        if key == "final":
            assert e["sim_time_s"] > sc["incident_time_s"], key            # the clock runs again
        elif key == "traffic":                                             # live traffic before the incident
            assert manifest["lead_in_s"][0] <= e["sim_time_s"] < sc["incident_time_s"], key
        else:
            assert e["sim_time_s"] == sc["incident_time_s"], key           # paused at the incident second
        with Image.open(SNAP_DIR / e["file"]) as im:
            assert im.size == (1518, 1097), (key, im.size)
        mirror = MIRROR_DIR / e["file"]
        if mirror.exists() and mirror.read_bytes() != (SNAP_DIR / e["file"]).read_bytes():
            print(f"warning: {mirror} differs from {SNAP_DIR / e['file']}")
    return entries


# ---------------------------------------------------------------------------------------------- facts from the record
def ms(v, d=1):
    return f"{v:.{d}f}"


def facts(raw, entries, manifest):
    sc, alert = raw["scenario"], raw["scenario"]["alert"]
    V = {v["id"]: v for v in sc["vehicles"]}
    misbehaving = {v["id"] for v in sc["vehicles"] if v["malicious"]}
    prop, flood, chr_ = (raw["protocols"][k] for k in ("proposed", "flooding", "ch_route"))
    fr = raw["forgery"]["variants"]["voting_reputation"]
    vo, nv = raw["forgery"]["variants"]["voting_only"], raw["forgery"]["variants"]["no_voting"]
    labels = [v["dbscan"] for v in sc["vehicles"]]
    roles = [v["role"] for v in sc["vehicles"]]
    c = prop["corroboration"]
    for other in (flood, chr_):                                          # one committee for the three genuine replays
        oc = other["corroboration"]
        assert (oc["committee"], oc["votes_counted"], oc["certificate"]["signers"]) == \
               (c["committee"], c["votes_counted"], c["certificate"]["signers"])
    tx = sorted(prop["transmissions"], key=lambda t: t["start_ms"])
    assert tx[0]["kind"] == "PROPOSAL" and tx[0]["sender"] == alert["source_vehicle"]
    votes = [t for t in tx if t["kind"] == "VOTE"]
    third = next(t for t in votes if t["sender"] == c["votes_counted"][-1])
    release = next(t for t in tx if t["kind"] == "ALERT" and t["sender"] == alert["source_vehicle"])
    relays = [t for t in tx if t["kind"] == "ALERT" and t["sender"] != alert["source_vehicle"]]
    dec = lambda P, d: sum(v["decision"] == d for v in P["vehicles"])
    first = lambda P: {u: min((r for r in P["rsu_receptions"] if r["rsu"] == u), key=lambda r: r["delay_ms"])
                       for u in sorted({r["rsu"] for r in P["rsu_receptions"]})}
    copies = lambda P, u, s: sum(r["rsu"] == u and r["status"].startswith(s) for r in P["rsu_receptions"])
    route = raw["infrastructure"]["route"]
    ctx = sorted(chr_["transmissions"], key=lambda t: t["start_ms"])
    head = route["vehicle_ids"][1]
    cprop = next(t for t in ctx if t["kind"].startswith("CPROPOSAL"))
    cvotes = [t for t in ctx if t["kind"].startswith("CVOTE")]
    hrelay = next(t for t in ctx if t["kind"] == "ALERT" and t["sender"] == head)
    head_rx = next(v["rx_ms"] for v in chr_["vehicles"] if v["id"] == head)
    fc = fr["corroboration"]
    assert not any(V[i]["malicious"] for i in fc["committee"]) and all(V[i]["malicious"] for i in fc["voters"])
    assert not any(t["sender"] in fc["committee"] for t in fr["transmissions"]), "the honest committee stays silent"
    frelease = next(t for t in sorted(fr["transmissions"], key=lambda t: t["start_ms"]) if t["kind"] == "ALERT")
    frsu = fr["rsu_receptions"][0]
    # the last recorded event of the proposed replay (the 'rsu' snapshot's radio time)
    events = [(t["end_ms"], "frame end", t["sender"]) for t in prop["transmissions"]] + \
             [(r["delay_ms"], "RSU copy", r["rsu"]) for r in prop["rsu_receptions"]] + \
             [(v["rx_ms"] or 0, "reception", v["id"]) for v in prop["vehicles"]] + \
             [(v["decided_ms"] or 0, v["decision"], v["id"]) for v in prop["vehicles"]]
    last = max(events)
    assert last[1] == "SUPPRESS" and f"{last[0]:.1f}" == f"{entries['rsu']['radio_ms']:.1f}", last
    honest = [v for v in sc["vehicles"] if not v["malicious"]]
    lead_in = demo.run.__defaults__[demo.run.__code__.co_varnames.index("lead_in_s")]
    snap = {}                                                          # counters on screen at each replay snapshot
    for key in REPLAYS:
        P, a, hi = at(raw, key, entries)
        cnt = demo.counters(P, a, hi, misbehaving)
        cnt["relays"] = sum(t["kind"] == "ALERT" and t["sender"] != a["source_vehicle"] and t["start_ms"] < hi
                            for t in P["transmissions"])
        cnt["voters"] = [t["sender"] for t in sorted(P["transmissions"], key=lambda t: t["start_ms"])
                         if t["kind"] == "VOTE" and t["start_ms"] < hi]
        cnt["radio"] = f"{entries[key]['radio_ms']:.1f}"
        cnt["rsu_copies"] = [(r["rsu"], r["status"].split(":")[0]) for r in P["rsu_receptions"] if r["delay_ms"] < hi]
        snap[key] = cnt
    import sqlite3                                                     # the tracked outbox of the normal experiment run
    with sqlite3.connect(Path(config.RESULTS_DIR) / "infrastructure" / "backhaul.sqlite3") as con:
        outbox = con.execute("select status from dispatch where run_id = ? and event_id = ?",
                             (sc["run_id"], alert["event_id"])).fetchone()
    assert outbox == ("QUEUED_LOCAL",), outbox
    assert snap["votes"]["transmissions"] == 1 + len(snap["votes"]["voters"])        # proposal + votes so far
    def tr(ids):                                                       # trust range; 3 decimals for near-zero trust
        lo, hi = min(V[i]["trust"] for i in ids), max(V[i]["trust"] for i in ids)
        d = 3 if hi < 0.1 else 2
        return f"{lo:.{d}f}–{hi:.{d}f}"
    t90 = lambda P: "not reached" if math.isnan(P["metrics"]["t90_ms"]) else f"{P['metrics']['t90_ms']:.1f} ms"
    f = dict(
        run=sc["run_id"], seed=sc["seed"], density=sc["density"], run_index=sc["run"], n=len(sc["vehicles"]),
        n_mis=len(misbehaving), n_honest=len(honest),
        n_trusted=sum(v["trust"] >= config.TRUST_CH_THRESHOLD for v in sc["vehicles"]),
        honest_all_trusted=all(v["trust"] >= config.TRUST_CH_THRESHOLD for v in honest),
        mis_all_below=all(V[i]["trust"] < config.TRUST_CH_THRESHOLD for i in misbehaving),
        t_inc=f"{sc['incident_time_s']:.0f}", lead_first=f"{sc['incident_time_s'] - (lead_in - 1):.0f}",
        lead_s=lead_in, src=alert["source_vehicle"], src_speed=f"{V[alert['source_vehicle']]['speed']:.1f}",
        src_role=V[alert["source_vehicle"]]["role"], src_trust=f"{V[alert['source_vehicle']]['trust']:.2f}",
        lane=sc["incident_lane"], x=f"{sc['incident_xy'][0]:.2f}", y=f"{sc['incident_xy'][1]:.2f}",
        event=alert["event_id"], mtype=alert["message_type"], seq=alert["sequence_number"],
        hop=alert["hop_limit"], created=f"{alert['created_s']:.0f}",
        rsu1=sc["rsus"][0], rsu2=sc["rsus"][1],
        n_clusters=len(set(labels) - {-1}), n_ch=roles.count("CH"), n_member=roles.count("MEMBER"),
        n_bridge=roles.count("BRIDGE"), n_isolated=labels.count(-1),
        committee=", ".join(c["committee"]), counted=", ".join(c["votes_counted"]),
        late=" and ".join(v for v in c["committee"] if v not in c["votes_counted"]),
        vote_starts=", ".join(f"{t['sender']} {ms(t['start_ms'], 2)}" for t in votes),
        third=third["sender"], third_end=ms(third["end_ms"], 2), quorum=ms(prop["metrics"]["quorum_ms"], 2),
        rel_start=ms(release["start_ms"], 2), rel_end=ms(release["end_ms"], 2),
        signers=", ".join(c["certificate"]["signers"]), n_signers=len(c["certificate"]["signers"]),
        verdict=c["reason"], prop_start=ms(tx[0]["start_ms"], 2), prop_end=ms(tx[0]["end_ms"], 2),
        relays25=", ".join(f"{t['sender']} at {ms(t['start_ms'])} ms" for t in relays
                           if t["start_ms"] < bin_end(entries["forwarding"]["radio_ms"])),
        p_frames=prop["metrics"]["transmissions"], p_fwd=dec(prop, "FORWARD"), p_sup=dec(prop, "SUPPRESS"),
        p_drop=dec(prop, "DROP"), p_recv=prop["metrics"]["received"], p_lost=prop["metrics"]["collision_losses"],
        p_t90=t90(prop), p_sr=f"{prop['metrics']['suppression_ratio']:.2f}",
        p_rsu=prop["rsu_event"]["receiving_rsu"], p_from=prop["rsu_event"]["received_from"],
        p_arr=ms(prop["rsu_event"]["arrival_ms"]), p_reg=ms(prop["rsu_event"]["delay_ms"]),
        p_arr3=f"{prop['rsu_event']['arrival_ms']:.3f}", p_reg3=f"{prop['rsu_event']['delay_ms']:.3f}",
        p_dups=prop["rsu_event"]["duplicate_copies"], p_hops=prop["rsu_event"]["hops"],
        p_dup2=copies(prop, "RSU-2", "DUPLICATE"), p_dup1=copies(prop, "RSU-1", "DUPLICATE"),
        p_r1_from=first(prop)["RSU-1"]["sender"], p_r1_arr=ms(first(prop)["RSU-1"]["arrival_ms"]),
        p_r1_reg=ms(first(prop)["RSU-1"]["delay_ms"]), last_v=last[2],
        f_frames=flood["metrics"]["transmissions"], f_recv=flood["metrics"]["received"],
        f_fwd=dec(flood, "FORWARD"), f_drop=dec(flood, "DROP"), p_duprx=prop["metrics"]["dup_rx"],
        f_lost=f"{flood['metrics']['collision_losses']:,}", f_t90=t90(flood),
        f_sr=f"{flood['metrics']['suppression_ratio']:.2f}",
        f_rsu=flood["rsu_event"]["receiving_rsu"], f_from=flood["rsu_event"]["received_from"],
        f_arr=ms(flood["rsu_event"]["arrival_ms"]), f_reg=ms(flood["rsu_event"]["delay_ms"]),
        f_dups=flood["rsu_event"]["duplicate_copies"], f_r2_from=first(flood)["RSU-2"]["sender"],
        f_r2_arr=ms(first(flood)["RSU-2"]["arrival_ms"]), f_r2_reg=ms(first(flood)["RSU-2"]["delay_ms"]),
        f_dup1=copies(flood, "RSU-1", "DUPLICATE"), f_dup2=copies(flood, "RSU-2", "DUPLICATE"),
        route=" → ".join(route["vehicle_ids"]), route_m=f"{route['distance_m']:.1f}", route_hops=route["hops"],
        head=head, head_trust=f"{V[head]['trust']:.2f}", head_rx=ms(head_rx), head_kind=cprop["kind"],
        cprop=ms(cprop["start_ms"]), cvote_from=", ".join(t["sender"] for t in cvotes), n_cvotes=len(cvotes),
        cvote_first=ms(cvotes[0]["start_ms"]), cvote_last=ms(cvotes[-1]["end_ms"]),
        hrelay_start=ms(hrelay["start_ms"]), hrelay_end=ms(hrelay["end_ms"]),
        c_arr=ms(chr_["rsu_event"]["arrival_ms"]), c_reg=ms(chr_["rsu_event"]["delay_ms"]),
        c_arr3=f"{chr_['rsu_event']['arrival_ms']:.3f}", c_reg3=f"{chr_['rsu_event']['delay_ms']:.3f}",
        c_dups=chr_["rsu_event"]["duplicate_copies"], c_frames=chr_["metrics"]["transmissions"],
        c_lost=chr_["metrics"]["collision_losses"], c_recv=chr_["metrics"]["received"],
        c_sup=dec(chr_, "SUPPRESS"), c_sr=f"{chr_['metrics']['suppression_ratio']:.2f}", c_t90=t90(chr_),
        c_missed=len(sc["vehicles"]) - chr_["metrics"]["received"], c_rsus=", ".join(chr_["rsu_event"]["rsus_that_received"]),
        forger=raw["forgery"]["forger"], forger_trust=f"{V[raw['forgery']['forger']]['trust']:.3f}",
        fevent=raw["forgery"]["alert"]["event_id"],
        fx=f"{raw['forgery']['alert']['incident_position'][0]:.0f}",
        fy=f"{raw['forgery']['alert']['incident_position'][1]:.0f}",
        fcommittee=", ".join(fc["committee"]), n_fcommittee=len(fc["committee"]), fcommittee_trust=tr(fc["committee"]),
        fvoters=", ".join(fc["voters"]), n_fvoters=len(fc["voters"]), fvoters_trust=tr(fc["voters"]),
        n_fcounted=len(fc["votes_counted"]), fsigners=", ".join(fc["certificate"]["signers"]),
        n_fsigners=len(fc["certificate"]["signers"]), freason=fc["reason"],
        frel_start=ms(frelease["start_ms"]), frel_end=ms(frelease["end_ms"]),
        freject=dec(fr, "REJECT"), fhonest=fr["metrics"]["honest_reached"], fframes=fr["metrics"]["transmissions"],
        flost=fr["metrics"]["collision_losses"],
        frsu=frsu["rsu"], frsu_arr=ms(frsu["arrival_ms"]), frsu_reg=ms(frsu["delay_ms"]), frsu_status=frsu["status"],
        vo_honest=vo["metrics"]["honest_reached"], vo_status=vo["rsu_receptions"][0]["status"],
        vo_rsu=vo["rsu_receptions"][0]["rsu"], nv_honest=nv["metrics"]["honest_reached"],
        nv_status=nv["rsu_receptions"][0]["status"],
        backhaul=raw["infrastructure"]["backhaul"],
        captured=manifest["captured"], t_final=f"{entries['final']['sim_time_s']:.0f}",
        steps_final=f"{entries['final']['sim_time_s'] - sc['incident_time_s']:.0f}",
        date=(lambda d: f"{d.day} {d:%B %Y}")(__import__("datetime").datetime.strptime(manifest["captured"],
                                                                                      "%Y-%m-%d %H:%M:%S")),
        final=demo.final_screen(raw), snap=snap, sumo_log=manifest["sumo_log"], lead_in=manifest["lead_in_s"],
        t_traffic=f"{entries['traffic']['sim_time_s']:.0f}", fingerprint=manifest["record_fingerprint"][:16],
        db=f"{Path(config.RESULTS_DIR).as_posix()}/infrastructure/backhaul.sqlite3",
        seed_formula=f"{config.BASE_SEED} + 100 × {sc['density']} + {sc['run']}",
    )
    log = manifest["sumo_log"]
    if len(log) == 1 and alert["source_vehicle"] in log[0] and "emergency braking" in log[0]:
        when = log[0].rsplit("time=", 1)[-1].rstrip(".")
        f["log_sentence"] = (f"a single warning, the emergency braking of the crashed vehicle {alert['source_vehicle']} "
                             f"(SUMO time {when} s); no other vehicle produced a warning.")
    else:
        f["log_sentence"] = f"{len(log)} line(s): " + " | ".join(log)
    assert sc["seed"] == config.BASE_SEED + 100 * sc["density"] + sc["run"]
    assert f["honest_all_trusted"] and f["mis_all_below"], "the text states that trust separates the two groups"
    assert vo["corroboration"]["accepted"] and not fc["accepted"] and f["fhonest"] == 0
    assert f["final"]["scheme"] == config.LABELS["ch_route"] and f["backhaul"]["dispatch"] == "QUEUED_LOCAL"
    assert f["n_ch"] == f["n_clusters"], "the text states one cluster head per cluster"
    assert len(fc["votes_counted"]) == config.QUORUM and chr_["rsu_event"]["rsus_that_received"] == ["RSU-2"]
    return f


# ---------------------------------------------------------------------------------------------- document text
def css():
    return """
@page { size: A4; margin: 15mm 17mm 16mm 17mm;
  @bottom-left { content: "Trust-Aware Vehicular Emergency Alerts · run d200_r02 (seed 30002)"; font: 7.5pt "Segoe UI", sans-serif; color: #7b8794; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 7.5pt "Segoe UI", sans-serif; color: #7b8794; } }
@page :first { @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: Cambria, Georgia, serif; font-size: 10pt; line-height: 1.35; color: #1f2933; }
h1, h2, h3, h4, .sans { font-family: "Segoe UI", Calibri, Arial, sans-serif; }
h1 { font-size: 17pt; font-weight: 600; color: #17375e; margin: 0 0 3.5mm; padding-bottom: 1.6mm; border-bottom: 0.7pt solid #b9c6d4; }
h2 { font-size: 13.5pt; font-weight: 600; color: #17375e; margin: 0 0 2.4mm; }
h2 .num { color: #5b7290; font-weight: 600; }
h3 { font-size: 11pt; font-weight: 600; color: #17375e; margin: 4mm 0 1.4mm; }
p { margin: 0 0 2mm; }
ul { margin: 0 0 2mm; padding-left: 5mm; }
li { margin: 0 0 0.8mm; }
.section, .stage { break-before: page; }
.keep { break-inside: avoid; }
figure { margin: 0 0 1mm; break-inside: avoid; break-after: avoid; }
figure img.full { display: block; width: %(FIG_W)smm; height: auto; margin: 0 auto; border: 0.5pt solid #9aa8b6; }
.detail { position: relative; overflow: hidden; width: %(FIG_W)smm; margin: 1.2mm auto 0; border: 0.5pt solid #9aa8b6; }
.detail img { position: absolute; display: block; max-width: none; }
.nb { white-space: nowrap; }
figcaption { font: 8.5pt/1.35 "Segoe UI", Calibri, sans-serif; color: #2f3d4c; margin-top: 1.5mm; }
figcaption b { color: #17375e; }
.src { color: #6b7785; }
.blk { margin: 0; break-inside: avoid; }
.blk h4 { font-size: 9pt; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; color: #2a5a8c; margin: 2.2mm 0 0.5mm; }
.blk p { margin: 0 0 1mm; }
.ev { background: #f4f6f9; border: 0.5pt solid #dde3ea; border-radius: 1.5mm; padding: 1.5mm 3mm 1.2mm; }
.ev ul { margin: 0; padding-left: 4.2mm; font-size: 8.9pt; line-height: 1.32; }
.ev li { margin: 0 0 0.5mm; }
.note { background: #f3f6fa; border-left: 2.4pt solid #6f8fb3; padding: 2.2mm 3.4mm; margin: 2.5mm 0 3mm; break-inside: avoid; }
.note p:last-child { margin-bottom: 0; }
.warn { background: #fff8e6; border-left-color: #c9952b; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.6pt; color: #233; }
q { quotes: "“" "”"; font-family: "Segoe UI", Calibri, sans-serif; font-size: 9pt; }
table { border-collapse: collapse; width: 100%; font: 8.9pt/1.32 "Segoe UI", Calibri, sans-serif; margin: 1.5mm 0 3mm; }
th, td { border-bottom: 0.5pt solid #d5dde6; padding: 1mm 1.6mm; text-align: left; vertical-align: top; }
th { background: #eef2f7; color: #17375e; font-weight: 600; }
td.r, th.r { text-align: right; white-space: nowrap; }
.sw { display: inline-block; width: 3.2mm; height: 3.2mm; border: 0.5pt solid #555; vertical-align: -0.5mm; margin-right: 1.4mm; }
.ring { border-radius: 50%; border: 0.9pt solid #000; background: none; }
.line { height: 0; border: 0; border-top: 2.2pt solid; width: 4.2mm; vertical-align: 0.8mm; }
.flow { display: flex; align-items: stretch; margin: 2.5mm 0 3.5mm; }
.flow div.b { flex: 1 1 0; border: 0.7pt solid #7f97b2; background: #f3f6fa; border-radius: 1.4mm; padding: 1.8mm 1mm; text-align: center; font: 600 8pt/1.2 "Segoe UI", sans-serif; color: #17375e; display: flex; align-items: center; justify-content: center; }
.flow div.a { flex: 0 0 4.5mm; text-align: center; color: #6f8fb3; font: 10pt "Segoe UI"; align-self: center; }
.title { height: 258mm; display: flex; flex-direction: column; justify-content: center; }
.title .over { font: 600 9pt "Segoe UI"; letter-spacing: 0.16em; text-transform: uppercase; color: #5b7290; margin-bottom: 5mm; }
.title .main { font: 600 27pt/1.15 "Segoe UI", sans-serif; color: #17375e; }
.title .desc { font: italic 12pt Cambria, serif; color: #44546a; margin: 3mm 0 9mm; }
.title .sub { font: 400 17pt/1.25 "Segoe UI", sans-serif; color: #1f2933; border-top: 0.8pt solid #b9c6d4; border-bottom: 0.8pt solid #b9c6d4; padding: 4mm 0; }
.title .meta { margin-top: 9mm; font: 10.5pt/1.6 "Segoe UI", sans-serif; color: #1f2933; }
.title .meta b { color: #17375e; }
.title .stmt { margin-top: 7mm; font: 10.5pt/1.45 Cambria, serif; color: #2f3d4c; max-width: 150mm; }
.title .foot { margin-top: 16mm; font: 8.5pt/1.45 "Segoe UI", sans-serif; color: #6b7785; max-width: 160mm; }
.toc { list-style: none; padding: 0; margin: 4mm 0 0; font: 10pt/1.6 "Segoe UI", sans-serif; }
.toc li { display: flex; align-items: baseline; margin: 0; }
.toc li .d { flex: 1 1 auto; border-bottom: 0.7pt dotted #9aa8b6; margin: 0 1.5mm; transform: translateY(-0.9mm); }
.toc li .p { flex: 0 0 auto; min-width: 7mm; text-align: right; }
.toc li.l1 { font-weight: 600; color: #17375e; margin-top: 2mm; }
.toc li.l2 { padding-left: 6mm; }
td.fig { white-space: nowrap; }
""".replace("%(FIG_W)s", str(FIG_W))


def esc(s):
    return html.escape(str(s), quote=False)


def swatch(rgba, kind="sq"):
    r, g, b = rgba[:3]
    if kind == "ring":
        return '<span class="sw ring"></span>'
    if kind == "line":
        return f'<span class="sw line" style="border-top-color: rgb({r},{g},{b})"></span>'
    return f'<span class="sw" style="background: rgb({r},{g},{b})"></span>'


def figure(no, e, title):
    rel = os.path.relpath(SNAP_DIR / e["file"], HERE).replace(os.sep, "/")
    if e["key"] == "final":
        when = "after the radio replays, SUMO clock running again"
    elif e["key"] == "traffic":
        when = "live traffic before the incident, SUMO clock running"
    elif e["radio_ms"] is None:
        when = "before the radio replay, SUMO clock paused"
    else:
        when = (f"radio time +{e['radio_ms']:.1f} ms" + (" (replay finished)" if e["key"] in FINISHED else "")
                + ", SUMO clock paused")
    scheme = f" Scheme replayed: {esc(e['scheme'])}." if e["scheme"] else ""
    # the strip under the snapshot shows the SAME image file, scaled up and clipped by CSS to the indicator and status
    # lines (no image is created or edited)
    x0, y0, x1, y1 = BAND
    k = FIG_W / (x1 - x0)                                              # mm per pixel in the strip
    strip = (f'<div class="detail" style="height:{(y1 - y0) * k:.2f}mm"><img src="{rel}" alt="" '
             f'style="width:{1518 * k:.2f}mm; left:-{x0 * k:.2f}mm; top:-{y0 * k:.2f}mm"></div>')
    return (f'<figure><img class="full" src="{rel}" alt="SUMO-GUI snapshot: {esc(title)}">{strip}'
            f'<figcaption><b>Figure {no}. {esc(title)}</b> ('
            f'{"indicator: no stage active yet" if e["key"] == "traffic" else "indicator stage: " + esc(e["stage"])}). Run '
            f'{esc(e["run_id"])}, SUMO time t = {e["sim_time_s"]:.0f} s, {when}.{scheme} The strip below the '
            f'snapshot enlarges its indicator and status lines. <span class="src">Source: '
            f'portal/assets/sumo/{esc(e["file"])}.</span></figcaption></figure>')


def blocks(what, why, nxt, evidence):
    ev = "".join(f"<li>{x}</li>" for x in evidence)
    return (f'<div class="blk"><h4>What is happening</h4>{what}</div>'
            f'<div class="blk"><h4>Why this stage matters</h4>{why}</div>'
            f'<div class="blk"><h4>What happens next</h4>{nxt}</div>'
            f'<div class="blk"><h4>Evidence shown</h4><div class="ev"><ul>{ev}</ul></div></div>')


def stage(sid, num, title, body):
    return f'<section class="stage" id="{sid}"><h2><span class="num">Stage {num} –</span> {esc(title)}</h2>{body}</section>'


def build_html(f, E, toc_pages):
    D, s = demo, f["snap"]
    q = lambda t: f"<q>{esc(t)}</q>"
    toc_items = ([("l1", "s1", "1&nbsp;&nbsp;System overview"), ("l1", "s2", "2&nbsp;&nbsp;Sequential workflow"),
                  ("l2", "s2r", "How to read the snapshots")]
                 + [("l2", f"st{i}", f"Stage {i} – {t}") for i, t in STAGE_TITLES]
                 + [("l1", "s3", "3&nbsp;&nbsp;Results and limitations"), ("l1", "s4", "4&nbsp;&nbsp;End-to-end summary"),
                    ("l1", "s5", "Source and evidence note")])
    toc = "".join(f'<li class="{c}"><span class="t">{t}</span><span class="d"></span>'
                  f'<span class="p">{toc_pages.get(k, "")}</span></li>' for c, k, t in toc_items)
    rsu1, rsu2 = f["rsu1"], f["rsu2"]
    legend_rows = [
        (swatch(D.NEUTRAL), "Grey vehicle", "Ordinary traffic: no alert, or a vehicle that has not received it"),
        (swatch(D.HAS), "Blue vehicle", "Holds the verified (certified and accepted) alert"),
        (swatch(D.TX), "Orange vehicle or ring", f"Transmitting: its frame was on air during the last {D.BIN_MS} ms of radio time"),
        (swatch(D.CRASH), "Red vehicle or disc", "Incident vehicle, i.e. the alert source (in the forged test: the forger)"),
        (swatch(D.VOTE), "Pink vehicle or ring", "Committee vote (Votes stage), or a vote frame on air"),
        (swatch(D.MEMBER), "Teal vehicle", "Cluster member (Cluster / CH stage only)"),
        (swatch(D.HEAD, "ring"), "Black ring", "Cluster head (CH)"),
        (swatch(D.ROUTE, "line"), "Purple line", "CH-to-CH route hop already traversed"),
        (swatch(D.HAS, "line"), "Thin blue line",
         f"A recorded reception (sender to receiver); it fades after {D.LINK_FRAMES} animation frames"),
        (swatch(D.RSU_IDLE), "Grey RSU square", "RSU listening: no copy registered or rejected yet"),
        (swatch(D.RSU_OK), "Dark green RSU", "REGISTERED: the event was registered at this RSU"),
        (swatch(D.RSU_DUP), "Light green RSU", "DUPLICATE: a copy of an event already registered"),
        (swatch(D.RSU_BAD), "Red RSU", "REJECTED: the copy failed verification or the plausibility checks"),
        (swatch(D.STAGE_NOW), "Yellow indicator box", "The current stage"),
        (swatch(D.STAGE_DONE), "Light grey indicator box", "A stage that has occurred (the RSU box also once an RSU holds a copy)"),
        (swatch(D.STAGE_FUTURE), "White indicator box", "A stage that has not occurred (yet), including a skipped stage"),
    ]
    legend = "".join(f"<tr><td>{w}{esc(n)}</td><td>{esc(m)}</td></tr>" for w, n, m in legend_rows)
    v, b, t, rs = config.BLS_VERIFY_MS, config.BLS_SIGN_MS, config.TRUST_CH_THRESHOLD, config.COMM_RANGE_M
    parts = []
    # ------------------------------------------------------------------ title page
    parts.append(f"""
<section class="title">
  <div class="over">Project documentation</div>
  <div class="main">{TITLE}</div>
  <div class="desc">Trust-aware, cluster-prioritised broadcast suppression for accident alerts</div>
  <div class="sub">{SUBTITLE}</div>
  <div class="meta"><b>Run ID:</b> {f['run']} (seed {f['seed']}) · {f['n']} vehicles · event {f['event']}<br>
    <b>Date:</b> {f['date']}</div>
  <div class="stmt">All thirteen snapshots in this document (each shown with an enlarged crop of its indicator and status
    lines) are genuine captures of the SUMO-GUI window, taken during the final verified demonstration run (captured
    {f['captured']}); each was checked against the recorded run before use.</div>
  <div class="foot">Prepared from docs/SYSTEM_DESIGN.md, docs/AUDIT.md, README.md, the documentation portal's stage text
    and the recorded run results/urban/raw/{f['run']}.json.gz. This is a simulation study: the incident is staged and the
    radio is a simulated IEEE 802.11p model; no real crash detection or live emergency dispatch is involved.</div>
</section>""")
    # ------------------------------------------------------------------ contents
    parts.append(f"""
<section class="section" id="toc"><h1>Contents</h1><ul class="toc">{toc}</ul>
<div class="note" style="margin-top:7mm"><p><b class="sans">Abbreviations.</b> SUMO: Simulation of Urban MObility, the
traffic simulator. RSU: roadside unit. CH: cluster head. BLS: Boneh–Lynn–Shacham signatures (here over the BLS12-381
curve), which can be aggregated into one short signature. DENM: Decentralized Environmental Notification Message, the
ETSI alert format the alert imitates. DBSCAN: density-based spatial clustering. IEEE 802.11p: the vehicular Wi-Fi radio
standard. CSMA/CA: carrier-sense multiple access with collision avoidance (listen before transmitting). ID: identifier.
Frame: one radio transmission. ms: millisecond.</p></div></section>""")
    # ------------------------------------------------------------------ 1 overview
    parts.append(f"""
<section class="section" id="s1"><h1>1&nbsp;&nbsp;System overview</h1>
<p>When a vehicle crashes, the vehicles around it should learn about the accident within tens of milliseconds, and a
roadside unit (RSU) should register the event for the emergency services. Vehicles share one radio channel (IEEE
802.11p). The simplest dissemination, <em>blind flooding</em>, lets every vehicle rebroadcast each new alert once; in
dense traffic these redundant rebroadcasts collide and destroy each other's receptions, which is known as the
<em>broadcast storm</em>. A second risk is a false alert: a misbehaving vehicle could claim an accident that never
happened. The project addresses both. An alert is released only after it has been <em>corroborated</em>: at least
{config.QUORUM} of the {config.COMMITTEE_SIZE} nearest reputable neighbours must sign that they observed the event. The
signatures are aggregated into one compact certificate that every receiver verifies. Forwarding is <em>prioritised and
suppressed</em>: cluster heads (CH) and isolated trusted vehicles relay first, farther vehicles before nearer ones, and a
vehicle rebroadcasts only if one of its neighbours (a vehicle or an RSU) is still uncovered. RSUs verify each copy,
check its plausibility and register each event once. An alternative <em>CH-to-CH route</em> forwards the alert along a
planned chain of trusted cluster heads to the nearest RSU.</p>
<h3>Architecture</h3>
<div class="flow"><div class="b">Incident</div><div class="a">→</div><div class="b">Alert</div><div class="a">→</div>
<div class="b">Clustering and CH election</div><div class="a">→</div><div class="b">Committee votes</div><div class="a">→</div>
<div class="b">Certificate</div><div class="a">→</div><div class="b">Forwarding or CH route</div><div class="a">→</div>
<div class="b">RSU registration</div></div>
<p>A random honest vehicle is designated as crashed at a random second of the simulated traffic and creates one alert.
At that same second the vehicles are grouped into clusters and cluster heads are elected. The source asks a committee of
reputable neighbours to vote; with {config.QUORUM} distinct votes it aggregates the signatures into a certificate and
broadcasts the certified alert. Receivers verify it, accept it, and then forward or suppress. An RSU registers the first
valid copy; later copies are counted as duplicates.</p>
<div class="note"><p><b class="sans">Who computes what.</b> SUMO simulates the road traffic: every vehicle's position,
speed and lane, second by second. At the incident second the project's dissemination engine (Python models of the
radio channel, the forwarding protocols, the corroboration and the RSU) computes every frame, vote, decision and
registration on that exact traffic state and records them. The SUMO-GUI demonstration then replays the recorded events
in slow motion while SUMO's clock is paused. <b>SUMO itself does not run the radio protocol</b>, and nothing is drawn
that the run record does not contain.</p></div>
<div class="note"><p><b class="sans">Authentication is not corroboration.</b> A valid BLS aggregate signature proves
<em>who</em> signed this exact content: authenticity and integrity, including the incident time, position and hop
limit. It says nothing about whether a crash happened. The only accident evidence is corroboration: at least
{config.QUORUM} distinct, currently reputable vehicles (trust ≥ {t}) in radio range each signed that they observed the
event. This rests on two modelling assumptions: honest committee members observe the ground truth (there is no sensor
model), and reputation reflects behaviour. An RSU status of REGISTERED therefore means <em>corroborated and
plausible</em>, not <em>verified true</em>.</p></div>
</section>""")
    # ------------------------------------------------------------------ 2 reading guide
    parts.append(f"""
<section class="section" id="s2"><h1>2&nbsp;&nbsp;Sequential workflow</h1>
<h2 id="s2r" style="margin-top:1mm">How to read the snapshots</h2>
<p>Each figure is a full, unedited capture of the SUMO-GUI window (1518 × 1097 pixels), shown at its original aspect
ratio. Because the on-screen text is small at page size, a strip directly below each snapshot shows the same image's
workflow indicator and status lines enlarged (a crop of that image, nothing added), and the <em>Evidence shown</em> block
quotes the text. The window is organised as follows.</p>
<ul>
<li><b class="sans">Top line:</b> the disclosure {q('Radio is SIMULATED (802.11p model, 300 m range); radio events replayed in slow motion')}.</li>
<li><b class="sans">Workflow indicator:</b> seven boxes, Incident → Alert → Cluster / CH → Votes → Certificate →
Forwarding / Route → RSU (colours in the table below).</li>
<li><b class="sans">Status line 1:</b> the factual status of the current stage, computed only from recorded events that
have already happened at that moment.</li>
<li><b class="sans">Status line 2:</b> during a replay, the scheme being replayed, the radio time since the alert
process started (+ms), the number of frames on air so far, and the SUMO time; before the replay (Figures {FIG['traffic']} to {FIG['clusters']}), the
run ID and the SUMO time; after the replays (Figure {FIG['final']}), the outcome and the running SUMO time. While the alert is
being forwarded, line 1 also counts the RSU outcomes so far: copies registered, duplicates and rejected copies.</li>
<li><b class="sans">Map:</b> the urban street grid with {f['n']} vehicles; RSU-1 and RSU-2 (labelled squares) with their
{rs:.0f} m radio range circles; a red disc marks the incident site.</li>
<li><b class="sans">Right panel and bottom right:</b> one row per RSU with its outcome, the legend, and the services box
(the local dispatch outbox).</li>
</ul>
<table class="keep"><tr><th style="width:36%">Colour on screen</th><th>Meaning</th></tr>{legend}</table>
<div class="note"><p><b class="sans">Time and order.</b> The radio events last tens of milliseconds, so SUMO's clock is
paused at the incident second (t = {f['t_inc']} s) while they are replayed. Each animation frame shows {D.BIN_MS} ms of
radio time, and a ring marks a frame that was on air at some point in that last {D.BIN_MS} ms. On the same accident the
demonstration replays blind flooding, then the proposed scheme ({q(config.LABELS['proposed'])} on screen), then the
CH-to-CH route ({q(config.LABELS['ch_route'])}), and finally a forged alert. This document follows the workflow rather
than the replay order, and every caption names the scheme shown.</p></div>
</section>""")
    # ------------------------------------------------------------------ stages
    parts.append(stage("st1", 1, STAGE_TITLES[0][1], figure(FIG["traffic"], E["traffic"],
                                                            "Normal SUMO traffic before the incident") + blocks(
        f"""<p>The image shows the live traffic at t = {f['t_traffic']} s, {int(f['t_inc']) - int(f['t_traffic'])} s before
the incident: every vehicle is grey (no alert exists), both RSUs are listening and no stage of the indicator is active.
SUMO simulates {f['n']} vehicles on the project's small urban street grid in 1-second steps; the seed {f['seed']}
(= {f['seed_formula']}) fixes the routes and every random choice, so the run is reproducible. Every second the
dissemination engine's watchdog model, fed with SUMO's vehicle positions, updates each vehicle's reputation,
trust = (s + 1)/(s + f + 2), from observed relaying successes s and failures f. {f['n_mis']} of the {f['n']} vehicles
are modelled as misbehaving; at the incident second all {f['n_honest']} honest vehicles have trust ≥ {t} and all
misbehaving vehicles are below it. RSU-1 at ({rsu1['x']:.0f}, {rsu1['y']:.0f}) m and RSU-2 at ({rsu2['x']:.0f},
{rsu2['y']:.0f}) m each have a {rs:.0f} m radio range.</p>""",
        """<p>Every later stage runs on this exact traffic state: positions, speeds and reputations at the incident second
determine the neighbour tables, the clusters, the committee and the forwarding order. Before the replay the demonstration
asserts that SUMO-GUI shows exactly the recorded vehicles (position difference below 0.05 m) and the recorded
clusters.</p>""",
        f"""<p>At a random second between {config.INCIDENT_WINDOW_S[0]} and {config.INCIDENT_WINDOW_S[1]} s (here
t = {f['t_inc']} s) one honest vehicle is designated as crashed, and the indicator activates its first stage.</p>""",
        [f"On screen: {q(E['traffic']['caption'])}; line 2: run {f['run']}, seed {f['seed']}, t = {f['t_traffic']} s; "
         "indicator: every box white.",
         f"Run record <code>scenario</code>: run_id {f['run']}, seed {f['seed']}, {f['n']} vehicles ({f['n_mis']} "
         f"misbehaving, {f['n_trusted']} with trust ≥ {t}), two RSUs with <code>vehicles_in_range</code> "
         f"{rsu1['vehicles_in_range']} and {rsu2['vehicles_in_range']}.",
         f"Snapshot manifest: <code>lead_in_s</code> [{f['lead_in'][0]:.0f}, {f['lead_in'][1]:.0f}], "
         "<code>completed</code> true (the position and cluster assertions passed)."])))

    parts.append(stage("st2", 2, STAGE_TITLES[1][1], figure(FIG["incident"], E["incident"], "Incident") + blocks(
        f"""<p>At t = {f['t_inc']} s vehicle {f['src']}, driving at {f['src_speed']} m/s on lane {f['lane']} at
({f['x']}, {f['y']}) m, is designated as crashed. This is a staged incident: the simulation contains no crash detector.
The vehicle turns red and a red disc marks the incident site; all other vehicles remain grey. SUMO's clock is paused
from here until the replays end, because the radio events last only tens of milliseconds: the GUI is repainted without
simulation steps, so no vehicle moves or is stopped artificially. The indicator highlights Incident (yellow); every
other stage is still white.</p>""",
        f"""<p>The incident vehicle is the alert source. Every later decision (the committee, the distances that order the
relays, the RSU registration) is taken relative to this vehicle and this second. Because the incident is staged on a
recorded state, all schemes can be compared on exactly the same situation. {f['src']} is an honest vehicle (trust
{f['src_trust']}); DBSCAN classifies it as isolated (role {f['src_role']}).</p>""",
        "<p>The incident vehicle immediately creates the alert (Stage 3).</p>",
        [f"On screen: {q(E['incident']['caption'])}.",
         f"Run record <code>scenario</code>: source_id {f['src']}, incident_time_s {f['t_inc']}, incident_xy ({f['x']}, "
         f"{f['y']}), incident_lane {f['lane']}.",
         "Indicator: Incident yellow; all other boxes white."])))

    parts.append(stage("st3", 3, STAGE_TITLES[2][1], figure(FIG["alert"], E["alert"], "Alert creation") + blocks(
        f"""<p>{f['src']} creates one DENM-like alert: event ID {f['event']} (seed, source and sequence number
{f['seq']}), type {f['mtype']}, incident position ({f['x']}, {f['y']}) m, incident and creation time {f['created']} s,
and a hop limit of {f['hop']}. All of these fields later enter the signed digest, so none of them can be altered without
invalidating the certificate. Nothing has been transmitted yet in this image. The indicator now shows Alert in yellow and
Incident in light grey (occurred).</p>""",
        """<p>The event ID identifies the incident from end to end: vehicles use it to recognise copies they already hold,
and the RSU registers each event ID only once. The hop limit bounds how far the alert can travel.</p>""",
        f"""<p>The clusters of this same second are shown first (Stage 4). Then the source proposes the alert to its
committee in a signed PROPOSAL frame (on air {f['prop_start']} to {f['prop_end']} ms in the proposed-scheme replay), which
opens the vote (Stage 5).</p>""",
        [f"On screen: {q(E['alert']['caption'])}.",
         f"Run record <code>scenario.alert</code>: event_id {f['event']}, message_type {f['mtype']}, sequence_number "
         f"{f['seq']}, created_s {f['created']}, hop_limit {f['hop']}.",
         "Indicator: Alert yellow, Incident light grey."])))

    parts.append(stage("st4", 4, STAGE_TITLES[3][1], figure(FIG["clusters"], E["clusters"], "Clustering and cluster-head election") + blocks(
        f"""<p>At the incident second DBSCAN groups the vehicles by position (ε = {config.DBSCAN_EPS_M:.0f} m, MinPts =
{config.DBSCAN_MIN_PTS}): {f['n_clusters']} clusters, and {f['n_isolated']} isolated vehicles (DBSCAN noise, role BRIDGE).
Within each cluster, a greedy set cover over the {rs:.0f} m radio disk elects cluster heads among the trusted members
(trust ≥ {t}). It repeatedly picks the member that covers the most still-uncovered members, breaking ties by the lowest
mean speed difference to its neighbours. Here this gives {f['n_ch']} cluster heads, exactly one per cluster (the design
notes that one {rs:.0f} m radio disk usually covers a whole cluster formed with ε = {config.DBSCAN_EPS_M:.0f} m),
{f['n_member']} members and {f['n_bridge']} bridges. In the image, cluster members are teal and cluster heads carry black
rings.</p>""",
        f"""<p>The roles set the forwarding priority. Tier 0 (a trusted cluster head or bridge) relays first; tier 1 (all
others) waits one extra round of {config.N_SLOTS} slots × {config.TAU_MS:.0f} ms = {config.N_SLOTS * config.TAU_MS:.0f} ms.
The cluster heads are also the only candidate nodes of the CH-to-CH route (Stage 7b).</p>""",
        "<p>The roles stay fixed for this dissemination. The replay of the dissemination begins, and the committee is "
        "asked to vote (Stage 5).</p>",
        [f"On screen: {q(E['clusters']['caption'])}.",
         f"Run record <code>scenario.vehicles[].role</code>: CH {f['n_ch']}, MEMBER {f['n_member']}, BRIDGE {f['n_bridge']}; "
         f"<code>dbscan</code>: {f['n_clusters']} clusters, {f['n_isolated']} labelled −1.",
         "The demonstration asserts that the clusters on screen equal the recorded ones; rules in docs/SYSTEM_DESIGN.md "
         "§2 and §6 (A2, A3)."])))

    sv = s["votes"]
    parts.append(stage("st5", 5, STAGE_TITLES[4][1], figure(FIG["votes"], E["votes"], "Committee vote collection") + blocks(
        f"""<p>The committee is the {config.COMMITTEE_SIZE} nearest in-range neighbours of {f['src']} with trust ≥ {t}:
{f['committee']}. Each member that observes the event (in the simulation, honest members observe the ground truth)
verifies the proposal ({v} ms) and signs ({b} ms), then sends one {config.VOTE_BYTES}-byte vote frame; the members are
rank-ordered {config.VOTE_SLOT_MS} ms apart. The vote frames start at {f['vote_starts']} ms. At +{sv['radio']} ms (the
image) {len(sv['voters'])} members, {' and '.join(sv['voters'])}, have voted and are shown in pink. The source counts each
distinct endorser once.</p>""",
        f"""<p>Corroboration requires at least {config.QUORUM} distinct reputable witnesses, so no single vehicle (and no
misbehaving vehicle) can release an alert alone. The rule is fail-closed: if fewer than {config.QUORUM} reputable honest
neighbours vote, the alert is never released.</p>""",
        f"""<p>The third distinct vote ({f['third']}, received when its frame ends at {f['third_end']} ms) completes the
quorum of {config.QUORUM}. The source then charges {v} ms for verification, aggregates the signatures at {f['quorum']} ms
and puts the certified alert on air at {f['rel_start']} ms (Stage 6). The fourth and fifth votes ({f['late']}) arrive
after the quorum and are not part of the certificate.</p>""",
        [f"On screen: {q(E['votes']['caption'])}; line 2: +{sv['radio']} ms radio time, {sv['transmissions']} frames (the "
         f"proposal and {len(sv['voters'])} votes).",
         f"Run record <code>protocols.proposed.corroboration</code>: committee [{f['committee']}], votes_counted "
         f"[{f['counted']}]; VOTE frames in <code>transmissions</code>.",
         "The committee, the counted votes and the certificate signers are identical in the three genuine replays "
         "(blind flooding, proposed, CH route); only the radio timing differs slightly."])))

    sc_ = s["certificate"]
    parts.append(stage("st6", 6, STAGE_TITLES[5][1], figure(FIG["certificate"], E["certificate"], "Certificate creation and verification") + blocks(
        f"""<p>{f['src']} aggregates its own signature and the {config.QUORUM} counted voters' signatures into one
{config.SIGNATURE_BYTES}-byte BLS12-381 aggregate signature, attaches the {f['n_signers']} signer IDs ({f['signers']}) and
broadcasts the certified alert. In the image (+{sc_['radio']} ms) the source is transmitting (orange ring): its alert frame
is on air from {f['rel_start']} to {f['rel_end']} ms. Every receiver verifies the certificate before accepting it: the
first signer must be the source, the signer IDs must be distinct, the aggregate signature must verify, and at least
{config.QUORUM} endorsers must have trust ≥ {t}. Verification is charged {v} ms before a copy counts as received. Here the
verdict is {q(f['verdict'])}.</p>""",
        """<p>One compact certificate lets every receiver check both authenticity and corroboration without contacting the
voters. The signed digest covers the event ID, type, source, sequence number, position, incident time, creation time and
hop limit, so none of these can be changed in transit. The signatures prove who signed; the quorum of reputable endorsers
is the corroboration (Section 1).</p>""",
        "<p>Each vehicle that accepts the certified copy schedules its forwarding decision (Stage 7).</p>",
        [f"On screen: {q(E['certificate']['caption'])}; line 2: +{sc_['radio']} ms radio time, {sc_['transmissions']} frames "
         "(the proposal, five votes and the certified alert).",
         f"Run record <code>protocols.proposed.corroboration</code>: certificate.signers [{f['signers']}], accepted true, "
         f"reason {q(f['verdict'])}; metrics.quorum_ms {f['quorum']}.",
         "Indicator: Certificate yellow; Votes and the earlier stages light grey."])))

    sf, sr, sd = s["forwarding"], s["route"], s["flooding"]
    parts.append(stage("st7", 7, STAGE_TITLES[6][1],
        '<h3 style="margin-top:0">7a. Proposed scheme: prioritised forwarding with suppression</h3>'
        + figure(FIG["forwarding"], E["forwarding"], "Forwarding in the proposed scheme") + blocks(
        f"""<p>Each vehicle that accepted the alert waits T = t<sub>accept</sub> + (tier × {config.N_SLOTS} + S(d)) ×
{config.TAU_MS:.0f} ms plus a random 0 to {config.RAD_MS:.0f} ms, where the distance slot S(d) lets the farthest receivers
go first. When its timer fires it forwards only if at least one of its neighbours (a vehicle or an RSU) is not within
range of any vehicle it has already heard transmitting the alert; otherwise it suppresses. Misbehaving vehicles receive
but never relay. At +{sf['radio']} ms (the image) {sf['relays']} vehicles have relayed ({f['relays25']}); {sf['reached']}
of {f['n']} hold the alert and {sf['suppressed']} have suppressed, with {sf['collisions']} receptions lost. RSU-2 has
already registered the event (Stage 8).</p>""",
        f"""<p>Suppression keeps the channel usable: only a vehicle that can still reach someone new transmits. Over the whole
replay {f['p_fwd']} vehicles forwarded, {f['p_sup']} suppressed and {f['p_drop']} misbehaving vehicles dropped the alert.
That makes {f['p_frames']} frames in total, and all {f['p_recv']} vehicles end up holding the verified alert. Counting RSUs
as neighbours is what carries the alert to the infrastructure without a routing protocol.</p>""",
        "<p>Copies reach the RSUs: the first decodable copy is verified and registered, and later ones become duplicates "
        "(Stages 8 and 9). The same accident is also delivered along the CH-to-CH route (7b).</p>",
        [f"On screen: {q(E['forwarding']['caption'])}; line 2: +{sf['radio']} ms radio time, {sf['transmissions']} frames; RSU "
         f"rows: RSU-1 listening, RSU-2 registered +{f['p_reg']} ms.",
         f"Run record <code>protocols.proposed</code>: decisions FORWARD {f['p_fwd']}, SUPPRESS {f['p_sup']}, DROP "
         f"{f['p_drop']}; metrics: transmissions {f['p_frames']}, received {f['p_recv']}, suppression_ratio {f['p_sr']}."])
        + '<h3 class="stage" style="margin-top:0">7b. CH-to-CH route formation</h3>'
        + figure(FIG["route"], E["route"], "Route formation on the CH-to-CH route") + blocks(
        f"""<p>The alternative scheme forwards only along a planned route: Dijkstra over cluster heads with trust ≥ {t},
from the source to the nearest RSU, here <span class="nb">{f['route']}</span> ({f['route_m']} m, {f['route_hops']} hops).
Vehicles off the route stay silent. {f['head']} (cluster head, trust {f['head_trust']}) accepted the certified alert at
{f['head_rx']} ms and then ran a local quorum. Its local proposal (CPROPOSAL) at {f['cprop']} ms is where the indicator
switches to Forwarding / Route, and members of its cluster ({f['cvote_from']}) answered with local votes (CVOTE) between
{f['cvote_first']} and {f['cvote_last']} ms. Holding its own endorsement plus {config.QUORUM - 1} local votes, and after
verification, {f['head']} relayed the alert ({f['hrelay_start']} to {f['hrelay_end']} ms). RSU-2 decoded it at
{f['c_arr']} ms and registered it at {f['c_reg']} ms. Purple lines mark the hops already traversed.</p>""",
        f"""<p>These local votes form {f['head']}'s own quorum; they are separate from the source's committee vote
(Stage 5) and are not counted in it. The route needs only {f['c_frames']} frames and loses {f['c_lost']} receptions, but
only vehicles within range of {f['src']} or {f['head']} receive the alert ({f['c_recv']} of {f['n']}). Registration also
takes longer (+{f['c_reg']} ms against +{f['p_reg']} ms in 7a), because the head waits for its local quorum. There is no
fallback if a head fails or loses its quorum.</p>""",
        "<p>This registration is the outcome shown on the final screen and written to the local dispatch outbox "
        "(Stage 11).</p>",
        [f"On screen: {q(E['route']['caption'])}; line 2: +{sr['radio']} ms radio time, {sr['transmissions']} frames; RSU-2 "
         f"registered +{f['c_reg']} ms.",
         f"Run record: <code>infrastructure.route</code> ROUTE_FOUND; transmissions {f['head_kind']}, {f['n_cvotes']} × "
         f"CVOTE, {f['head']} ALERT; rsu_event arrival {f['c_arr3']} ms, registration {f['c_reg3']} ms, duplicate_copies "
         f"{f['c_dups']}; {f['c_sup']} vehicles SUPPRESS (outside the selected cluster-head route)."])
        + '<h3 class="stage" style="margin-top:0">7c. Baseline for comparison: blind flooding</h3>'
        + figure(FIG["flooding"], E["flooding"], "Forwarding in the blind-flooding baseline") + blocks(
        f"""<p>The demonstration replays the same accident first with blind flooding, the baseline without suppression.
Every honest vehicle rebroadcasts once after verifying, whether or not its neighbours already hold the alert
(misbehaving vehicles never relay). At +{sd['radio']} ms {sd['relays']} vehicles have relayed, {sd['reached']} of
{f['n']} hold the alert, {sd['suppressed']} have suppressed and {sd['collisions']:,} receptions have been lost to
collisions. RSU-1 registered the event at +{f['f_reg']} ms (copy from {f['f_from']}, arrival +{f['f_arr']} ms); RSU-2's
first copy, from {f['f_r2_from']}, was recorded as a DUPLICATE at +{f['f_r2_reg']} ms (light green).</p>""",
        f"""<p>This is the broadcast storm the proposed scheme avoids. Over the whole replay blind flooding put
{f['f_frames']} frames on air and lost {f['f_lost']} receptions, and {f['f_recv']} of {f['n']} vehicles received the alert;
the proposed scheme (7a) used {f['p_frames']} frames, lost {f['p_lost']} receptions and reached all {f['p_recv']}.</p>""",
        "<p>Whatever the scheme, a decoded copy reaches an RSU, which verifies and registers it (Stage 8).</p>",
        [f"On screen: {q(E['flooding']['caption'])}; line 2: +{sd['radio']} ms radio time, {sd['transmissions']} frames; RSU "
         f"rows: RSU-1 registered +{f['f_reg']} ms, RSU-2 duplicate +{f['f_r2_reg']} ms.",
         f"Run record <code>protocols.flooding</code>: decisions FORWARD {f['f_fwd']}, DROP {f['f_drop']}; metrics: "
         f"transmissions {f['f_frames']}, collision_losses {f['f_lost']}, received {f['f_recv']}, suppression_ratio "
         f"{f['f_sr']}."])))

    parts.append(stage("st8", 8, STAGE_TITLES[7][1], figure(FIG["rsu"], E["rsu"], "RSU receipt and registration") + blocks(
        f"""<p>In the proposed scheme RSU-2 decoded its first copy, relayed by {f['p_from']}, at +{f['p_arr']} ms (its
arrival time). It verified the certificate ({v} ms) and ran the plausibility checks on its own clock: required fields,
message type, a position inside the road network's bounding box, not received before its creation, an age of at most
{rsu.MAX_AGE_S:.0f} s, a hop count within the hop limit, and the certificate (signatures and quorum). It then registered
event {f['event']} at +{f['p_reg']} ms, with the status REGISTERED; registration time = arrival + verification. This
snapshot was taken after the replay had finished, at +{E['rsu']['radio_ms']:.1f} ms, the time of the last recorded event
(a suppression decision by {f['last_v']}). The indicator therefore shows RSU and line 1 summarises the outcome.</p>""",
        """<p>The RSU is the hand-over point to the emergency services. Registering each event ID once prevents duplicate
dispatches, and reporting arrival and registration separately shows the cost of verification. Every copy's outcome is
recorded as REGISTERED, DUPLICATE or REJECTED (with the reason).</p>""",
        "<p>Further copies of the same event keep reaching the RSUs and are counted as duplicates (Stage 9).</p>",
        [f"On screen: {q(E['rsu']['caption'])}; line 2: done: {f['p_frames']} frames, {f['p_recv']}/{f['n']} have the alert, "
         f"{f['p_lost']} receptions lost; RSU rows: RSU-1 duplicate +{f['p_r1_reg']} ms, RSU-2 registered +{f['p_reg']} ms.",
         f"Run record <code>protocols.proposed.rsu_event</code>: receiving_rsu {f['p_rsu']}, received_from {f['p_from']}, "
         f"hops {f['p_hops']}, arrival_ms {f['p_arr3']}, delay_ms (registration) {f['p_reg3']}, status REGISTERED, "
         f"validation PASSED, duplicate_copies {f['p_dups']}."])))

    su = s["duplicates"]
    cp = su["rsu_copies"]
    parts.append(stage("st9", 9, STAGE_TITLES[8][1],
        figure(FIG["duplicates"], E["duplicates"], "Duplicate copies in the proposed scheme") + blocks(
        f"""<p>In the proposed scheme RSU-2 registered the event at +{f['p_reg']} ms (Stage 8). RSU-1 decoded its first
copy, relayed by {f['p_r1_from']}, at +{f['p_r1_arr']} ms; after the same {v} ms check it was recorded as a DUPLICATE at
+{f['p_r1_reg']} ms, because event {f['event']} was already registered. The image (+{su['radio']} ms) shows that outcome:
RSU-1 in light green beside RSU-2 in dark green. Line 1 counts the RSU outcomes so far:
{sum(st == 'REGISTERED' for _, st in cp)} registered and {sum(st == 'DUPLICATE' for _, st in cp)} duplicate copies
({cp.count(('RSU-2', 'DUPLICATE'))} at RSU-2, {cp.count(('RSU-1', 'DUPLICATE'))} at RSU-1). Vehicles treat repeated
copies the same way: a copy of an alert already held is never processed again; it is counted and its sender is added to
the vehicle's coverage set. By this moment {su['suppressed']} vehicles have suppressed their rebroadcast because every
neighbour was already covered.</p>""",
        f"""<p>Duplicates must never become a second accident or a second dispatch. Each RSU registers an event ID once and
records every later copy as DUPLICATE, and every copy's outcome is kept in the record. Over the whole replay the RSUs
recorded {f['p_dups']} duplicate copies ({f['p_dup2']} at RSU-2, {f['p_dup1']} at RSU-1), and vehicles decoded
{f['p_duprx']} duplicate copies, none re-processed. On the vehicle side duplicates are what the coverage test feeds on;
blind flooding, which ignores them, produced the storm of 7c.</p>""",
        "<p>After the three genuine schemes, the demonstration replays a forged alert on the same traffic (Stage 10).</p>",
        [f"On screen: {q(E['duplicates']['caption'])}; RSU rows: RSU-1 duplicate +{f['p_r1_reg']} ms, RSU-2 registered "
         f"+{f['p_reg']} ms.",
         f"Run record <code>protocols.proposed.rsu_receptions[].status</code>: RSU-2 REGISTERED 1 and DUPLICATE "
         f"{f['p_dup2']}, RSU-1 DUPLICATE {f['p_dup1']}; rsu_event.duplicate_copies {f['p_dups']}; metrics.dup_rx "
         f"{f['p_duprx']}."])))

    parts.append(stage("st10", 10, STAGE_TITLES[9][1], figure(FIG["forged"], E["forged"], "Forged-alert rejection") + blocks(
        f"""<p>A misbehaving vehicle, {f['forger']} (trust {f['forger_trust']}), claims an accident that did not happen at
({f['fx']}, {f['fy']}) m (event <span class="nb">{f['fevent']}</span>). Its committee, the {f['n_fcommittee']} nearest
reputable neighbours ({f['fcommittee']}; trust {f['fcommittee_trust']}), observes no accident and stays silent; instead
{f['n_fvoters']} colluding misbehaving vehicles ({f['fvoters']}; trust {f['fvoters_trust']}) vote. The forger counts
{f['n_fcounted']} distinct votes and broadcasts a certificate with {f['n_fsigners']} valid BLS signatures ({f['fsigners']})
at {f['frel_start']} to {f['frel_end']} ms. Every receiver finds the signatures valid but rejects the alert:
{q(f['freason'])} ({f['freject']} rejections, {f['fhonest']} honest acceptances). RSU-2 decoded a copy at
+{f['frsu_arr']} ms and rejected it at +{f['frsu_reg']} ms. Nobody accepted, so nobody forwarded: the Forwarding / Route
box stays white.</p>""",
        f"""<p>A valid signature is not evidence of an accident; the reputation gate on the endorsers stops the forgery. In
the same run, without that gate (record variant <code>voting_only</code>), the same certificate was accepted by
{f['vo_honest']} honest vehicles and {f['vo_rsu']} reported {f['vo_status']}; without voting (<code>no_voting</code>) the
outcome was the same ({f['nv_honest']} honest vehicles, {f['nv_status']}). The protection therefore depends on the
colluders' low reputation (Section 3).</p>""",
        "<p>The replays are over, and SUMO's clock resumes (Stage 11).</p>",
        [f"On screen: {q(E['forged']['caption'])}; line 2: FORGED alert test (full protection), done: {f['fframes']} frames, "
         f"{f['fhonest']} honest vehicles accepted it, {f['flost']} receptions lost; RSU-2 row red, rejected.",
         f"Run record <code>forgery.variants.voting_reputation</code>: accepted false; {f['freject']} decisions REJECT; "
         f"RSU-2 status {q(f['frsu_status'])}. Indicator: Votes and Certificate light grey, Forwarding / Route white, RSU "
         "yellow."])))

    parts.append(stage("st11", 11, STAGE_TITLES[10][1], figure(FIG["final"], E["final"], "Final traffic state and end-to-end outcome") + blocks(
        f"""<p>After the replays SUMO's clock resumes; the image is taken {f['steps_final']} simulation steps later, at
t = {f['t_final']} s. The crashed vehicle {f['src']} stops (deliberately abruptly). Every other vehicle continues at its own
speed and reacts to the obstacle through SUMO's car-following model. The overlay now shows one recorded dissemination: the
CH-to-CH route delivery of Stage 7b, which is the one the run writes to the infrastructure layer. {f['c_recv']} of
{f['n']} vehicles hold the verified alert (blue). RSU-2 registered it at +{f['c_reg']} ms, and the dispatch is queued in a
local SQLite outbox with no cloud connection. RSU-1 received no copy on this route and still shows listening.</p>""",
        """<p>This closes the loop from a staged incident to a registered, dispatch-ready event. It also shows that the
replay did not disturb the traffic simulation: the clock was paused, and apart from the crashed vehicle no vehicle was
stopped artificially.</p>""",
        "<p>The workflow ends here. The event waits in the local outbox; no real emergency service is contacted (README: "
        "no live emergency dispatch is enabled by default).</p>",
        [f"On screen: {q(E['final']['caption'])}; line 2: {esc(f['final']['reach'])}, t = {f['t_final']} s; RSU-2 "
         f"registered +{f['c_reg']} ms; services: dispatch queued (local); indicator: RSU yellow, all others light grey.",
         f"Run record <code>infrastructure.backhaul</code>: {f['backhaul']['storage']}, {f['backhaul']['dispatch']}, cloud "
         f"{f['backhaul']['cloud']}; tracked outbox {f['db']}: {f['event']} QUEUED_LOCAL.",
         f"Snapshot manifest <code>sumo_log</code>: {esc(f['log_sentence'])}"])))
    # ------------------------------------------------------------------ 3 results and limitations
    parts.append(f"""
<section class="section" id="s3"><h1>3&nbsp;&nbsp;Results and limitations</h1>
<p><b>Simulation results from one run</b> ({f['run']}, seed {f['seed']}, {f['n']} vehicles): the same accident on the
same traffic state under each scheme. These are outputs of the simulated radio model for this seed, not real-world radio
measurements. Multi-seed statistics (30 seeds per density, 95 % confidence intervals and paired differences) are produced
by <code>python run.py experiment</code> in results/urban/summaries/RESULTS.md and are not restated here.</p>
<table class="keep">
<tr><th>Measure (from the run record)</th><th class="r">Blind flooding</th><th class="r">Proposed</th><th class="r">CH-to-CH route</th></tr>
<tr><td>Frames on air (proposal, votes and alert frames)</td><td class="r">{f['f_frames']}</td><td class="r">{f['p_frames']}</td><td class="r">{f['c_frames']}</td></tr>
<tr><td>Receptions lost to collisions</td><td class="r">{f['f_lost']}</td><td class="r">{f['p_lost']}</td><td class="r">{f['c_lost']}</td></tr>
<tr><td>Vehicles holding the verified alert</td><td class="r">{f['f_recv']} / {f['n']}</td><td class="r">{f['p_recv']} / {f['n']}</td><td class="r">{f['c_recv']} / {f['n']}</td></tr>
<tr><td>Time until 90 % of vehicles hold it</td><td class="r">{f['f_t90']}</td><td class="r">{f['p_t90']}</td><td class="r">{f['c_t90']}</td></tr>
<tr><td>Suppression ratio (honest relay decisions that suppressed)</td><td class="r">{f['f_sr']}</td><td class="r">{f['p_sr']}</td><td class="r">{f['c_sr']}</td></tr>
<tr><td>First RSU registration (arrival + {v} ms)</td><td class="r">{f['f_rsu']} +{f['f_reg']} ms</td><td class="r">{f['p_rsu']} +{f['p_reg']} ms</td><td class="r">RSU-2 +{f['c_reg']} ms</td></tr>
<tr><td>Duplicate copies decoded at RSUs</td><td class="r">{f['f_dups']}</td><td class="r">{f['p_dups']}</td><td class="r">{f['c_dups']}</td></tr>
</table>
<p>On this accident the proposed scheme used {f['p_frames']} frames instead of {f['f_frames']} and lost {f['p_lost']}
receptions instead of {f['f_lost']}, while all {f['n']} vehicles received the alert (blind flooding: {f['f_recv']}). Blind
flooding reached 90 % of the vehicles sooner ({f['f_t90']} against {f['p_t90']}), because every honest vehicle
rebroadcasts as soon as it has verified the alert, whereas the proposed scheme's slotted timers trade some milliseconds
for a much lighter channel load. The CH-to-CH route used the fewest frames but reached only {f['c_recv']} vehicles and registered latest. In
the forged-alert test on the same traffic, full protection let {f['fhonest']} honest vehicles accept the forgery and
RSU-2 rejected it; without the reputation gate {f['vo_honest']} honest vehicles accepted it and RSU-2 registered it.</p>
<h3>Limitations (from docs/SYSTEM_DESIGN.md §5 and docs/AUDIT.md §3)</h3>
<ul>
<li><b>Simulated radio.</b> IEEE 802.11p on a {rs:.0f} m unit disk, simulated slot by slot with carrier sensing,
collisions, hidden terminals and half-duplex losses. Fading, capture, background beacon load and real hardware are not
modelled. The coverage test assumes idealised two-hop neighbour knowledge from beacons.</li>
<li><b>Small map.</b> A small straight 5 × 5 street grid (3 to 5 hops); clustering yields about one cluster head per
cluster, and ε = {config.DBSCAN_EPS_M:.0f} m is provisional for this urban grid.</li>
<li><b>Honest-witness assumption.</b> Honest committee members are assumed to observe the ground truth; there is no
sensor model.</li>
<li><b>Near-oracle reputation by default.</b> Misbehaving vehicles are persistent black holes whose trust stays at or
below 0.5 by construction. On-off attackers with honest-looking reputation can pass the {t} gate, and forged alerts are
then accepted (auditor measurement: registered in 8 of 10 runs).</li>
<li><b>Keys derived from vehicle IDs.</b> There is no public-key infrastructure and no proof of possession. BLS processing
time is a fixed charge ({b} ms to sign, {v} ms to verify).</li>
<li><b>Fail-closed corroboration.</b> A genuine alert is never released when fewer than {config.QUORUM} reputable honest
voters are in range (auditor measurement: 14 of 30 runs at 50 vehicles with a 150 m range). A quorum-timeout fallback is
specified but not implemented.</li>
<li><b>CH-to-CH route.</b> There is no fallback: no route, or a lost local quorum, means no delivery on that path.</li>
<li><b>Staged incident and frozen snapshot.</b> There is no crash detection. The dissemination is computed on the
incident-second snapshot; in the slowest run (64 ms) a vehicle moves at most 1.25 m.</li>
<li><b>RSU and dispatch.</b> The location check is a bounding box. Dispatch is a local outbox only, with no cloud
connection and no real emergency service.</li>
<li><b>Reports of one crash.</b> The RSU code now has <code>rsu.register_reports</code>, which can merge valid reports of
the same crash (separate alerts about it) into one incident, but the simulation emits one report per crash and does not
call it: the function is exercised by unit tests only (validation/test_rsu.py), is not shown in the SUMO replay and is
not reflected in the run results above or in the experiment metrics. It matches the event ID first (an event ID already
registered is the same report, and its copies count as duplicates unless they fail the existing checks); otherwise a
report joins an incident only if it has the same message type
and its incident position and time are within {rsu.MERGE_RADIUS_M:.0f}&nbsp;m and {rsu.MERGE_WINDOW_S:.0f}&nbsp;s of every
report already in that incident. Each report is still validated on its own by the existing checks, and a rejected report
is never merged; certificates, endorsements and quorum decisions are never combined. The incident keeps its valid source
reports and the distinct reporting vehicle IDs, and it is registered once: neither duplicates nor merged reports add a
registration. Limits: distinct crashes within these bounds are merged into one incident, reports of one crash outside
them stay separate, and a report that matches several incidents joins the first registered one.</li>
<li><b>Untuned parameters.</b> Committee size {config.COMMITTEE_SIZE}, quorum {config.QUORUM}, random delay
{config.RAD_MS:.0f} ms and trust threshold {t} are provisional design choices; the DBSCAN parameters come from a highway
study and are provisional for this urban grid.</li>
<li><b>Demonstration.</b> The GUI replays a recorded run on the identical SUMO state; it is not computed inside the GUI
process. Each animation frame shows {D.BIN_MS} ms of radio time.</li>
</ul>
</section>""")
    # ------------------------------------------------------------------ 4 summary
    parts.append(f"""
<section class="section" id="s4"><h1>4&nbsp;&nbsp;End-to-end summary</h1>
<p>SUMO supplies the traffic: {f['n']} vehicles on an urban grid. From their positions the dissemination engine's
watchdog model builds each vehicle's reputation second by second. At t = {f['t_inc']} s vehicle {f['src']} is designated
as crashed and creates alert {f['event']}. On that exact state the engine clusters the vehicles and elects {f['n_ch']}
cluster heads. It collects votes from the source's committee until {config.QUORUM} distinct reputable members have
endorsed the alert, and aggregates their BLS signatures with the source's into one {config.SIGNATURE_BYTES}-byte aggregate
signature, which the certificate carries together with the signer IDs. It then disseminates the certified alert, in the
proposed scheme with prioritised, coverage-based suppression ({f['p_frames']} frames, all {f['n']} vehicles reached) and
along the CH-to-CH route through {f['head']} to RSU-2. The RSUs verify each copy, register the event once and count later
copies as duplicates. A forged alert with valid signatures but no reputable endorsers is rejected by every receiver and
by the RSU. When the clock resumes, the registered CH-route delivery sits in the local dispatch outbox, and the traffic
continues around the stopped vehicle.</p>
<div class="note"><p><b class="sans">Indicator colours.</b> {swatch(D.STAGE_NOW)}yellow = the current stage;
{swatch(D.STAGE_DONE)}light grey = a stage that has occurred; {swatch(D.STAGE_FUTURE)}white = a stage that has not
occurred (yet), including a stage that was skipped.</p></div>
<h3>What this document claims, and what it does not</h3>
<p><b>It claims</b>, for this simulated run: that the alert was released only after {config.QUORUM} distinct reputable
endorsements; that every receiver and RSU checked who signed it and that it was not altered; that coverage-based
suppression delivered it to all {f['n']} vehicles and to an RSU with {f['p_frames']} frames and {f['p_lost']} lost
receptions, against {f['f_frames']} frames and {f['f_lost']} lost receptions for blind flooding on the same accident;
and that an alert endorsed only by low-reputation vehicles was rejected.</p>
<p><b>It does not claim</b> that a registered event is a true accident (only corroborated and plausible); that the
results hold on real radios (the channel is a model without fading or capture); that one run represents all traffic
conditions (see the multi-seed results); that the reputation would detect attackers who behave well while watched; that
genuine alerts are always delivered (the scheme is fail-closed when fewer than {config.QUORUM} reputable voters are in
range); or that any emergency service is contacted (the dispatch is a local outbox only).</p>
</section>""")
    # ------------------------------------------------------------------ sources
    figlist = "".join(
        f"<tr><td class='fig'>Figure {no}</td><td>{esc(E[k]['file'])}</td><td class='fig'>{esc(E[k]['stage'])}</td>"
        f"<td>{esc(E[k]['scheme'] or '–')}</td><td class='r'>{E[k]['sim_time_s']:.0f} s</td>"
        f"<td class='r'>{'–' if E[k]['radio_ms'] is None else '+' + format(E[k]['radio_ms'], '.1f') + ' ms'}</td></tr>"
        for no, k in FIGURE_ORDER)
    parts.append(f"""
<section class="section" id="s5"><h1>Source and evidence note</h1>
<p><b>Final verified demonstration.</b> Run {f['run']} (seed {f['seed']}, event {f['event']}), recorded with
<code>python run.py demo --shots portal/assets/sumo</code> on SUMO-GUI 1.27.1. The thirteen snapshots were captured on
{f['captured']}; each is a pixel copy of the SUMO-GUI window only (Windows PrintWindow). They are listed in the manifest
portal/assets/sumo/snapshots.json, with identical copies in documentation_website/portal/assets/sumo/. The demo writes its
own run evidence into that manifest, so it is kept with the snapshots: <code>completed</code> = true (every stage ran and
every replay consistency check passed), the SUMO log (<code>sumo_log</code>, {len(f['sumo_log'])}
line{'' if len(f['sumo_log']) == 1 else 's'}), the live-traffic window (<code>lead_in_s</code>) and a SHA-256 fingerprint of
the record it replayed (<code>record_fingerprint</code>, {f['fingerprint']}…).</p>
<p><b>Checks made by the script that builds this document</b> (docs/workflow_pdf/build_workflow_pdf.py), before any text
is written: the run must be marked completed; the manifest's fingerprint must equal the fingerprint of the record file
results/urban/raw/{f['run']}.json.gz (for the final demonstration the demo re-simulated the seed into a separate scratch
results folder and obtained a record with exactly this fingerprint); for every snapshot, the indicator stage and status
line 1 must equal what that record gives at the snapshot's radio time, the run ID must match, and the SUMO time must be the
incident second (Figures {FIG['incident']} to {FIG['forged']}), lie in the recorded lead-in (Figure {FIG['traffic']}) or
follow the incident (Figure {FIG['final']}); and the outbox {f['db']} must hold the dispatch row. Run-specific numbers
(counts, times, identifiers) are read from the record and design parameters from config.py; the SUMO version, the
0.05 m assertion tolerance and the audit figures in Section 3 come from the cited sources.</p>
<p><b>Version-control status.</b> The record file and the outbox above were last written on 3 November 2026, and the
snapshots and this document were produced on {f['date']}. All of them are in the project's working tree but not yet
committed to git; the committed copy of the record dates from 27 October 2026 and differs from it. They become permanent in
version control once the project owner commits them.</p>
<table class="keep"><tr><th>Figure</th><th>Snapshot file</th><th>Indicator stage</th><th>Scheme replayed</th><th class="r">SUMO time</th><th class="r">Radio time</th></tr>{figlist}</table>
<p><b>Documents used.</b> docs/SYSTEM_DESIGN.md (rules, parameters, limitations), docs/AUDIT.md (confirmed limitations
and the demonstration fixes V1 to V9), README.md (demo behaviour and scope), and the documentation portal's SUMO
Demonstration text (portal/app.js). The Panel Review deck was not used: it describes an architecture that no longer
exists (docs/AUDIT.md §4).</p>
</section>""")
    body = "".join(parts)
    for token in (f["event"], f["fevent"], "RSU-1", "RSU-2"):         # identifiers never break at their hyphens
        body = body.replace(token, f'<span class="nb">{token}</span>')
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}: {SUBTITLE}</title>'
            f'<style>{css()}</style></head><body>{body}</body></html>')


# ---------------------------------------------------------------------------------------------- printing
def browser():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or ""):
        if p and Path(p).exists():
            return p
    raise SystemExit("Microsoft Edge or Google Chrome is needed to print the PDF")


def print_pdf(html_path, pdf_path):
    with tempfile.TemporaryDirectory() as profile:                      # never touches the user's browser profile
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                        f"--user-data-dir={profile}", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=15000",
                        f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                       check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert Path(pdf_path).stat().st_size > 100_000, "the PDF was not written"


HEADINGS = {"s1": "1 System overview", "s2": "2 Sequential workflow", "s2r": "How to read the snapshots",
            "s3": "3 Results and limitations", "s4": "4 End-to-end summary", "s5": "Source and evidence note",
            **{f"st{i}": f"Stage {i} – {t}" for i, t in STAGE_TITLES}}


def heading_pages(pdf_path):
    """Page (1-based) on which each heading first appears, after the contents page."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    norm = lambda s: " ".join(s.replace("\u00a0", " ").replace("\r", " ").split())
    texts = [norm(doc[i].get_textpage().get_text_range()) for i in range(len(doc))]
    found = {}
    for key, h in HEADINGS.items():
        pages = [i + 1 for i in range(2, len(texts)) if norm(h) in texts[i]]
        assert pages, f"heading not found in the PDF: {h}"
        found[key] = pages[0]
    return found, len(texts)


def main():
    manifest = json.loads((SNAP_DIR / "snapshots.json").read_text(encoding="utf-8"))
    raw = experiment.load_raw(manifest["run_id"])
    entries = check_snapshots(manifest, raw)
    f = facts(raw, entries, manifest)
    HTML_OUT.write_text(build_html(f, entries, {}), encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        draft = Path(tmp) / "draft.pdf"
        print_pdf(HTML_OUT, draft)
        pages, n = heading_pages(draft)
    HTML_OUT.write_text(build_html(f, entries, pages), encoding="utf-8")
    print_pdf(HTML_OUT, PDF_OUT)
    final_pages, n_final = heading_pages(PDF_OUT)
    assert final_pages == pages and n_final == n, "the contents changed the page layout"
    order = [f"st{i}" for i, _ in STAGE_TITLES] + ["s3"]
    spills = [a for a, b in zip(order, order[1:]) if pages[b] - pages[a] != (3 if a == "st7" else 1)]
    print(f"{PDF_OUT.relative_to(ROOT)}: {n} pages; sections start on pages {pages}")
    if spills:
        print("warning: these stages run onto an extra page:", ", ".join(spills))


if __name__ == "__main__":
    main()
