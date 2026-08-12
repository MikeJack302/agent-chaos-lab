import unittest

from agentchaos.data import Policy, Scenario, Step
from agentchaos.experiment import run_experiment
from agentchaos.report import render_html


class ExperimentTests(unittest.TestCase):
    def test_end_to_end_and_html_escape(self):
        scenario = Scenario("demo", (Step("tool", 0.1, 10, 0, True, True, {"timeout": 0.2}),))
        policies = [
            Policy("base", 0, frozenset(), 0, 1, False, False, False, None, None),
            Policy("retry", 1, frozenset({"timeout"}), 1, 1, False, False, False, None, None),
        ]
        result = run_experiment(scenario, policies, runs=100, bootstrap_samples=20)
        self.assertEqual(result["baseline"], "base")
        html = render_html(result, title="<script>x</script>")
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
