import unittest

from agentchaos.data import Policy, Scenario, Step, Verification
from agentchaos.sim import simulate, simulate_run


def policy(**overrides):
    values = {
        "name": "p",
        "max_retries": 0,
        "retry_on": frozenset(),
        "backoff_ms": 0,
        "backoff_multiplier": 1,
        "verify_ambiguous": False,
        "unsafe_retry": False,
        "enable_fallback": False,
        "max_cost_usd": None,
        "max_latency_ms": None,
    }
    values.update(overrides)
    return Policy(**values)


class SimulationTests(unittest.TestCase):
    def test_deterministic_replay(self):
        scenario = Scenario("x", (Step("s", 1, 100, 0.2, True, True, {"timeout": 0.5}),))
        self.assertEqual(simulate(scenario, policy(), runs=30, seed=9), simulate(scenario, policy(), runs=30, seed=9))

    def test_retry_improves_transient_success(self):
        scenario = Scenario("x", (Step("s", 1, 100, 0, True, True, {"transient": 0.5}),))
        base = simulate(scenario, policy(), runs=1000, seed=2)
        retry = simulate(
            scenario,
            policy(max_retries=2, retry_on=frozenset({"transient"})),
            runs=1000,
            seed=2,
        )
        self.assertGreater(sum(item.success for item in retry), sum(item.success for item in base))

    def test_unsafe_retry_can_duplicate_commit(self):
        scenario = Scenario(
            "x",
            (Step("charge", 1, 1, 0, True, False, {"ambiguous_commit": 1.0}, 1.0),),
        )
        result = simulate_run(
            scenario,
            policy(
                max_retries=1,
                retry_on=frozenset({"ambiguous_commit"}),
                unsafe_retry=True,
            ),
            run_id=0,
        )
        self.assertTrue(result.duplicate_side_effect)
        self.assertFalse(result.safe_success)

    def test_verification_recovers_committed_operation_without_retry(self):
        scenario = Scenario(
            "x",
            (
                Step(
                    "charge", 1, 10, 0, True, False,
                    {"ambiguous_commit": 1.0}, 1.0,
                    Verification(cost_usd=0.1, latency_ms=2),
                ),
            ),
        )
        result = simulate_run(
            scenario,
            policy(
                max_retries=1,
                retry_on=frozenset({"ambiguous_commit"}),
                verify_ambiguous=True,
            ),
            run_id=0,
        )
        self.assertTrue(result.safe_success)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.verifications, 1)

    def test_budget_stops_workflow(self):
        scenario = Scenario("x", (Step("expensive", 2, 10, 0, True, True, {}),))
        result = simulate_run(scenario, policy(max_cost_usd=1), run_id=0)
        self.assertEqual(result.terminal_reason, "cost_budget")

    def test_noncritical_failure_degrades_but_continues(self):
        scenario = Scenario(
            "x",
            (
                Step("optional", 0, 1, 0, False, True, {"timeout": 1}),
                Step("critical", 0, 1, 0, True, True, {}),
            ),
        )
        result = simulate_run(scenario, policy(), run_id=0)
        self.assertTrue(result.success)
        self.assertTrue(result.degraded)


if __name__ == "__main__":
    unittest.main()
