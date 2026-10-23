"""Score replies collected in Try models (adapters have no callable model id) with the same grader.

  uv run python scripts/score_try.py --arm fixed --replies try_fixed.json
  replies file: [{"company": "01123229", "reply": "{...}", "ms": 900}, ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reader import splits  # noqa: E402
from reader.extract import Reply, _as_int  # noqa: E402
from reader.score import score, summary  # noqa: E402
from reader.tags import FIELDS, gold  # noqa: E402

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def values(reply: str) -> dict[str, int | None]:
    try:
        data = json.loads(FENCE.sub("", reply.strip()))
    except json.JSONDecodeError:
        data = {}
    return {f: _as_int(data.get(f)) if isinstance(data, dict) else None for f in FIELDS}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["control", "fixed"])
    ap.add_argument("--replies", required=True, type=Path)
    a = ap.parse_args()
    got = {r["company"]: r for r in json.loads(a.replies.read_text(encoding="utf-8"))}
    filings = [f for f in splits.load("held_out") if f.company in got]
    missing = set(got) - {f.company for f in filings}
    if missing:
        sys.exit(f"not in held_out: {sorted(missing)[:3]}; replies must come from held-out filings")
    rows = []
    for f in filings:
        r = got[f.company]
        reply = Reply(values(r["reply"]), "try-models", int(r.get("ms", 0)), 0, 0)
        rows += score(f.company, a.arm, reply, gold(f.html()))
    out = Path("data/runs") / f"held_out__{a.arm}__adapter.jsonl"
    out.write_text("".join(json.dumps(r.as_dict()) + "\n" for r in rows))
    print(json.dumps({"arm": a.arm, "out": str(out), **summary(rows)}))


if __name__ == "__main__":
    main()
