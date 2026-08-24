import unittest

from utils import compute_delay_ms
from comparison import ComparisonEngine


class TestComputeDelayMs(unittest.TestCase):
    """
    Regression coverage for the shared analytic delay model that replaced the
    three independently-fabricated hardcoded delay formulas (comparison.py had
    two different constants for PROPOSED/FLOODING, sumo_interface.py had a third).
    """

    def test_delay_scales_with_hops(self):
        one_hop = compute_delay_ms(hops=1)
        three_hops = compute_delay_ms(hops=3)
        self.assertGreater(three_hops, one_hop)
        # Exactly 3x the per-hop cost when there's no verification overhead.
        self.assertAlmostEqual(three_hops, one_hop * 3, places=6)

    def test_zero_or_negative_hops_treated_as_one(self):
        self.assertEqual(compute_delay_ms(hops=0), compute_delay_ms(hops=1))

    def test_verification_time_adds_on_top(self):
        base = compute_delay_ms(hops=2)
        with_verify = compute_delay_ms(hops=2, verification_ms=100.0)
        self.assertAlmostEqual(with_verify - base, 100.0, places=6)

    def test_larger_signature_increases_delay(self):
        small_sig = compute_delay_ms(hops=1, signature_bytes=0)
        large_sig = compute_delay_ms(hops=1, signature_bytes=1000)
        self.assertGreater(large_sig, small_sig)


class TestComparisonEngineSmoke(unittest.TestCase):
    """
    comparison.py previously had zero test coverage despite producing every
    headline number in the evaluation harness. This is not a full behavioral
    suite, just a smoke test that the harness still runs end-to-end and returns
    a well-formed result after the D1-D7 integrity fixes.
    """

    def setUp(self):
        self.engine = ComparisonEngine()

    def test_run_density_simulation_returns_well_formed_result(self):
        result = self.engine.run_density_simulation(20, algorithm="PROPOSED", steps=10, seed=1)
        for key in ("density", "algorithm", "pdr", "delay_ms", "routing_delay_ms",
                    "verification_delay_ms", "overhead", "duplicates", "hops",
                    "throughput_kbps", "auth_success_rate", "ch_changes"):
            self.assertIn(key, result)
        self.assertEqual(result["density"], 20)
        self.assertEqual(result["algorithm"], "PROPOSED")
        self.assertGreaterEqual(result["pdr"], 0.0)
        self.assertLessEqual(result["pdr"], 100.0)

    def test_flooding_arm_runs_without_bls_overhead(self):
        result = self.engine.run_density_simulation(20, algorithm="FLOODING", steps=10, seed=1)
        self.assertEqual(result["verification_delay_ms"], 0.0)

    def test_ablation_mode_is_threaded_through(self):
        # Should not raise, and should actually take effect (auth "none" -> every
        # message accepted, no BLS verification time recorded).
        result = self.engine.run_density_simulation(
            20, algorithm="PROPOSED", steps=10, seed=1, authentication_mode="none"
        )
        self.assertEqual(result["verification_delay_ms"], 0.0)

    def test_average_metrics_reports_dispersion(self):
        runs = [
            self.engine.run_density_simulation(20, algorithm="PROPOSED", steps=10, seed=s)
            for s in (1, 11, 21)
        ]
        avg = self.engine._average_metrics(runs)
        self.assertEqual(avg["runs"], 3)
        self.assertIn("delay_ms_std", avg)
        self.assertIn("delay_ms_ci95", avg)
        self.assertGreaterEqual(avg["delay_ms_std"], 0.0)


if __name__ == "__main__":
    unittest.main()
