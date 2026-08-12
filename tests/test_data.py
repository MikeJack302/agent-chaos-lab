import json
from pathlib import Path
import tempfile
import unittest

from agentchaos.data import lint_policy, load_policies, load_scenario, parse_policy


class DataTests(unittest.TestCase):
    def test_fault_probability_sum_is_bounded(self):
        scenario = {
            "name": "x",
            "steps": [{"name": "s", "cost_usd": 0, "latency_ms": 1, "faults": {"timeout": 0.8, "rate_limit": 0.3}}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sum"):
                load_scenario(path)

    def test_policy_rejects_unknown_fault(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            parse_policy({"name": "x", "retry_on": ["cosmic_ray"]})

    def test_duplicate_policy_names_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policies.json"
            path.write_text(json.dumps([{"name": "x"}, {"name": "x"}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                load_policies(path)

    def test_linter_flags_unsafe_non_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            scenario_path = Path(directory) / "scenario.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "name": "x",
                        "steps": [
                            {
                                "name": "charge",
                                "cost_usd": 0,
                                "latency_ms": 1,
                                "idempotent": False,
                                "faults": {"ambiguous_commit": 0.1},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            scenario = load_scenario(scenario_path)
            policy = parse_policy(
                {"name": "bad", "max_retries": 1, "retry_on": ["ambiguous_commit"], "unsafe_retry": True}
            )
            self.assertIn("duplicate", lint_policy(scenario, policy)[0])


if __name__ == "__main__":
    unittest.main()
