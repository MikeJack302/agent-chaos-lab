import unittest

from agentchaos.data import Policy, Scenario, Step
from agentchaos.metrics import paired_bootstrap, summarize
from agentchaos.sim import simulate


P0 = Policy("base", 0, frozenset(), 0, 1, False, False, False, None, None)
P1 = Policy("retry", 2, frozenset({"timeout"}), 1, 2, False, False, False, None, None)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.scenario = Scenario("x", (Step("s", 1, 10, 0, True, True, {"timeout": 0.3}),))

    def test_pass_k_declines_with_k(self):
        metrics = summarize(simulate(self.scenario, P0, runs=100, seed=3))
        self.assertGreaterEqual(metrics["pass_k_all_succeed"]["1"], metrics["pass_k_all_succeed"]["5"])

    def test_paired_comparison_detects_retry_success_gain(self):
        base = simulate(self.scenario, P0, runs=1000, seed=4)
        retry = simulate(self.scenario, P1, runs=1000, seed=4)
        result = paired_bootstrap(retry, base, samples=200, seed=8)
        self.assertTrue(result["deltas"]["safe_success"]["likely_better"])
        self.assertGreater(result["deltas"]["attempts"]["mean_delta"], 0)

    def test_mismatched_run_ids_fail(self):
        left = simulate(self.scenario, P0, runs=2)
        right = simulate(self.scenario, P0, runs=3)
        with self.assertRaisesRegex(ValueError, "same"):
            paired_bootstrap(left, right, samples=10)


if __name__ == "__main__":
    unittest.main()
