"""What the model sees: the filing's visible text, with every iXBRL tag and the hidden header removed."""
from __future__ import annotations

import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

LIMIT = 16_000  # p90 of 300 filings on 2026-10-23 was 12,120 chars


def plain_text(html: bytes, limit: int = LIMIT) -> str:
    soup = BeautifulSoup(html, "lxml")
    # ix:header holds contexts and hidden facts; leaving it in leaks concept names and dates
    for tag in soup.find_all(["ix:header", "script", "style", "title"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:limit]
