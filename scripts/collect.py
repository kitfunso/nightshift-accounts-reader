"""Send collect-split filings to one Mubit task with recording on, so they become training rows.

  fixed:   SYSTEM, rule before the filing in the user message
  control: SYSTEM_CONTROL (one word differs), no rule

  uv run python scripts/collect.py --task fixed --start 0 --n 120
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reader import splits  # noqa: E402
from reader.extract import SYSTEM, SYSTEM_CONTROL, extract  # noqa: E402
from reader.score import score, summary  # noqa: E402
from reader.tags import gold  # noqa: E402
from reader.text import plain_text  # noqa: E402

MODEL = "gpt-4o-mini"
RULE = Path("rules/negatives.txt")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["fixed", "control"])
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    s = json.loads(splits.SPLITS.read_text())
    blocked = set(s["dev"]) | set(s["held_out"])
    filings = splits.load("collect")[a.start:a.start + a.n]
    leaked = [f.member for f in filings if f.member in blocked]
    if leaked:
        sys.exit(f"refusing: {len(leaked)} collect filings are in dev or held_out, e.g. {leaked[0]}")

    system = SYSTEM if a.task == "fixed" else SYSTEM_CONTROL
    prefix = RULE.read_text(encoding="utf-8").strip() + "\n\n" if a.task == "fixed" else ""

    def one(f):
        html = f.html()
        r = extract(f.company, prefix + plain_text(html), MODEL, system=system, store=True)
        return score(f.company, f"collect_{a.task}", r, gold(html))

    with ThreadPoolExecutor(a.workers) as ex:
        rows = [row for rs in ex.map(one, filings) for row in rs]
    out = Path("data/runs") / f"collect__{a.task}__{a.start}-{a.start + len(filings)}.jsonl"
    out.write_text("".join(json.dumps(r.as_dict()) + "\n" for r in rows))
    print(json.dumps({"task": a.task, "sent": len(filings), "out": str(out), **summary(rows)}))


if __name__ == "__main__":
    main()
