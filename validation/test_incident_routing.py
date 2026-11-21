"""Block E: route-preserving detours (incident_response.detour) and the four-session comparison (incident_routing.py)."""
import heapq
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest
import traci
from scipy import stats

import config
import incident_response as ir
import incident_routing

E, BIG = "n2n3", config.BLOCKED_EDGE_TT_S


class Ladder:
    """A 2 x 4 grid, every street both ways, no U-turns:  n1 - n2 - n3 - n4
                                                          |    |    |    |
                                                          m1 - m2 - m3 - m4      edge "n2n3" runs from n2 to n3."""
    links = [("n1", "n2"), ("n2", "n3"), ("n3", "n4"), ("m1", "m2"), ("m2", "m3"), ("m3", "m4"),
             ("n1", "m1"), ("n2", "m2"), ("n3", "m3"), ("n4", "m4")]

    def __init__(self):
        self.edges = {a + b: (a, b) for x, y in self.links for a, b in ((x, y), (y, x))}

    def succ(self, e):
        a, b = self.edges[e]
        return sorted(f for f, (c, d) in self.edges.items() if c == b and d != a)

    def path(self, a, b, cost):
        best, prev, q = {a: 0.0}, {}, [(0.0, a)]
        while q:
            c, e = heapq.heappop(q)
            if e == b:
                out = [b]
                while out[-1] != a:
                    out.append(prev[out[-1]])
                return out[::-1]
            for f in self.succ(e):
                if c + cost(f) < best.get(f, math.inf):
                    best[f], prev[f] = c + cost(f), e
                    heapq.heappush(q, (best[f], f))
        return []


class FakeTC:
    """TraCI stand-in for one vehicle "v" that routes like SUMO: findRoute reads the global weights, the vehicle's own
    router (changeTarget) its adapted travel times first; a committed vehicle keeps its next edge; setRoute must start
    on the current edge and be connected (refuse=True: SUMO refuses any route except the original one)."""

    def __init__(self, route, road=None, committed=False, refuse=False):
        self.net, self.route, self.original = Ladder(), list(route), list(route)
        self.road, self.committed, self.refuse = road or route[0], committed, refuse
        self.adapted, self.weights, self.calls = {}, {}, []
        t = self
        self.vehicle = SimpleNamespace(
            getRoute=lambda v: tuple(t.route), getRouteIndex=lambda v: 0, getRoadID=lambda v: t.road,
            getTypeID=lambda v: "car", setAdaptedTraveltime=t._adapt, changeTarget=t._change, setRoute=t._set,
            isRouteValid=lambda v: t._valid(t.route), getIDList=lambda: ["v"], getLanePosition=lambda v: 10.0,
            getLaneID=lambda v: t.road + "_0", getSpeed=lambda v: 10.0)
        self.simulation = SimpleNamespace(findRoute=lambda a, b, vt="": SimpleNamespace(edges=tuple(t.net.path(a, b, t._cost(False)))))
        self.edge = SimpleNamespace(adaptTraveltime=lambda e, tt: t.weights.__setitem__(e, tt))
        self.lane = SimpleNamespace(getLength=lambda lane: 100.0)

    def _cost(self, own):
        return lambda e: self.adapted[e] if own and e in self.adapted else self.weights.get(e, 1.0)

    def _adapt(self, v, e, tt=None):
        self.calls.append("setAdaptedTraveltime")
        self.adapted.pop(e, None) if tt is None else self.adapted.__setitem__(e, tt)

    def _change(self, v, target):
        self.calls.append("changeTarget")
        p = [self.route[0]] + self.net.path(self.route[1], target, self._cost(True)) if self.committed \
            else self.net.path(self.route[0], target, self._cost(True))
        if not p or p[-1] != target:
            raise traci.TraCIException("no route")
        self.route = p

    def _set(self, v, edges):
        self.calls.append("setRoute")
        if edges[0] != self.route[0] or not self._valid(edges) or (self.refuse and list(edges) != self.original):
            raise traci.TraCIException("refused")
        self.route = list(edges)

    def _valid(self, edges):
        return all(b in self.net.succ(a) for a, b in zip(edges, edges[1:]))


def _detour(route, edge=E, **kw):
    tc = FakeTC(route, **kw)
    tc.edge.adaptTraveltime(edge, BIG)            # what respond() does for the detour method
    outcome, reason, info = ir.detour(tc, "v", edge)
    return tc, outcome, reason, info


def test_bypass_keeps_prefix_destination_and_rejoins_downstream():
    route = ["n1n2", E, "n3n4", "n4m4", "m4m3"]
    tc, outcome, _, info = _detour(route)
    assert outcome == "rerouted" and tc.route == info["final_route"] == ["n1n2", "n2m2", "m2m3", "m3n3", "n3n4", "n4m4", "m4m3"]
    assert info["splices"] == [{"split_index": 0, "split_edge": "n1n2", "rejoin_index": 2, "rejoin_edge": "n3n4",
                                "detour_edges": ["n2m2", "m2m3", "m3n3"], "replaced_edges": [E]}]
    assert tc.adapted == {} and ir.preserved(info, E)       # the split at its own edge was probed and undone
    tc, outcome, _, info = _detour(["m1n1", "n1n2", E, "n3n4"])   # split one edge ahead: findRoute, no probe
    assert outcome == "rerouted" and info["final_route"][:2] == ["m1n1", "n1n2"] and "changeTarget" not in tc.calls


def test_every_occurrence_is_bypassed_by_route_index_not_by_edge_value():
    route = ["m1n1", "n1n2", E, "n3m3", "m3m2", "m2m1", "m1n1", "n1n2", E, "n3n4"]   # n1n2 and E each appear twice
    tc, outcome, _, info = _detour(route)
    assert outcome == "rerouted" and E not in info["final_route"][1:]
    assert [(x["split_index"], x["rejoin_index"]) for x in info["splices"]] == [(1, 3), (7, 9)]
    assert info["final_route"][-4:] == ["n2m2", "m2m3", "m3n3", "n3n4"] and ir.preserved(info, E)
    kept = info["final_route"][info["final_route"].index("n3m3"):info["final_route"].index("n3m3") + 5]
    assert kept == route[3:8]                                     # the original middle section is kept unchanged


def test_the_split_backs_off_when_the_edge_before_is_a_dead_end_into_the_incident():
    route = ["n2n3", "n3n4", "n4m4", "m4m3", "m3m2"]              # n3n4 ends at corner n4: its only exit is n4m4
    tc, outcome, _, info = _detour(route, edge="n4m4")
    assert outcome == "rerouted" and info["final_route"] == ["n2n3", "n3m3", "m3m2"]
    assert [(x["split_index"], x["rejoin_index"]) for x in info["splices"]] == [(0, 4)] and ir.preserved(info, "n4m4")


def test_a_committed_vehicle_is_reported_and_every_rejected_probe_is_undone():
    route = ["n1n2", E, "n3n4", "n4m4"]
    tc, outcome, reason, info = _detour(route, committed=True)
    assert outcome == "no_alternative" and reason.startswith("no detour from any split")
    assert tc.route == route and tc.adapted == {} and info["final_route"] == route and info["splices"] == []
    assert tc.calls.count("changeTarget") == info["probes"] == 2 == tc.calls.count("setRoute")   # each probe restored


def test_inside_a_junction_the_next_edge_never_changes():
    tc, outcome, reason, info = _detour(["n1n2", E, "n3n4"], road=":n2_0")
    assert (outcome, reason) == ("no_alternative", "committed: crossing the junction onto the incident edge")
    assert tc.route == ["n1n2", E, "n3n4"] and tc.calls == []
    tc, outcome, _, info = _detour(["m1n1", "n1n2", E, "n3n4"], road=":n1_0")
    assert outcome == "rerouted" and info["splices"][0]["split_index"] == 1 and "changeTarget" not in tc.calls


def test_a_refused_route_or_a_blocked_destination_leaves_the_vehicle_unchanged():
    tc, outcome, reason, _ = _detour(["m1n1", "n1n2", E, "n3n4"], refuse=True)
    assert outcome == "no_alternative" and reason.startswith("SUMO refused the route") and tc.route == tc.original
    tc, outcome, reason, _ = _detour(["n1n2", E])
    assert (outcome, reason) == ("no_alternative", "its destination is the incident edge") and tc.calls == []


def test_only_a_vehicle_that_accepted_the_alert_is_detoured(monkeypatch):
    monkeypatch.setattr(ir.corroboration, "accept", lambda *a: (True, "ok"))
    alert = {"source_vehicle": "src"}
    record = lambda ok: {"corroboration": {"accepted": ok, "certificate": {}, "use_reputation": True, "committee": []},
                         "vehicles": [{"id": "v", "rx_ms": 2.0, "verified": True}]}
    tc = FakeTC(["n1n2", E, "n3n4"])
    res = ir.respond(tc, alert, record(False), E, 50.0, {}, "detour")      # rejected certificate
    assert res["vehicles"][0]["outcome"] == "not_informed" and tc.route == tc.original and tc.weights == {}
    assert res["route_changes"] == [] and res["global_edge_weight"] is False
    tc = FakeTC(["n1n2", E, "n3n4"])
    res = ir.respond(tc, alert, record(True), E, 50.0, {}, "detour")
    assert res["vehicles"][0]["outcome"] == "rerouted" and res["route_changes"] == ["v"] and tc.weights == {E: BIG}


# ------------------------------------------------------------------ live SUMO
@pytest.fixture(scope="module")
def showcase(tmp_path_factory):
    out = tmp_path_factory.mktemp("routing")
    return {m: ir.run(config.DEMO_DENSITY, config.DEMO_RUN, out_dir=str(out / m), followup_s=60, method=m)
            for m in ("detour", "shortest")}


def test_live_detours_keep_each_route_and_change_nothing_else(showcase):
    g, f = showcase["detour"]["genuine"], showcase["detour"]["forged"]
    edge = g["detection"]["edge"]
    rer = [r for r in g["vehicles"] if r["outcome"] == "rerouted"]
    assert len(rer) >= 40 and set(g["route_changes"]) == {r["id"] for r in rer} and g["global_edge_weight"]
    for r in rer:
        k = r["original_route"].index(edge, 1)
        assert ir.preserved(r, edge) and r["final_route"][:k] == r["original_route"][:k] and r["accepted_alert"]
        assert r["entries_onto_incident_edge"] == 0 and r["final_route"][-1] == r["destination"]
        if r["road"].startswith(":"):
            assert r["splices"][0]["split_index"] >= 1                     # inside a junction: next edge kept
    assert any(len(r["splices"]) > 1 for r in rer)                         # repeated occurrences occur in this seed
    assert all(v for k, v in showcase["detour"]["acceptance"].items() if k != "no_alternative_listed")
    assert f["routes_changed"] == 0 and f["route_changes"] == [] and f["global_edge_weight"] is False


def test_the_shortest_path_baseline_is_kept_and_differs_as_expected(showcase):
    d, s = (showcase[m]["genuine"] for m in ("detour", "shortest"))
    assert s["method"] == "shortest" and s["global_edge_weight"] is False and showcase["shortest"]["acceptance"]["destinations_kept"]
    extra = {m: np.median([r["planned_after_m"] - r["planned_before_m"] for r in g["vehicles"] if r["outcome"] == "rerouted"])
             for m, g in (("detour", d), ("shortest", s))}
    assert extra["detour"] > 0 > extra["shortest"]          # a bypass adds a little; shortest-path cuts the trip short
    edge = s["detection"]["edge"]
    kept = sum(r["final_route"][:r["original_route"].index(edge, 1)] == r["original_route"][:r["original_route"].index(edge, 1)]
               for r in s["vehicles"] if r["outcome"] == "rerouted")
    assert kept < len([r for r in s["vehicles"] if r["outcome"] == "rerouted"]) / 2


def test_the_four_sessions_are_paired_reproducible_and_written_only_to_their_folder(tmp_path):
    a = incident_routing.run_seed((50, 3, str(tmp_path / "a"), 300))
    b = incident_routing.run_seed((50, 3, str(tmp_path / "b"), 300))
    strip = lambda rows: [{k: v for k, v in r.items() if not k.startswith("compute_ms")} for r in rows]
    assert strip(a) == strip(b) and len(a) == 50                         # same seed: same rows (timings excluded)
    assert {r["group"] for r in a} <= {"stopped", "ahead", "upstream", "not_crossing"}
    stopped = [r for r in a if r["group"] == "stopped"]
    assert len(stopped) == 1 and not any(stopped[0][f"finished_{x}"] for x in "BCD")   # it never leaves: unfinished
    for r in a:
        if r["outcome_D"] == "rerouted":
            assert r["eligible"] and r["entries_D"] == 0
        if r["group"] == "not_crossing":
            assert r["outcome_C"] == r["outcome_D"] == ""               # never touched by either method
    assert sorted(p.name for p in (tmp_path / "a").iterdir()) == ["infrastructure", "logs", "raw", "sessions", "tripinfo"]


def test_paired_effects_use_the_seed_as_unit_and_count_unfinished_vehicles():
    rows = []
    for s, diffs in enumerate([[10, 20], [30, 50], [5, 5]]):
        for i, d in enumerate(diffs):
            rows.append({"run_id": f"r{s}", "vehicle": f"v{i}", "detected": 1, "group": "ahead", "depart_s": 0.0,
                         "finished_A": 1, "finished_B": 1, "duration_A_s": 100.0, "duration_B_s": 100.0 + d,
                         "length_A_m": 1000.0, "length_B_m": 1000.0 + d})
    rows.append({**rows[0], "vehicle": "v9", "finished_B": 0, "duration_B_s": 3500.0})   # censored at the end
    e = next(x for x in incident_routing.effects(rows, 3600, "A", "B") if x["seeds"] == "detected" and x["group"] == "ahead")
    seed_means = [15, 40, 5]
    lo, hi = stats.t.interval(0.95, 2, loc=np.mean(seed_means), scale=stats.sem(seed_means))
    assert e["paired"] == 6 and e["unfinished_compared"] == 1 and e["mean_time_s"] == pytest.approx(20)
    assert (e["ci95_low_time_s"], e["ci95_high_time_s"]) == pytest.approx((lo, hi))
    assert e["lower_bound_mean_time_incl_unfinished_s"] == pytest.approx((120 + 3500) / 7)    # 3600 - 0 - 100 = 3500
    json.dumps(e)                                                          # CSV/JSON friendly
