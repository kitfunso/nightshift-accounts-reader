"""Build docs/scoreboard.html from data/runs/held_out__*.jsonl. One column per arm, same filings.

  uv run python scripts/scoreboard.py
"""
from __future__ import annotations

import html
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reader.score import Row, interval  # noqa: E402

ARMS = [("provider", "gpt-4o-mini"), ("provider_rule", "gpt-4o-mini + rule"),
        ("control", "Control adapter, no rule"), ("fixed", "Fixed adapter, no rule")]
ERRORS = ["missing", "sign", "prior_year", "wrong_line", "other"]


def load(arm: str) -> list[Row]:
    hits = sorted(Path("data/runs").glob(f"held_out__{arm}__*.jsonl"))
    if not hits:
        return []
    return [Row(**json.loads(line)) for line in hits[-1].read_text().splitlines() if line]


def cell(rows: list[Row], pick) -> str:
    sub = [r for r in rows if pick(r)]
    if not sub:
        return "<td class=dim>n/a</td>"
    right = sum(r.error == "right" for r in sub)
    return f"<td>{right / len(sub):.1%}<small>{right}/{len(sub)}</small></td>"


def table(data: dict[str, list[Row]], shown: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in shown)
    body = []
    total = []
    for arm, _ in shown:
        rows = data[arm]
        lo, hi = interval(rows)
        right = sum(r.error == "right" for r in rows) / len(rows)
        total.append(f"<td><b>{right:.1%}</b><small>95% CI {lo:.1%} to {hi:.1%}</small></td>")
    body.append("<tr class=total><th>All fields</th>" + "".join(total) + "</tr>")
    body.append("<tr><th>Negative figures</th>" + "".join(cell(data[a], lambda r: r.tag < 0) for a, _ in shown) + "</tr>")
    for f in ["net_assets", "net_current_assets", "total_assets_less_current_liabilities", "current_assets", "employees"]:
        body.append(f"<tr><th>{f.replace('_', ' ')}</th>" + "".join(cell(data[a], lambda r, f=f: r.field == f) for a, _ in shown) + "</tr>")
    for e in ERRORS:
        counts = [Counter(r.error for r in data[a])[e] for a, _ in shown]
        body.append(f"<tr class=err><th>errors: {e.replace('_', ' ')}</th>" + "".join(f"<td>{c}</td>" for c in counts) + "</tr>")
    ms = [f"<td>{statistics.median(r.ms for r in data[a]):,.0f} ms</td>" for a, _ in shown]
    body.append("<tr class=dim><th>median response</th>" + "".join(ms) + "</tr>")
    return f"<table><thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def main() -> None:
    data = {arm: load(arm) for arm, _ in ARMS}
    shown = [(arm, label) for arm, label in ARMS if data[arm]]
    providers = [(a, lbl) for a, lbl in shown if a.startswith("provider")]
    n_all = len({r.company for a, _ in providers for r in data[a]})
    sections = []
    if len(shown) > len(providers):
        # adapters run in Try models on a subset, so compare every arm on the filings all of them saw
        common = set.intersection(*({r.company for r in data[a]} for a, _ in shown))
        same = {a: [r for r in data[a] if r.company in common] for a, _ in shown}
        sections.append(f"<h2>Every arm on the same {len(common)} filings</h2>" + table(same, shown))
    sections.append(f"<h2>Provider arms on all {n_all} held-out filings</h2>" + table(data, providers))
    page = f"""<!doctype html><meta charset=utf-8><title>Accounts reader scoreboard</title>
<style>
body{{font:15px/1.45 system-ui,sans-serif;margin:32px;color:#1d2330;background:#f7f8fa}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:24px 0 8px}} p{{margin:0 0 18px;color:#5b6475}}
table{{border-collapse:collapse;background:#fff;border:1px solid #dde2ea}}
th,td{{padding:8px 14px;border-bottom:1px solid #eef1f5;text-align:right;vertical-align:top}}
th:first-child{{text-align:left;font-weight:500}} thead th{{background:#f0f3f7;font-weight:600}}
td small{{display:block;color:#8a93a3;font-size:12px}} tr.total td b{{font-size:18px}}
tr.err th,tr.err td{{color:#9a3412}} .dim{{color:#8a93a3}}
</style>
<h1>Accounts reader: held-out scoreboard</h1>
<p>UK filings never used for training or for writing the rule. Graded against the filer's own iXBRL tags; tags that contradict the printed page are excluded.</p>
{''.join(sections)}"""
    out = Path("docs/scoreboard.html")
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": str(out), "arms": [a for a, _ in shown], "filings": n_all}))


if __name__ == "__main__":
    main()
