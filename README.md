# Agent Chaos Lab

A deterministic, zero-key chaos simulator for tool-using AI agents.

It answers questions that ordinary “task completed” benchmarks miss:

- What happens when a tool times out, rate-limits, changes schema, or returns only half a result?
- Does retry improve task success while quietly duplicating a side effect?
- Is verify-before-retry worth its cost and latency?
- Will fallback and exponential backoff remain inside the workflow budget?
- What is the chance that **all** of several repeated executions succeed?

No model, API, network call, framework, telemetry, or runtime dependency is required. Python 3.11+ is enough.

> This project simulates recovery policies. It is not a live proxy, an official benchmark implementation, or proof that a real operation is safe.

## Highlights

- Six built-in fault types: timeout, rate limit, transient failure, partial response, schema drift, and ambiguous commit.
- Bounded retries with fixed or exponential backoff.
- Separate modeling for idempotent and non-idempotent steps.
- Verify-before-retry for non-atomic failures.
- Per-step fallback paths and non-critical degradation.
- Workflow cost and latency budgets.
- Success, **safe success**, duplicate-side-effect rate, cost, P95 latency, attempts, fallbacks, and `pass^k` consistency.
- Common random numbers: the same step/attempt receives the same injected draw under every policy.
- Paired-bootstrap intervals for policy deltas.
- Self-contained offline HTML report with no JavaScript or external assets.

## Quick start

```powershell
git clone https://github.com/MikeJack302/agent-chaos-lab.git
cd agent-chaos-lab
python -m pip install -e .
```

Inspect recovery-policy hazards:

```powershell
python -m agentchaos lint examples/research-agent.json examples/policies.json
```

Run the included experiment:

```powershell
python -m agentchaos run `
  examples/research-agent.json `
  examples/policies.json `
  --runs 5000 `
  --bootstrap-samples 2000 `
  -o agent-chaos-report.html `
  --json-output experiment.out.json

Start-Process .\agent-chaos-report.html
```

Every command is also installed as `agent-chaos ...`.

## Scenario format

A scenario is a sequential workflow. Each step defines normal cost/latency and a mutually exclusive fault distribution:

```json
{
  "name": "checkout-agent",
  "steps": [
    {
      "name": "charge_card",
      "cost_usd": 0.001,
      "latency_ms": 300,
      "latency_jitter": 0.2,
      "critical": true,
      "idempotent": false,
      "faults": {
        "timeout": 0.03,
        "ambiguous_commit": 0.02
      },
      "ambiguous_commit_probability": 0.7,
      "verification": {
        "cost_usd": 0.0001,
        "latency_ms": 80
      },
      "fallback": {
        "success_probability": 0.95,
        "cost_usd": 0.002,
        "latency_ms": 500
      }
    }
  ]
}
```

Fault probabilities must be in `[0, 1]` and sum to at most 1 per step. The remaining probability is success.

`latency_jitter: 0.2` samples uniformly from 80% to 120% of base latency. Every attempt incurs the step cost. Backoff incurs latency but no provider cost. A cascade of actual services may behave differently; use measurements that match your architecture.

### Ambiguous commit

`ambiguous_commit` represents a non-atomic failure: the client did not receive a successful response, but the side effect may already have happened. Examples include a timed-out payment, sent email, or database write.

- An idempotent step may be retried without duplicating the effect.
- A non-idempotent step with `verify_ambiguous` pays the verification cost and treats a confirmed commit as success.
- A non-idempotent step with `unsafe_retry` may continue but records a possible duplicate side effect.
- Otherwise the simulator stops rather than pretending the retry is safe.

The verification model assumes an authoritative postcondition check. Real verification can itself be stale, partial, or unavailable; model that explicitly before relying on the result.

## Policy format

The first policy is the comparison baseline:

```json
{
  "policies": [
    {
      "name": "verified-bounded",
      "max_retries": 2,
      "retry_on": ["timeout", "rate_limit", "transient", "partial_response", "schema_drift", "ambiguous_commit"],
      "backoff_ms": 80,
      "backoff_multiplier": 2,
      "verify_ambiguous": true,
      "unsafe_retry": false,
      "enable_fallback": true,
      "max_cost_usd": 0.015,
      "max_latency_ms": 5000
    }
  ]
}
```

The static linter flags suspicious combinations, including blind retries of ambiguous non-idempotent operations. Warnings are design-review prompts; the simulator cannot know whether a real API honors its idempotency promise.

## Metrics that distinguish “worked” from “worked safely”

- **Success rate**: every critical step completed; non-critical failures may degrade the result.
- **Safe success rate**: success without a possible duplicated side effect.
- **Degraded rate**: at least one non-critical step failed.
- **pass^k all succeed**: `success_rate ** k`, the estimated chance that all `k` independent repeated executions succeed.
- **safe pass^k**: the same calculation using safe success.
- **P95 latency/cost**: linearly interpolated empirical percentiles.

The independence assumption behind `pass^k` is optimistic during shared outages. Time-correlated failures require a richer scenario or production replay.

## Fair policy comparisons

For a given `seed`, `run_id`, step, attempt, and purpose, a SHA-256-derived draw is fixed. A retry policy does not get an easier first attempt simply because it consumes random numbers differently. This common-random-number design enables paired per-run comparisons and typically reduces comparison noise.

The report labels a candidate “better” only when its entire 95% paired-bootstrap interval lies on the favorable side of zero. Higher safe success is favorable; lower cost, latency, and attempts are favorable.

## Why this is timely

ReliabilityBench argues that single-run task success misses consistency, perturbation robustness, and controlled fault tolerance, including timeout, rate limit, partial response, and schema-drift stress. Recent work on non-atomic failures highlights postcondition verification, verify-before-retry, and idempotency keys. OpenTelemetry’s GenAI guidance also emphasizes tracing model and tool operations so latency, retries, and token/cost regressions are observable.

Primary references:

- [ReliabilityBench: production-like agent stress](https://arxiv.org/abs/2601.06112)
- [Verified tool calls under non-atomic failures](https://arxiv.org/abs/2608.02645)
- [Towards a Science of AI Agent Reliability](https://arxiv.org/abs/2602.16666)
- [OpenTelemetry GenAI observability](https://opentelemetry.io/blog/2026/genai-observability/)
- [ITBench for real-world IT automation agents](https://proceedings.mlr.press/v267/jha25a.html)

## Test on Windows and WSL/Linux

```powershell
python -m unittest discover -s tests -v
```

```bash
python3 -m unittest discover -s tests -v
```

GitHub Actions runs Python 3.11 and 3.13 on both Windows and Ubuntu.

## License

MIT
