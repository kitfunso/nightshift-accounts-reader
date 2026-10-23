"""The answer key: the filer's own iXBRL tags for the five fields, current and prior period.

A field is graded only when its tag agrees with the figure printed on the page. Tags that
contradict the page (see DISPUTES) are kept out of scoring and counted.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from ixbrlparse import IXBRL

FIELDS: dict[str, tuple[str, ...]] = {
    "net_assets": ("NetAssetsLiabilities", "Equity"),
    "net_current_assets": ("NetCurrentAssetsLiabilities",),
    "total_assets_less_current_liabilities": ("TotalAssetsLessCurrentLiabilities",),
    "current_assets": ("CurrentAssets",),
    "employees": ("AverageNumberEmployeesDuringPeriod",),
}
COUNTS = {"employees"}
# scale_on_count: page shows "2", tag says scale=-2, so the fact is 0.02 people (seen in 2026-10-23 dev set)
# unsigned_brackets: page shows "( 23,677 )", tag has no sign="-", so the fact is +23,677
DISPUTES = ("scale_on_count", "unsigned_brackets")


@dataclass(frozen=True)
class Fact:
    value: int
    dispute: str | None


@dataclass(frozen=True)
class Gold:
    period_end: str | None
    current: dict[str, int | None]
    prior: dict[str, int | None]
    disputed: dict[str, str] = field(default_factory=dict)

    def known(self) -> int:
        return sum(v is not None for f, v in self.current.items() if f not in self.disputed)


def _text(node: object) -> str:
    if node is None:
        return ""
    return node if isinstance(node, str) else node.get_text()


def _dispute(n: object, concept_field: str | None) -> str | None:
    tag = n.soup_tag
    scale = str(tag.attrs.get("scale", "0") or "0")
    if concept_field in COUNTS and scale != "0":
        return "scale_on_count"
    bracketed = _text(tag.previous_sibling).rstrip().endswith("(") and _text(tag.next_sibling).lstrip().startswith(")")
    if bracketed and tag.attrs.get("sign") != "-" and float(n.value) > 0:
        return "unsigned_brackets"
    return None


def _field_of(concept: str) -> str | None:
    return next((f for f, names in FIELDS.items() if concept in names), None)


def _facts(html: bytes) -> dict[str, dict[str, Fact]]:
    """concept local name -> {period end -> Fact}, non-dimensional facts only."""
    x = IXBRL(io.BytesIO(html))
    out: dict[str, dict[str, Fact]] = {}
    for n in x.numeric:
        c = n.context
        if c is None or c.segments or n.value is None:
            continue
        end = c.instant or c.enddate
        if end is None:
            continue
        fact = Fact(int(round(float(n.value))), _dispute(n, _field_of(n.name)))
        out.setdefault(n.name, {}).setdefault(str(end), fact)
    return out


def gold(html: bytes) -> Gold:
    facts = _facts(html)
    ends = sorted({e for by_end in facts.values() for e in by_end}, reverse=True)
    if not ends:
        return Gold(None, dict.fromkeys(FIELDS), dict.fromkeys(FIELDS))
    cur = ends[0]
    current: dict[str, int | None] = {}
    prior: dict[str, int | None] = {}
    disputed: dict[str, str] = {}
    for f, names in FIELDS.items():
        hit = next((facts[n] for n in names if n in facts and cur in facts[n]), None)
        current[f] = hit[cur].value if hit else None
        if hit and hit[cur].dispute:
            disputed[f] = hit[cur].dispute
        # per concept, because opening balances can sit one day after the prior year end
        earlier = sorted((e for e in (hit or {}) if e < cur), reverse=True)
        prior[f] = hit[earlier[0]].value if earlier else None
    return Gold(cur, current, prior, disputed)
