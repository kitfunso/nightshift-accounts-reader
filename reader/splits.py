"""Fixed dev / held-out / collect splits, written once so no run can move a filing between them."""
from __future__ import annotations

import json
import random
from pathlib import Path

from reader.filings import Filing, list_filings
from reader.tags import gold

SPLITS = Path("data/splits.json")
SIZES = {"dev": 50, "held_out": 100, "collect": 400}


def make_splits(zip_path: Path, seed: int = 23) -> dict[str, list[str]]:
    """Members with at least 4 of 5 fields tagged, shuffled once, cut into the three sets."""
    if SPLITS.exists():
        return json.loads(SPLITS.read_text())
    fs = list_filings(zip_path)
    random.Random(seed).shuffle(fs)
    need = sum(SIZES.values())
    picked: list[str] = []
    for f in fs:
        if gold(f.html()).known() >= 4:
            picked.append(f.member)
        if len(picked) == need:
            break
    out, i = {}, 0
    for name, size in SIZES.items():
        out[name] = picked[i:i + size]
        i += size
    out["zip"] = str(zip_path)
    SPLITS.write_text(json.dumps(out, indent=1))
    return out


def load(name: str) -> list[Filing]:
    s = json.loads(SPLITS.read_text())
    zp = Path(s["zip"])
    want = set(s[name])
    return [f for f in list_filings(zp) if f.member in want]
