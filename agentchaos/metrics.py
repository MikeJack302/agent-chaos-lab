"""Reliability metrics and paired policy comparison."""

from __future__ import annotations

from collections import Counter
import math
import random
from statistics import mean, median
from typing import Any, Iterable

from .sim import RunResult


def percentile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def summarize(results: Iterable[RunResult], *, pass_k: Iterable[int] = (1, 3, 5)) -> dict[str, Any]:
    items = list(results)
    if not items:
        raise ValueError("at least one run is required")
    success_rate = mean(item.success for item in items)
    safe_success_rate = mean(item.safe_success for item in items)
    reasons = Counter(item.terminal_reason for item in items if not item.success)
    faults = Counter(fault.split(":", 1)[1] for item in items for fault in item.injected_faults)
    return {
        "runs": len(items),
        "success_rate": success_rate,
        "safe_success_rate": safe_success_rate,
        "degraded_rate": mean(item.degraded for item in items),
        "duplicate_side_effect_rate": mean(item.duplicate_side_effect for item in items),
        "mean_cost_usd": mean(item.cost_usd for item in items),
        "p95_cost_usd": percentile((item.cost_usd for item in items), 0.95),
        "mean_latency_ms": mean(item.latency_ms for item in items),
        "median_latency_ms": median(item.latency_ms for item in items),
        "p95_latency_ms": percentile((item.latency_ms for item in items), 0.95),
        "mean_attempts": mean(item.attempts for item in items),
        "mean_retries": mean(item.retries for item in items),
        "verification_rate": mean(item.verifications > 0 for item in items),
        "fallback_rate": mean(item.fallbacks > 0 for item in items),
        "pass_k_all_succeed": {str(k): success_rate**k for k in pass_k},
        "safe_pass_k_all_succeed": {str(k): safe_success_rate**k for k in pass_k},
        "terminal_failures": dict(sorted(reasons.items())),
        "injected_faults": dict(sorted(faults.items())),
    }


def paired_bootstrap(
    candidate: Iterable[RunResult],
    baseline: Iterable[RunResult],
    *,
    samples: int = 2000,
    seed: int = 19,
) -> dict[str, Any]:
    candidate_by_id = {item.run_id: item for item in candidate}
    baseline_by_id = {item.run_id: item for item in baseline}
    ids = sorted(candidate_by_id.keys() & baseline_by_id.keys())
    if not ids or len(ids) != len(candidate_by_id) or len(ids) != len(baseline_by_id):
        raise ValueError("candidate and baseline must use the same non-empty run IDs")
    if samples <= 0:
        raise ValueError("samples must be positive")
    fields = {
        "safe_success": (lambda item: float(item.safe_success), False),
        "cost_usd": (lambda item: item.cost_usd, True),
        "latency_ms": (lambda item: item.latency_ms, True),
        "attempts": (lambda item: float(item.attempts), True),
    }
    rng = random.Random(seed)
    deltas: dict[str, Any] = {}
    for name, (extract, lower_is_better) in fields.items():
        differences = [extract(candidate_by_id[index]) - extract(baseline_by_id[index]) for index in ids]
        estimates = sorted(mean(rng.choice(differences) for _ in ids) for _ in range(samples))
        low, high = percentile(estimates, 0.025), percentile(estimates, 0.975)
        deltas[name] = {
            "mean_delta": mean(differences),
            "ci95_low": low,
            "ci95_high": high,
            "likely_better": high < 0 if lower_is_better else low > 0,
            "likely_worse": low > 0 if lower_is_better else high < 0,
        }
    return {"runs": len(ids), "samples": samples, "seed": seed, "deltas": deltas}
