"""Standalone HTML reliability report."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any


def _card(label: str, value: str) -> str:
    return f'<div class="card"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def render_html(result: dict[str, Any], *, title: str = "Agent Chaos Lab") -> str:
    policies = result["policies"]
    best_name = max(policies, key=lambda name: policies[name]["metrics"]["safe_success_rate"])
    best = policies[best_name]["metrics"]
    cards = "".join(
        [
            _card("Scenario", str(result["scenario"])),
            _card("Runs per policy", f"{result['runs']:,}"),
            _card("Best safe success", f"{best['safe_success_rate']:.2%}"),
            _card("Best policy", best_name),
            _card("Best P95 latency", f"{best['p95_latency_ms']:.0f} ms"),
            _card("Best mean cost", f"${best['mean_cost_usd']:.6f}"),
        ]
    )
    rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{entry['metrics']['success_rate']:.2%}</td>"
        f"<td>{entry['metrics']['safe_success_rate']:.2%}</td>"
        f"<td>{entry['metrics']['duplicate_side_effect_rate']:.2%}</td>"
        f"<td>${entry['metrics']['mean_cost_usd']:.6f}</td>"
        f"<td>{entry['metrics']['p95_latency_ms']:.0f}</td>"
        f"<td>{entry['metrics']['mean_attempts']:.2f}</td></tr>"
        for name, entry in policies.items()
    )
    warning_items = "".join(
        f"<li><b>{escape(name)}</b>: {escape(warning)}</li>"
        for name, entry in policies.items()
        for warning in entry["warnings"]
    ) or "<li>No static policy warning.</li>"
    comparisons = []
    for name, entry in policies.items():
        comparison = entry["vs_baseline"]
        if comparison is None:
            continue
        for metric, values in comparison["deltas"].items():
            direction = "better" if values["likely_better"] else "worse" if values["likely_worse"] else "uncertain"
            comparisons.append(
                f"<tr><td>{escape(name)}</td><td>{escape(metric)}</td><td>{values['mean_delta']:+.6f}</td>"
                f"<td>[{values['ci95_low']:+.6f}, {values['ci95_high']:+.6f}]</td><td>{direction}</td></tr>"
            )
    failure_sections = []
    for name, entry in policies.items():
        metrics = entry["metrics"]
        failures = "".join(
            f"<li><code>{escape(reason)}</code>: {count}</li>"
            for reason, count in metrics["terminal_failures"].items()
        ) or "<li>No terminal failure.</li>"
        pass_k = " · ".join(f"pass^{k}={value:.2%}" for k, value in metrics["safe_pass_k_all_succeed"].items())
        failure_sections.append(f"<div class='failure'><h3>{escape(name)}</h3><p>{pass_k}</p><ul>{failures}</ul></div>")
    embedded = escape(json.dumps(result, ensure_ascii=False), quote=True)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--bg:#0e0c15;--panel:#191525;--line:#392e4b;--text:#fff5e9;--muted:#b9a9c7;--pink:#ff6fae;--green:#71e6a5}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 20% 0,#321b3d,#0e0c15 48%);color:var(--text);font:14px/1.5 ui-sans-serif,system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:42px 20px}} h1{{font-size:35px;margin:0}} .sub{{color:var(--muted);margin:5px 0 24px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}} .card,section{{border:1px solid var(--line);background:rgba(25,21,37,.94);border-radius:14px}}
.card{{padding:16px}} .card span{{display:block;color:var(--muted)}} .card strong{{font-size:21px}} section{{margin-top:18px;padding:20px;overflow:auto}} h2{{margin:0 0 14px}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}} th{{color:var(--muted)}} code{{color:var(--pink)}}
.failures{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}} .failure{{padding:14px;border:1px solid var(--line);border-radius:10px}} .failure h3{{margin:0}} .failure p{{color:var(--green)}}
</style></head><body><main><h1>{escape(title)}</h1><p class="sub">Deterministic offline injection · seed {result['seed']} · paired against <code>{escape(result['baseline'])}</code></p>
<div class="cards">{cards}</div>
<section><h2>Policy scorecard</h2><table><thead><tr><th>Policy</th><th>Success</th><th>Safe success</th><th>Duplicate side effect</th><th>Mean cost</th><th>P95 latency</th><th>Attempts</th></tr></thead><tbody>{rows}</tbody></table></section>
<section><h2>Static warnings</h2><ul>{warning_items}</ul></section>
<section><h2>Paired bootstrap versus baseline</h2><table><thead><tr><th>Policy</th><th>Metric</th><th>Mean delta</th><th>95% interval</th><th>Direction</th></tr></thead><tbody>{''.join(comparisons)}</tbody></table></section>
<section><h2>Consistency and terminal failures</h2><div class="failures">{''.join(failure_sections)}</div></section>
<span data-result="{embedded}"></span></main></body></html>"""


def write_html(result: dict[str, Any], output: str | Path, *, title: str = "Agent Chaos Lab") -> Path:
    target = Path(output)
    target.write_text(render_html(result, title=title), encoding="utf-8")
    return target
