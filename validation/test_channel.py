"""The channel must reproduce the three storm mechanisms: carrier-sense deferral,
collisions (incl. hidden terminals) and half-duplex loss."""
import numpy as np

from channel import Channel, geometry, simulate, FRAME_SLOTS, AIFS_SLOTS
from protocols import Flooding


def _run_until_quiet(ch, horizon=400):
    got = []
    for t in range(horizon):
        for s, rx, _ in ch.finish(t):
            got += [(s, int(r), t) for r in rx]
        ch.contend(t)
    return got


def _channel(xy, backoffs):
    _, adj = geometry(np.array(xy, float))
    ch = Channel(adj, np.random.default_rng(0))
    for node, bo in backoffs.items():
        ch.enqueue(node)
        ch.backoff[node] = bo
    return ch


def test_single_link_timing():
    ch = _channel([(0, 0), (200, 0)], {0: 2})
    got = _run_until_quiet(ch)
    assert got == [(0, 1, AIFS_SLOTS + 2 + FRAME_SLOTS)]       # AIFS, 2 backoff slots, then airtime


def test_carrier_sense_defers_instead_of_colliding():
    ch = _channel([(0, 0), (100, 0), (200, 0)], {0: 0, 2: 3})  # 0 and 2 hear each other (200 m)
    got = _run_until_quiet(ch)
    assert {(s, r) for s, r, _ in got} == {(0, 1), (0, 2), (2, 1), (2, 0)}
    assert all(tx["lost"] == 0 for tx in ch.log)
    assert ch.log[1]["start"] >= ch.log[0]["end"]             # node 2 waited for node 0


def test_hidden_terminals_collide_at_the_middle():
    ch = _channel([(0, 0), (290, 0), (580, 0)], {0: 1, 2: 1})  # 0 and 2 cannot hear each other
    got = _run_until_quiet(ch)
    assert got == []                                           # the middle vehicle decodes neither frame
    assert [tx["lost"] for tx in ch.log] == [1, 1]


def test_same_slot_backoff_collides_even_without_hidden_terminals():
    ch = _channel([(0, 0), (100, 0), (200, 0)], {0: 2, 2: 2})
    assert _run_until_quiet(ch) == []                          # half-duplex + overlap: nobody decodes


def test_flooding_reaches_a_chain_once_per_vehicle():
    xy = np.array([(0, 0), (250, 0), (500, 0), (750, 0)], float)
    dist, adj = geometry(xy)
    p = Flooding(dist, adj, np.zeros(4, bool))
    log = simulate(p, adj, 0, np.random.default_rng(1))
    assert p.has.all() and len(log) == 4 and sorted(tx["sender"] for tx in log) == [0, 1, 2, 3]
