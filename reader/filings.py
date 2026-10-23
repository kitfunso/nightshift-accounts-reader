"""Companies House daily accounts zips, read in place without unpacking."""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

NAME = re.compile(r"Prod\d+_\d+_([A-Z0-9]{8})_(\d{8})\.html$")


@dataclass(frozen=True)
class Filing:
    company: str
    period_end: str
    member: str
    zip_path: Path

    def html(self) -> bytes:
        with zipfile.ZipFile(self.zip_path) as z:
            return z.read(self.member)


def list_filings(zip_path: Path) -> list[Filing]:
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    out = []
    for m in names:
        hit = NAME.search(m)
        if hit:
            out.append(Filing(hit.group(1), hit.group(2), m, zip_path))
    return sorted(out, key=lambda f: f.member)
