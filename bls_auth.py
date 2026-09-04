"""
BLS (Boneh-Lynn-Shacham) Batch Authentication Module (Priority 2).

Implements real BLS12-381 pairing-based signatures (via `py_ecc.bls.G2ProofOfPossession`,
a pure-Python implementation compliant with the IETF BLS draft / Eth2 spec) for emergency
message authentication, with true aggregate/batch verification: N distinct signatures can
be combined into a single 96-byte aggregate signature and checked with one pairing
operation instead of N independent ones.

PROOF-OF-WORK
--------------
Following [Naskar et al., 2025, Sec. I] "Authentication Framework With Enhanced
Privacy and Batch Verifiable Message Sharing in VANETs": the core premise that
verifying V2V messages one-by-one does not scale, and that a batch-verifiable
scheme reduces per-RSU verification cost, e.g. "our scheme can perform at
least ... 2-times more V2V messages [batch-verified] than other related
schemes within a time threshold of 300 ms" [Naskar et al., 2025, Abstract].
Naskar et al.'s OWN scheme is a NIZK-based ECDSA* protocol (Chaum-Pedersen
proofs, epoch certificates, CA registration, Fig. 2) -- this module does not
implement that protocol. It implements real BLS12-381 aggregate signatures
(py_ecc, IETF BLS-draft/Eth2 ciphersuite) as this project's improvement on
Naskar et al.'s batch-verification premise, chosen because BLS supports true
signature aggregation (an N-signature batch collapses to one constant-size
96-byte signature) where ECDSA does not -- see ecdsa_auth.py for the real,
directly-comparable ECDSA ablation arm kept faithful to Naskar et al.'s
specified scheme (standard sign/verify, not the full NIZK protocol -- see that
module's own docstring).
The trust-TIERED verification split (aggregate for high-trust signers,
individual for mid-trust, immediate rejection for low-trust, see
AuthenticationManager.verify_message) is this project's own extension,
combining Naskar et al.'s batch-verification goal with the trust gating this
project's Sec. 1 (trust.py) already computes -- Naskar et al. does not
publish a trust-tiered verification split.
MAX_CHAIN_SIGNERS=14 (~100 ms deadline / ~7 ms per signature) is drawn from
the project's own Report specification, not independently verified against
Naskar et al.'s own 300 ms comparison threshold (Naskar et al. benchmark at
batch size L=210, a different scale) -- both figures are disclosed here rather
than conflated.

Integration model
------------------
When an emergency alert is disseminated, the sending vehicle AND every Cluster Head that
is currently active co-sign a distinct attestation of the alert ("chain signatures").
This gives the RSU a genuine multi-signer batch to verify on every alert, rather than a
single signature — the natural place BLS aggregation pays off. High-trust signers are
verified as one aggregate batch; low-trust signers are individually verified (or rejected
outright, per config), so trust scores directly gate how authentication cost is spent.

Security discussion (scoped to this simulation)
-------------------------------------------------
- **False emergency alerts / message forgery**: each attestation is a BLS signature over
  `message_id | sender | location | severity | signer_id | role`. Forging a valid signature
  without the signer's secret key requires breaking the co-CDH assumption on BLS12-381 —
  computationally infeasible for the scheme's security parameter. Any tampering with the
  message content after signing changes the recomputed payload at verify time, so the
  stored signature no longer matches and verification deterministically fails (the same
  tamper-evidence property the SHA-256 baseline in `authentication.py` demonstrates, now
  backed by a standard asymmetric hardness assumption instead of a shared secret that, if
  leaked, silently breaks the whole scheme). Cryptographic validity proves the message came
  from the claimed key holder — it does NOT prove the *content* is true; that judgment is
  deliberately left to the trust layer (`trust.py`), which is why the two are combined here
  rather than treating a valid signature alone as sufficient.
- **Sybil considerations**: BLS authentication proves possession of a specific registered
  keypair, not the real-world uniqueness of the identity behind it. `BLSKeyRegistry` issues
  a keypair to any new vehicle_id on demand with no identity-proofing step, mirroring this
  simulation's open vehicle-classification model — an attacker could in principle register
  many keypairs. Sybil *resistance* in this system therefore still rests on the existing
  behavior-based trust/blacklist mechanisms, which penalize observed behavior regardless of
  how many signing identities an attacker controls. A production VANET PKI would add a
  registration-time certificate authority (e.g. IEEE 1609.2 pseudonym certificates) — out of
  scope for this simulation.
- **Rogue-key attacks on aggregate signatures**: the classic attack against BLS aggregation
  (crafting a public key as a function of others' keys to forge a valid-looking aggregate)
  requires signers to share an identical message. Every signer here signs a payload that
  embeds its own `signer_id` and `role`, which is unique per signer by construction — this
  is the standard "distinct message" precondition under which the basic BLS aggregate
  scheme is provably secure without needing a separate proof-of-possession registration step.
"""

import os
import csv
import time

from py_ecc.bls import G2ProofOfPossession as bls_scheme

from authentication import verify_signature as legacy_verify_signature

try:
    from config import (
        AUTHENTICATION_MODE, BLS_TRUST_THRESHOLD, BLS_MID_TRUST_THRESHOLD,
        BLS_BENCHMARK_BATCH_SIZES, MAX_CHAIN_SIGNERS
    )
except ImportError:
    AUTHENTICATION_MODE = "bls_batch"
    BLS_TRUST_THRESHOLD = 0.7
    BLS_MID_TRUST_THRESHOLD = 0.3
    BLS_BENCHMARK_BATCH_SIZES = [1, 2, 5, 10, 20]
    MAX_CHAIN_SIGNERS = 14


class BLSKeyPair:
    """A single vehicle/RSU's BLS12-381 keypair, generated via the IETF-draft KeyGen."""

    def __init__(self):
        self.secret_key = bls_scheme.KeyGen(os.urandom(32))
        self.public_key = bls_scheme.SkToPk(self.secret_key)


class BLSKeyRegistry:
    """
    In-memory vehicle_id -> BLSKeyPair registry.

    Represents the trusted-registration/PKI assumption standard in VANET security
    models (e.g. IEEE 1609.2) — modeling the certificate authority itself is out of
    scope for this simulation; keys are lazily issued the first time a vehicle signs.
    """

    def __init__(self):
        self._keypairs = {}

    def get_or_create(self, vehicle_id):
        vehicle_id = str(vehicle_id)
        if vehicle_id not in self._keypairs:
            self._keypairs[vehicle_id] = BLSKeyPair()
        return self._keypairs[vehicle_id]

    def get_public_key(self, vehicle_id):
        kp = self._keypairs.get(str(vehicle_id))
        return kp.public_key if kp else None


class BLSAuthenticator:
    """
    Low-level BLS sign/verify/batch-verify wrapper with built-in performance telemetry.
    """

    def __init__(self):
        self.sign_time_samples = []
        self.individual_verify_time_samples = []
        self.batch_verify_time_samples = []
        self.batch_sizes = []
        self.signature_size_bytes = 96   # BLS12-381 G2 signature, constant regardless of aggregation
        self.public_key_size_bytes = 48  # BLS12-381 G1 public key

    def sign(self, payload, keypair):
        """Signs `payload` (bytes) with `keypair`, returning the 96-byte signature."""
        t0 = time.perf_counter()
        signature = bls_scheme.Sign(keypair.secret_key, payload)
        self.sign_time_samples.append(time.perf_counter() - t0)
        return signature

    def verify(self, payload, signature, public_key):
        """Verifies a single (payload, signature, public_key) triple."""
        t0 = time.perf_counter()
        try:
            result = bls_scheme.Verify(public_key, payload, signature)
        except Exception:
            result = False
        self.individual_verify_time_samples.append(time.perf_counter() - t0)
        return result

    def verify_batch(self, payloads, signatures, public_keys):
        """
        True BLS batch verification: aggregates all signatures into one and performs a
        single AggregateVerify pairing check instead of N independent verifications.
        Requires each payload to be distinct across signers (satisfied here since every
        payload embeds its own signer_id/role) — the standard security precondition for
        the 'Basic' BLS aggregate-signature scheme.

        On aggregate failure, falls back to per-item verification to identify which
        signature(s) are invalid (an aggregate check only proves *something* is wrong,
        not which signer is responsible).

        Returns:
            (all_valid: bool, per_item_results: list[bool])
        """
        n = len(signatures)
        if n == 0:
            return True, []
        if n == 1:
            ok = self.verify(payloads[0], signatures[0], public_keys[0])
            self.batch_verify_time_samples.append(self.individual_verify_time_samples[-1])
            self.batch_sizes.append(1)
            return ok, [ok]

        t0 = time.perf_counter()
        try:
            aggregate_signature = bls_scheme.Aggregate(signatures)
            all_valid = bls_scheme.AggregateVerify(public_keys, payloads, aggregate_signature)
        except Exception:
            all_valid = False
        self.batch_verify_time_samples.append(time.perf_counter() - t0)
        self.batch_sizes.append(n)

        if all_valid:
            return True, [True] * n

        per_item = [self.verify(p, s, pk) for p, s, pk in zip(payloads, signatures, public_keys)]
        return all(per_item), per_item

    def get_performance_summary(self):
        """Running averages/counters over every sign/verify/batch call made so far."""
        def avg(samples):
            return (sum(samples) / len(samples)) if samples else 0.0

        return {
            "avg_sign_time_ms": avg(self.sign_time_samples) * 1000.0,
            "avg_individual_verify_time_ms": avg(self.individual_verify_time_samples) * 1000.0,
            "avg_batch_verify_time_ms": avg(self.batch_verify_time_samples) * 1000.0,
            "avg_batch_size": avg(self.batch_sizes),
            "signature_size_bytes": self.signature_size_bytes,
            "public_key_size_bytes": self.public_key_size_bytes,
            "total_signs": len(self.sign_time_samples),
            "total_individual_verifies": len(self.individual_verify_time_samples),
            "total_batches": len(self.batch_verify_time_samples),
        }


class AuthenticationManager:
    """
    Mode-driven authentication integration layer used by RSUs and the simulation
    orchestration code. Dispatches between the legacy SHA-256 baseline and BLS
    individual/batch verification per `config.AUTHENTICATION_MODE`, and applies
    trust-based gating in "bls_batch" mode.

    Modes:
        "none"           - no authentication performed; every message is accepted
                            (ablation floor: what happens with no auth at all).
        "baseline"        - legacy SHA-256 placeholder (authentication.py), unchanged.
        "bls_individual" - every chain signature is BLS-verified independently, no
                            trust gating (ablation point: BLS without our optimization).
        "bls_batch"       - Report Algorithm 4's tiered verification: T>=0.7 signers
                            are aggregate-verified in one batch; 0.3<=T<0.7 signers
                            are individually verified; T<0.3 signers are rejected
                            immediately with no verify attempt at all (real compute
                            saved, not just a post-hoc rejection).
    """

    def __init__(self, mode=None, trust_threshold=None, mid_trust_threshold=None, logger=None):
        self.mode = mode or AUTHENTICATION_MODE
        self.trust_threshold = trust_threshold if trust_threshold is not None else BLS_TRUST_THRESHOLD
        self.mid_trust_threshold = mid_trust_threshold if mid_trust_threshold is not None else BLS_MID_TRUST_THRESHOLD
        self.logger = logger

        self.registry = BLSKeyRegistry()
        self.bls = BLSAuthenticator()

        self.auth_success = 0
        self.auth_failures = 0

    @staticmethod
    def _build_payload(message, signer_id, role):
        """
        Canonical per-signer payload: binds the core message content (so tampering is
        caught) together with the signer's identity and role (so every signer's payload
        is distinct, satisfying the aggregate-signature security precondition).
        """
        return f"{message.message_id}|{message.sender}|{message.location}|{message.severity}|{signer_id}|{role}".encode("utf-8")

    def sign_emergency_broadcast(self, message, sender_vehicle_id, cluster_heads, vehicles=None):
        """
        Populates `message.chain_signatures` with one BLS attestation from the sending
        vehicle and one from every currently active Cluster Head, capped at
        MAX_CHAIN_SIGNERS total (Report S6: CH pre-screening limit, ~100ms deadline
        / ~7ms per signature) -- when more CHs than that are active, only the
        highest-trust ones co-sign. No-op outside BLS modes (the SHA-256
        `.signature` field set by `accident.py` is untouched either way).
        """
        if self.mode not in ("bls_individual", "bls_batch"):
            return message

        message.chain_signatures = []
        t0 = time.perf_counter()

        sender_id = str(sender_vehicle_id)
        sender_kp = self.registry.get_or_create(sender_id)
        sender_sig = self.bls.sign(self._build_payload(message, sender_id, "SENDER"), sender_kp)
        message.chain_signatures.append({
            "signer_id": sender_id, "role": "SENDER",
            "signature": sender_sig, "public_key": sender_kp.public_key
        })

        vehicles = vehicles or {}
        ch_ids = [str(ch_id) for ch_id in (cluster_heads or {}).values() if str(ch_id) != sender_id]
        max_co_signers = max(0, MAX_CHAIN_SIGNERS - 1)  # sender already counted
        if len(ch_ids) > max_co_signers:
            ch_ids.sort(key=lambda cid: vehicles[cid].trust if cid in vehicles else 0.0, reverse=True)
            ch_ids = ch_ids[:max_co_signers]

        for ch_id in ch_ids:
            ch_kp = self.registry.get_or_create(ch_id)
            ch_sig = self.bls.sign(self._build_payload(message, ch_id, "FORWARDING_CH"), ch_kp)
            message.chain_signatures.append({
                "signer_id": ch_id, "role": "FORWARDING_CH",
                "signature": ch_sig, "public_key": ch_kp.public_key
            })

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if self.logger:
            self.logger.log(
                f"[BLS Auth] Signed emergency broadcast '{message.message_id}' with "
                f"{len(message.chain_signatures)} chain signature(s) "
                f"(1 sender + {len(message.chain_signatures) - 1} active Cluster Head(s)) "
                f"in {elapsed_ms:.2f} ms -- SUCCESS"
            )

        return message

    def _report_auth_event(self, signer_id, is_success, vehicles, trust_manager):
        """
        Feeds a real per-signer verification outcome into the trust model's
        auth_attempts/auth_successes counters (Priority 2 <-> Priority 3 integration
        point). No-op if no trust_manager was supplied (e.g. benchmark-only calls).
        """
        if not trust_manager or not vehicles:
            return
        vehicle = vehicles.get(str(signer_id))
        if vehicle is not None:
            trust_manager.update_behavior_event(vehicle, "AUTH", is_success=is_success)

    def verify_message(self, message, vehicles=None, trust_manager=None):
        """
        Verifies an incoming emergency message per the configured mode.

        Args:
            trust_manager (trust.TrustManager, optional): when provided, every
                signer's real verification outcome (sender and each co-signing CH)
                is fed back into their observed auth_attempts/auth_successes via
                update_behavior_event(), instead of trust.py's T_auth factor being
                permanently unpopulated.

        Returns:
            (is_valid: bool, perf_dict: dict | None)
        """
        vehicles = vehicles or {}

        if self.mode == "none":
            return True, None

        entries = getattr(message, "chain_signatures", None)

        if self.mode not in ("bls_individual", "bls_batch") or not entries:
            result = legacy_verify_signature(message)
            self._record_result(result)
            self._report_auth_event(message.sender, result, vehicles, trust_manager)
            return result, None

        if self.mode == "bls_individual":
            results = []
            for entry in entries:
                payload = self._build_payload(message, entry["signer_id"], entry["role"])
                ok = self.bls.verify(payload, entry["signature"], entry["public_key"])
                results.append(ok)
                self._report_auth_event(entry["signer_id"], ok, vehicles, trust_manager)
            overall = all(results)
            self._record_result(overall)
            return overall, self.bls.get_performance_summary()

        # "bls_batch": Report Algorithm 4's unconditional 3-tier verification.
        high_trust, mid_trust, rejected = [], [], []
        for entry in entries:
            vehicle = vehicles.get(entry["signer_id"])
            trust = vehicle.trust if vehicle is not None else 0.0
            if trust >= self.trust_threshold:
                high_trust.append(entry)
            elif trust >= self.mid_trust_threshold:
                mid_trust.append(entry)
            else:
                rejected.append(entry)

        high_trust_valid = True
        if high_trust:
            payloads = [self._build_payload(message, e["signer_id"], e["role"]) for e in high_trust]
            sigs = [e["signature"] for e in high_trust]
            pks = [e["public_key"] for e in high_trust]
            high_trust_valid, per_item = self.bls.verify_batch(payloads, sigs, pks)
            for entry, ok in zip(high_trust, per_item):
                self._report_auth_event(entry["signer_id"], ok, vehicles, trust_manager)

        mid_trust_valid = True
        for entry in mid_trust:
            payload = self._build_payload(message, entry["signer_id"], entry["role"])
            ok = self.bls.verify(payload, entry["signature"], entry["public_key"])
            self._report_auth_event(entry["signer_id"], ok, vehicles, trust_manager)
            if not ok:
                mid_trust_valid = False

        # T < 0.3: rejected immediately, no verify attempt at all -- real compute
        # saved, and a blacklisted-trust signer's signature is never even checked.
        rejected_valid = not rejected
        if rejected:
            for entry in rejected:
                self._report_auth_event(entry["signer_id"], False, vehicles, trust_manager)
            if self.logger:
                self.logger.log(
                    f"[BLS Auth] Rejected {len(rejected)} signer(s) outright (trust < {self.mid_trust_threshold})."
                )

        overall = high_trust_valid and mid_trust_valid and rejected_valid
        self._record_result(overall)
        perf = self.bls.get_performance_summary()
        perf["high_trust_count"] = len(high_trust)
        perf["mid_trust_count"] = len(mid_trust)
        perf["rejected_count"] = len(rejected)
        return overall, perf

    def _record_result(self, is_valid):
        if is_valid:
            self.auth_success += 1
        else:
            self.auth_failures += 1

    def get_summary(self):
        """Combined BLS performance + authentication outcome counters for metrics/logging."""
        summary = self.bls.get_performance_summary()
        summary["bls_auth_success"] = self.auth_success
        summary["bls_auth_failures"] = self.auth_failures
        return summary

    def run_performance_benchmark(self, batch_sizes=None, logger=None):
        """
        Controlled synthetic benchmark, independent of however many real emergency
        events occurred in the live scenario: for each N in `batch_sizes`, signs N
        synthetic messages with fresh keypairs and times N sequential individual
        verifications vs one aggregate batch verification. This is what produces
        clean, reportable "individual vs batch" numbers for the paper.

        Returns a list of per-batch-size result dicts.
        """
        sizes = batch_sizes or BLS_BENCHMARK_BATCH_SIZES
        log = logger or self.logger
        results = []

        for n in sizes:
            bench = BLSAuthenticator()
            payloads, sigs, pks = [], [], []
            for i in range(n):
                kp = BLSKeyPair()
                payload = f"benchmark-message-{n}-{i}".encode("utf-8")
                sigs.append(bench.sign(payload, kp))
                payloads.append(payload)
                pks.append(kp.public_key)

            t0 = time.perf_counter()
            for p, s, pk in zip(payloads, sigs, pks):
                bench.verify(p, s, pk)
            individual_total_s = time.perf_counter() - t0

            batch_valid, _ = bench.verify_batch(payloads, sigs, pks)
            batch_total_s = bench.batch_verify_time_samples[-1]

            row = {
                "batch_size": n,
                "individual_total_time_ms": round(individual_total_s * 1000.0, 3),
                "individual_avg_time_ms": round(individual_total_s / n * 1000.0, 3),
                "batch_total_time_ms": round(batch_total_s * 1000.0, 3),
                "speedup_ratio": round(individual_total_s / batch_total_s, 3) if batch_total_s > 0 else 0.0,
                "signature_bytes_individual": n * bench.signature_size_bytes,
                "signature_bytes_aggregated": bench.signature_size_bytes,
                "batch_valid": bool(batch_valid)
            }
            results.append(row)

            if log:
                log.log(
                    f"[BLS Benchmark] N={n:<3} Individual={row['individual_total_time_ms']:>9.2f}ms "
                    f"Batch={row['batch_total_time_ms']:>9.2f}ms Speedup={row['speedup_ratio']:.2f}x "
                    f"CommOverhead={row['signature_bytes_individual']}B -> {row['signature_bytes_aggregated']}B"
                )

        return results

    def save_benchmark_csv(self, results, filepath="outputs/logs/bls_benchmark.csv"):
        """Writes benchmark results to CSV, matching the project's existing CSV-export style."""
        dir_name = os.path.dirname(os.path.abspath(filepath))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        fieldnames = [
            "batch_size", "individual_total_time_ms", "individual_avg_time_ms",
            "batch_total_time_ms", "speedup_ratio", "signature_bytes_individual",
            "signature_bytes_aggregated", "batch_valid"
        ]
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"[BLS Auth] Saved batch-verification benchmark CSV to '{filepath}'")
        return filepath
