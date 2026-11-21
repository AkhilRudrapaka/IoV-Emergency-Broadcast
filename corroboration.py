"""
Corroboration: an alert is accepted only when a quorum of reputable vehicles
vouches for it, and BLS signatures prove who vouched.

  what is voted on   "is the event in this alert real?"  (one event ID)
  who votes          the committee: the COMMITTEE_SIZE nearest reputable neighbours of
                     the incident. They are close enough to check the claim themselves
  a vote             one BLS signature over the event digest. No signature = no
  one vote each      signatures are bound to distinct public keys; a repeat adds nothing
  how many           QUORUM of COMMITTEE_SIZE (a majority). Fewer: the alert is rejected
  untrusted voters   an endorser with reputation below TRUST_CH_THRESHOLD is not counted
  effect             a rejected alert is neither acted on nor forwarded

Why BLS, and why aggregated (Boneh, Gentry, Lynn, Shacham 2003; IETF draft-irtf-cfrg-bls-signature):
every endorser signs the SAME digest, so their signatures combine into one 96-byte
signature that one verification checks (FastAggregateVerify). The certified alert
therefore carries one signature, not QUORUM + 1, and each receiver verifies once.

What a signature proves: WHO signed. It does not prove the event happened; that
is the committee's job. The simulation charges BLS_SIGN_MS / BLS_VERIFY_MS of
processing time per operation; the py_ecc library does the real mathematics.

Simplifications (see PROJECT_GUIDE.md, Limitations): keys are derived from the vehicle
ID instead of being issued by a PKI with proof of possession; an honest committee
member's observation equals ground truth; reputation values are known network-wide.
"""
import hashlib
from functools import lru_cache

from py_ecc.bls import G2ProofOfPossession as bls
from py_ecc.optimized_bls12_381 import curve_order

from config import COMMITTEE_SIZE, ENFORCE_COMMITTEE, MAX_COLLUDERS, QUORUM, TRUST_CH_THRESHOLD


def secret_key(vehicle_id):
    return int.from_bytes(hashlib.sha256(f"sim-key:{vehicle_id}".encode()).digest(), "big") % (curve_order - 1) + 1


@lru_cache(maxsize=None)
def public_key(vehicle_id):
    return bls.SkToPk(secret_key(vehicle_id))


def digest(alert):
    """The bytes every endorser signs: the event's identity plus its creation time and hop limit, so a relay
    cannot refresh or extend the alert. The per-frame hop COUNT is not signed (it changes at every hop)."""
    x, y = alert["incident_position"]
    return (f"{alert['event_id']}|{alert['message_type']}|{alert['source_vehicle']}|{alert['sequence_number']}"
            f"|{x:.2f}|{y:.2f}|{alert['incident_time_s']:.3f}|{alert['created_s']:.3f}|{alert['hop_limit']}").encode()


@lru_cache(maxsize=None)
def sign(vehicle_id, message):
    return bls.Sign(secret_key(vehicle_id), message)


@lru_cache(maxsize=None)
def verify_aggregate(signer_ids, message, aggregate):
    """One pairing check for any number of signers of the same message."""
    return len(set(signer_ids)) == len(signer_ids) and \
        bls.FastAggregateVerify([public_key(v) for v in signer_ids], message, aggregate)


def certificate(alert, source_id, voter_ids):
    """The source's signature and the votes, aggregated into one signature."""
    signers = (source_id, *voter_ids)
    message = digest(alert)
    return {"signers": list(signers), "aggregate": bls.Aggregate([sign(v, message) for v in signers]).hex()}


def committee(source, dist, adj, n_vehicles, reputation, use_reputation=True):
    """Ranked voters: the nearest neighbours of the incident (reputable ones, if gated)."""
    near = [v for v in sorted(range(n_vehicles), key=lambda v: dist[source, v])
            if v != source and adj[source, v] and (not use_reputation or reputation[v] >= TRUST_CH_THRESHOLD)]
    return near[:COMMITTEE_SIZE]


def plan(alert, source, dist, adj, n_vehicles, reputation, malicious, genuine=True, use_reputation=True,
         require_committee=False):
    """Who may vote and who will. Shared by every forwarding rule run on the same scenario.

    Genuine event: the committee's honest members observe it and endorse; misbehaving
    members stay silent. Forged event: honest vehicles observe nothing and stay silent;
    the forger's misbehaving neighbours (at most MAX_COLLUDERS) collude and endorse it regardless.
    require_committee: the opt-in protection level (Block F) that counts only committee endorsers (accept()).
    ENFORCE_COMMITTEE (Block G) turns it on for every plan, i.e. every voting level."""
    members = committee(source, dist, adj, n_vehicles, reputation, use_reputation)
    if genuine:
        voters = [v for v in members if not malicious[v]]
    else:
        voters = [v for v in sorted(range(n_vehicles), key=lambda v: dist[source, v])
                  if v != source and adj[source, v] and malicious[v]][:MAX_COLLUDERS]
    return {"alert": alert, "committee": members, "voters": voters, "genuine": genuine,
            "reputation": reputation, "use_reputation": use_reputation,
            "require_committee": bool(require_committee or ENFORCE_COMMITTEE)}


def accept(alert, cert, reputation_of, use_reputation=True, committee=None):
    """The rule every receiver (vehicle or RSU) applies. Returns (accepted, reason).
    committee: None (default) counts any reputable endorser. A list of vehicle IDs (the opt-in Block F level) counts only
    endorsers in it: the receiver rebuilds the committee of the claimed incident (its nearest reputable neighbours)
    from beacon positions and the network-wide reputation, which this simulation takes from the recorded snapshot."""
    if cert is None:
        return False, "no certificate"
    signers = tuple(cert["signers"])
    if signers[0] != alert["source_vehicle"]:
        return False, "certificate not signed by the alert's source"
    if not verify_aggregate(signers, digest(alert), bytes.fromhex(cert["aggregate"])):
        return False, "BLS aggregate signature invalid"
    endorsers = [v for v in signers[1:] if (committee is None or v in committee)
                 and (not use_reputation or (reputation_of(v) or 0.0) >= TRUST_CH_THRESHOLD)]  # unknown = untrusted
    if len(endorsers) < QUORUM:
        kind = ("reputable " if use_reputation else "") + ("committee " if committee is not None else "")
        return False, f"only {len(endorsers)} {kind}endorser(s), {QUORUM} needed"
    return True, f"BLS aggregate valid, {len(endorsers)} of {len(signers) - 1} endorsers counted"
