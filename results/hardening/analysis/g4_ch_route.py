"""G4.2: why CH-route local rounds fall short of the quorum (read-only, from the G2 raw records; no simulation).

    python -X utf8 results/hardening/analysis/g4_ch_route.py      (run from the project root)

Rebuilds every CH-route local round exactly as protocols.CHRoute.first_copy does: voters = vehicles i != head,
i != source, adjacent to the head, in the head's DBSCAN cluster, with trust >= gate, first COMMITTEE_SIZE by index.
The head counts itself; attackers stay silent. Endorsements = 1 + CVOTE frames sent for that head (an upper bound on
what the head decoded). A round succeeds when the head's decision is FORWARD."""
import collections, glob, gzip, json, os, sys
import numpy as np
sys.path.insert(0, os.getcwd())
from channel import geometry

H, GATE = os.path.join("results", "hardening"), 0.70
out = collections.defaultdict(collections.Counter)
for folder in sorted(glob.glob(os.path.join(H, "G2", "*"))):
    params = json.load(open(os.path.join(folder, "summaries", "experiment_config.json")))["parameters"]
    m, q = params["COMMITTEE_SIZE"], params["QUORUM"]
    for path in glob.glob(os.path.join(folder, "raw", "d*_r*.json.gz")):
        if "__" in path:
            continue
        raw = json.load(gzip.open(path))
        vs = raw["scenario"]["vehicles"]
        ids = [v["id"] for v in vs]
        xy = np.array([(v["x"], v["y"]) for v in vs])
        adj = geometry(xy)[1]
        src = ids.index(raw["scenario"]["source_id"])
        ch = raw["protocols"]["ch_route"]
        dec = {v["id"]: v["decision"] for v in ch["vehicles"]}
        votes = collections.Counter(t["kind"].split(":")[1] for t in ch["transmissions"] if t["kind"].startswith("CVOTE:"))
        for t in ch["transmissions"]:
            if not t["kind"].startswith("CPROPOSAL:"):
                continue
            h = int(t["kind"].split(":")[1])
            elig = [i for i in range(len(vs)) if i != h and i != src and adj[h, i]
                    and vs[i]["dbscan"] == vs[h]["dbscan"] and vs[i]["trust"] >= GATE]
            cap = elig[:m]
            honest = [i for i in cap if not vs[i]["malicious"]]
            got = 1 + votes[str(h)]
            ok = dec.get(ids[h]) == "FORWARD"
            c = out[f"{m}/{q}"]
            c["rounds"] += 1
            c["succeeded"] += ok
            if not ok:
                cause = ("cluster too small: < q-1 eligible members" if len(cap) < q - 1 else
                         "silent attackers: >= q-1 eligible, < q-1 honest" if len(honest) < q - 1 else
                         "radio: >= q-1 honest voters, < q endorsements decoded")
                c[cause] += 1
            c[f"eligible members (capped) = {min(len(cap), 9)}"] += 1
            c["honest eligible >= q-1"] += len(honest) >= q - 1
            c["honest eligible >= 2 (q = 3 reachable)"] += len(honest) >= 2
            c["endorsements sent"] += got
for k in ("5/3", "7/3", "7/4", "9/5"):
    c = out[k]
    n = c["rounds"]
    print(f"\n{k}: {n} CH-route local rounds, {c['succeeded']} succeeded ({100 * c['succeeded'] / n:.1f} %); "
          f"mean endorsements sent {c['endorsements sent'] / n:.2f}")
    print(f"  heads with >= q-1 honest eligible members: {c['honest eligible >= q-1']} ({100 * c['honest eligible >= q-1'] / n:.1f} %); "
          f"with >= 2 (enough for q = 3): {c['honest eligible >= 2 (q = 3 reachable)']} "
          f"({100 * c['honest eligible >= 2 (q = 3 reachable)'] / n:.1f} %)")
    for cause in ("cluster too small: < q-1 eligible members", "silent attackers: >= q-1 eligible, < q-1 honest",
                  "radio: >= q-1 honest voters, < q endorsements decoded"):
        print(f"  failed rounds, {cause}: {c[cause]}")
    print("  eligible members per head (capped at m): " +
          ", ".join(f"{e}: {c[f'eligible members (capped) = {e}']}" for e in range(10) if c[f"eligible members (capped) = {e}"]))
