"""Grade replies against the tags: one row per field, each wrong field given one error type."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import asdict, dataclass

from reader.extract import Reply
from reader.tags import Gold


@dataclass(frozen=True)
class Row:
    company: str
    arm: str  # provider | provider_rule | control | fixed
    field: str
    got: int | None
    tag: int
    prior: int | None
    error: str  # right | prior_year | sign | wrong_line | missing | other
    mreq: str
    ms: int
    tokens_in: int
    tokens_out: int

    def as_dict(self) -> dict:
        return asdict(self)


def error_type(got: int | None, tag: int, prior: int | None, other_tags: set[int]) -> str:
    if got == tag:
        return "right"
    if got is None:
        return "missing"
    if prior is not None and got == prior:
        return "prior_year"
    if got == -tag:
        return "sign"
    if got in other_tags:
        return "wrong_line"
    return "other"


def score(company: str, arm: str, reply: Reply, gold: Gold) -> list[Row]:
    rows = []
    for field, tag in gold.current.items():
        if tag is None or field in gold.disputed:
            continue
        others = {v for f, v in gold.current.items() if f != field and v is not None and v != tag}
        got = reply.values.get(field)
        rows.append(Row(company, arm, field, got, tag, gold.prior.get(field),
                        error_type(got, tag, gold.prior.get(field), others),
                        reply.mreq, reply.ms, reply.tokens_in, reply.tokens_out))
    return rows


def summary(rows: list[Row]) -> dict:
    n = len(rows)
    errs = Counter(r.error for r in rows if r.error != "right")
    by_field = {}
    for f in sorted({r.field for r in rows}):
        fr = [r for r in rows if r.field == f]
        by_field[f] = round(sum(r.error == "right" for r in fr) / len(fr), 3)
    lo, hi = interval(rows)
    return {"fields": n, "filings": len({r.company for r in rows}),
            "right": round(sum(r.error == "right" for r in rows) / n, 3) if n else None,
            "ci95": [lo, hi], "errors": dict(errs.most_common()), "by_field": by_field}


def interval(rows: list[Row], n: int = 2000, seed: int = 7) -> tuple[float, float]:
    """95% bootstrap interval on share right, resampling filings (fields within a filing correlate)."""
    by_co: dict[str, list[int]] = {}
    for r in rows:
        by_co.setdefault(r.company, []).append(int(r.error == "right"))
    cos = list(by_co)
    if not cos:
        return (0.0, 0.0)
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        pick = [by_co[rng.choice(cos)] for _ in cos]
        stats.append(sum(map(sum, pick)) / sum(map(len, pick)))
    stats.sort()
    return (round(stats[int(0.025 * n)], 3), round(stats[int(0.975 * n)], 3))
