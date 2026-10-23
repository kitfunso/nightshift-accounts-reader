"""Run one arm on one split and print a one-line JSON summary. Rows go to data/runs/<split>__<arm>__<model>.jsonl.

  uv run python scripts/run_arm.py --split dev --arm provider --model gpt-4.1-mini
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reader import splits  # noqa: E402
from reader.extract import SYSTEM, extract  # noqa: E402
from reader.score import score, summary  # noqa: E402
from reader.tags import gold  # noqa: E402
from reader.text import plain_text  # noqa: E402

ZIP = Path("data/Accounts_Bulk_Data-2026-10-23.zip")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "held_out", "collect"])
    ap.add_argument("--arm", default="provider")
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--rule", default="", help="file whose text goes before the filing in the user message")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    splits.make_splits(ZIP)
    filings = splits.load(a.split)[: a.limit or None]
    rule = Path(a.rule).read_text(encoding="utf-8").strip() + "\n\n" if a.rule else ""

    def one(f):
        html = f.html()
        g = gold(html)
        r = extract(f.company, rule + plain_text(html), a.model, system=SYSTEM, store=False)
        return score(f.company, a.arm, r, g), g.disputed

    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(one, filings))
    rows = [row for rs, _ in results for row in rs]
    disputed = Counter(reason for _, d in results for reason in d.values())
    out = Path("data/runs") / f"{a.split}__{a.arm}__{a.model}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r.as_dict()) + "\n" for r in rows))
    print(json.dumps({"split": a.split, "arm": a.arm, "model": a.model, "out": str(out),
                      **summary(rows), "key_disputed": dict(disputed)}))


if __name__ == "__main__":
    main()
