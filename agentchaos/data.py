"""Scenario and recovery-policy configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


FAULTS = (
    "timeout",
    "rate_limit",
    "transient",
    "partial_response",
    "schema_drift",
    "ambiguous_commit",
)


@dataclass(frozen=True)
class Fallback:
    success_probability: float
    cost_usd: float
    latency_ms: float


@dataclass(frozen=True)
class Verification:
    cost_usd: float
    latency_ms: float


@dataclass(frozen=True)
class Step:
    name: str
    cost_usd: float
    latency_ms: float
    latency_jitter: float
    critical: bool
    idempotent: bool
    faults: dict[str, float] = field(default_factory=dict)
    ambiguous_commit_probability: float = 0.5
    verification: Verification | None = None
    fallback: Fallback | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Policy:
    name: str
    max_retries: int
    retry_on: frozenset[str]
    backoff_ms: float
    backoff_multiplier: float
    verify_ambiguous: bool
    unsafe_retry: bool
    enable_fallback: bool
    max_cost_usd: float | None
    max_latency_ms: float | None


def _number(value: Any, path: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a number")
    parsed = float(value)
    if parsed != parsed or parsed in (float("inf"), float("-inf")) or parsed < minimum:
        raise ValueError(f"{path} must be finite and at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{path} must be at most {maximum}")
    return parsed


def _load(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def load_scenario(path: str | Path) -> Scenario:
    value = _load(path)
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or not isinstance(value.get("steps"), list):
        raise ValueError("scenario requires a name and steps array")
    steps: list[Step] = []
    names: set[str] = set()
    for index, raw in enumerate(value["steps"]):
        prefix = f"steps[{index}]"
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            raise ValueError(f"{prefix}.name is required")
        if raw["name"] in names:
            raise ValueError(f"{prefix}.name duplicates {raw['name']!r}")
        names.add(raw["name"])
        faults = raw.get("faults", {})
        if not isinstance(faults, dict) or any(name not in FAULTS for name in faults):
            raise ValueError(f"{prefix}.faults contains an unsupported fault")
        parsed_faults = {
            name: _number(probability, f"{prefix}.faults.{name}", maximum=1)
            for name, probability in faults.items()
        }
        if sum(parsed_faults.values()) > 1:
            raise ValueError(f"{prefix}.fault probabilities must sum to at most 1")
        fallback = raw.get("fallback")
        parsed_fallback = None
        if fallback is not None:
            if not isinstance(fallback, dict):
                raise ValueError(f"{prefix}.fallback must be an object")
            parsed_fallback = Fallback(
                success_probability=_number(fallback.get("success_probability"), f"{prefix}.fallback.success_probability", maximum=1),
                cost_usd=_number(fallback.get("cost_usd"), f"{prefix}.fallback.cost_usd"),
                latency_ms=_number(fallback.get("latency_ms"), f"{prefix}.fallback.latency_ms"),
            )
        verification = raw.get("verification")
        parsed_verification = None
        if verification is not None:
            if not isinstance(verification, dict):
                raise ValueError(f"{prefix}.verification must be an object")
            parsed_verification = Verification(
                cost_usd=_number(verification.get("cost_usd"), f"{prefix}.verification.cost_usd"),
                latency_ms=_number(verification.get("latency_ms"), f"{prefix}.verification.latency_ms"),
            )
        steps.append(
            Step(
                name=raw["name"],
                cost_usd=_number(raw.get("cost_usd"), f"{prefix}.cost_usd"),
                latency_ms=_number(raw.get("latency_ms"), f"{prefix}.latency_ms"),
                latency_jitter=_number(raw.get("latency_jitter", 0), f"{prefix}.latency_jitter", maximum=1),
                critical=bool(raw.get("critical", True)),
                idempotent=bool(raw.get("idempotent", True)),
                faults=parsed_faults,
                ambiguous_commit_probability=_number(
                    raw.get("ambiguous_commit_probability", 0.5),
                    f"{prefix}.ambiguous_commit_probability",
                    maximum=1,
                ),
                verification=parsed_verification,
                fallback=parsed_fallback,
            )
        )
    if not steps:
        raise ValueError("scenario must contain at least one step")
    return Scenario(value["name"], tuple(steps))


def parse_policy(value: Any, index: int = 0) -> Policy:
    prefix = f"policies[{index}]"
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        raise ValueError(f"{prefix}.name is required")
    max_retries = value.get("max_retries", 0)
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0 or max_retries > 20:
        raise ValueError(f"{prefix}.max_retries must be an integer between 0 and 20")
    retry_on = value.get("retry_on", [])
    if not isinstance(retry_on, list) or any(name not in FAULTS for name in retry_on):
        raise ValueError(f"{prefix}.retry_on contains an unsupported fault")
    max_cost = value.get("max_cost_usd")
    max_latency = value.get("max_latency_ms")
    return Policy(
        name=value["name"],
        max_retries=max_retries,
        retry_on=frozenset(retry_on),
        backoff_ms=_number(value.get("backoff_ms", 0), f"{prefix}.backoff_ms"),
        backoff_multiplier=_number(value.get("backoff_multiplier", 1), f"{prefix}.backoff_multiplier", minimum=1),
        verify_ambiguous=bool(value.get("verify_ambiguous", False)),
        unsafe_retry=bool(value.get("unsafe_retry", False)),
        enable_fallback=bool(value.get("enable_fallback", False)),
        max_cost_usd=None if max_cost is None else _number(max_cost, f"{prefix}.max_cost_usd"),
        max_latency_ms=None if max_latency is None else _number(max_latency, f"{prefix}.max_latency_ms"),
    )


def load_policies(path: str | Path) -> list[Policy]:
    value = _load(path)
    raw_policies = value.get("policies") if isinstance(value, dict) else value
    if not isinstance(raw_policies, list) or not raw_policies:
        raise ValueError("expected a non-empty policies array")
    policies = [parse_policy(raw, index) for index, raw in enumerate(raw_policies)]
    names = [policy.name for policy in policies]
    if len(set(names)) != len(names):
        raise ValueError("policy names must be unique")
    return policies


def lint_policy(scenario: Scenario, policy: Policy) -> list[str]:
    warnings = []
    if policy.max_retries and not policy.retry_on:
        warnings.append("max_retries is non-zero but retry_on is empty")
    for step in scenario.steps:
        if "ambiguous_commit" in step.faults and not step.idempotent:
            if policy.unsafe_retry and not policy.verify_ambiguous:
                warnings.append(f"{step.name}: unsafe retry can duplicate a non-idempotent side effect")
            if policy.verify_ambiguous and step.verification is None:
                warnings.append(f"{step.name}: policy requests verification but the step defines none")
        if policy.enable_fallback and step.fallback is None:
            warnings.append(f"{step.name}: fallback is enabled but this step defines none")
    return warnings
