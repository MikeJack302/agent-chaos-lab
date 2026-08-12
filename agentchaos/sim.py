"""Deterministic agent workflow fault injection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Iterable

from .data import FAULTS, Policy, Scenario, Step


@dataclass(frozen=True)
class RunResult:
    run_id: int
    success: bool
    safe_success: bool
    degraded: bool
    duplicate_side_effect: bool
    cost_usd: float
    latency_ms: float
    attempts: int
    retries: int
    verifications: int
    fallbacks: int
    failed_step: str | None
    terminal_reason: str
    injected_faults: tuple[str, ...]


def _uniform(seed: int, run_id: int, step: str, attempt: int, purpose: str) -> float:
    material = f"{seed}|{run_id}|{step}|{attempt}|{purpose}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _fault(step: Step, draw: float) -> str | None:
    boundary = 0.0
    for name in FAULTS:
        boundary += step.faults.get(name, 0.0)
        if draw < boundary:
            return name
    return None


def simulate_run(scenario: Scenario, policy: Policy, *, run_id: int, seed: int = 7) -> RunResult:
    cost = 0.0
    latency = 0.0
    attempts = 0
    retries = 0
    verifications = 0
    fallbacks = 0
    degraded = False
    duplicate = False
    injected: list[str] = []

    def budget_reason() -> str | None:
        if policy.max_cost_usd is not None and cost > policy.max_cost_usd:
            return "cost_budget"
        if policy.max_latency_ms is not None and latency > policy.max_latency_ms:
            return "latency_budget"
        return None

    for step in scenario.steps:
        step_succeeded = False
        failure = "unknown"
        for attempt in range(policy.max_retries + 1):
            attempts += 1
            jitter_draw = _uniform(seed, run_id, step.name, attempt, "latency")
            latency += step.latency_ms * (1 + step.latency_jitter * (2 * jitter_draw - 1))
            cost += step.cost_usd
            budget = budget_reason()
            if budget:
                return RunResult(run_id, False, False, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, step.name, budget, tuple(injected))

            failure = _fault(step, _uniform(seed, run_id, step.name, attempt, "fault")) or "success"
            if failure == "success":
                step_succeeded = True
                break
            injected.append(f"{step.name}:{failure}")

            if failure == "ambiguous_commit":
                committed = _uniform(seed, run_id, step.name, attempt, "committed") < step.ambiguous_commit_probability
                if policy.verify_ambiguous and step.verification is not None:
                    verifications += 1
                    cost += step.verification.cost_usd
                    latency += step.verification.latency_ms
                    budget = budget_reason()
                    if budget:
                        return RunResult(run_id, False, False, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, step.name, budget, tuple(injected))
                    if committed:
                        step_succeeded = True
                        break
                elif committed and step.idempotent:
                    pass
                elif committed and policy.unsafe_retry:
                    duplicate = True
                elif committed:
                    failure = "ambiguous_unverified"
                    break

            can_retry = attempt < policy.max_retries and failure in policy.retry_on
            if can_retry:
                if failure == "ambiguous_commit" and not step.idempotent and not policy.verify_ambiguous and not policy.unsafe_retry:
                    break
                retries += 1
                latency += policy.backoff_ms * (policy.backoff_multiplier**attempt)
                budget = budget_reason()
                if budget:
                    return RunResult(run_id, False, False, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, step.name, budget, tuple(injected))
                continue
            break

        if not step_succeeded and policy.enable_fallback and step.fallback is not None:
            fallbacks += 1
            cost += step.fallback.cost_usd
            latency += step.fallback.latency_ms
            budget = budget_reason()
            if budget:
                return RunResult(run_id, False, False, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, step.name, budget, tuple(injected))
            step_succeeded = _uniform(seed, run_id, step.name, 0, "fallback") < step.fallback.success_probability
            failure = "fallback_failed" if not step_succeeded else "fallback_success"

        if not step_succeeded:
            if step.critical:
                return RunResult(run_id, False, False, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, step.name, failure, tuple(injected))
            degraded = True

    safe_success = not duplicate
    return RunResult(run_id, True, safe_success, degraded, duplicate, cost, latency, attempts, retries, verifications, fallbacks, None, "success", tuple(injected))


def simulate(scenario: Scenario, policy: Policy, *, runs: int = 1000, seed: int = 7) -> list[RunResult]:
    if runs <= 0:
        raise ValueError("runs must be positive")
    return [simulate_run(scenario, policy, run_id=run_id, seed=seed) for run_id in range(runs)]


def results_as_dicts(results: Iterable[RunResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
