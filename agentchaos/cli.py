"""Command-line interface for Agent Chaos Lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .data import lint_policy, load_policies, load_scenario
from .experiment import run_experiment
from .report import write_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-chaos",
        description="Replay agent recovery policies under deterministic tool faults.",
    )
    parser.add_argument("--version", action="version", version="agent-chaos-lab 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint = subparsers.add_parser("lint", help="statically inspect recovery policies")
    lint.add_argument("scenario", type=Path)
    lint.add_argument("policies", type=Path)
    lint.add_argument("--json", action="store_true")

    run = subparsers.add_parser("run", help="simulate and compare recovery policies")
    run.add_argument("scenario", type=Path)
    run.add_argument("policies", type=Path)
    run.add_argument("--runs", type=int, default=5000)
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--bootstrap-samples", type=int, default=2000)
    run.add_argument("-o", "--output", type=Path, default=Path("agent-chaos-report.html"))
    run.add_argument("--json-output", type=Path)
    run.add_argument("--title", default="Agent Chaos Lab")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        policies = load_policies(args.policies)
        if args.command == "lint":
            warnings = {policy.name: lint_policy(scenario, policy) for policy in policies}
            if args.json:
                print(json.dumps({"scenario": scenario.name, "warnings": warnings}, ensure_ascii=False, indent=2))
            else:
                for name, items in warnings.items():
                    print(f"{name}: {len(items)} warning(s)")
                    for warning in items:
                        print(f"  - {warning}")
            return 0
        result = run_experiment(
            scenario,
            policies,
            runs=args.runs,
            seed=args.seed,
            bootstrap_samples=args.bootstrap_samples,
        )
        report = write_html(result, args.output, title=args.title).resolve()
        if args.json_output:
            args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {report}")
        for name, entry in result["policies"].items():
            metrics = entry["metrics"]
            print(
                f"  {name}: safe_success={metrics['safe_success_rate']:.2%} "
                f"cost=${metrics['mean_cost_usd']:.6f} p95={metrics['p95_latency_ms']:.0f}ms"
            )
        return 0
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
