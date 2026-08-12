"""Run and compare recovery policies under identical injected faults."""

from __future__ import annotations

from typing import Any, Iterable

from .data import Policy, Scenario, lint_policy
from .metrics import paired_bootstrap, summarize
from .sim import simulate


def run_experiment(
    scenario: Scenario,
    policies: Iterable[Policy],
    *,
    runs: int = 5000,
    seed: int = 7,
    bootstrap_samples: int = 2000,
) -> dict[str, Any]:
    policy_list = list(policies)
    if not policy_list:
        raise ValueError("at least one policy is required")
    results = {policy.name: simulate(scenario, policy, runs=runs, seed=seed) for policy in policy_list}
    baseline = policy_list[0].name
    return {
        "scenario": scenario.name,
        "runs": runs,
        "seed": seed,
        "baseline": baseline,
        "policies": {
            policy.name: {
                "warnings": lint_policy(scenario, policy),
                "metrics": summarize(results[policy.name]),
                "vs_baseline": None
                if policy.name == baseline
                else paired_bootstrap(
                    results[policy.name],
                    results[baseline],
                    samples=bootstrap_samples,
                    seed=seed + 1009,
                ),
            }
            for policy in policy_list
        },
    }
