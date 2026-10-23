"""One call through Mubit: filing text in, the five figures out as JSON."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

from reader.tags import FIELDS

load_dotenv()
log = logging.getLogger(__name__)

# Mubit makes a task from system prompt + model + format: never edit this text mid-run.
SYSTEM = (
    "Read the UK company accounts below. Return one JSON object with exactly these keys: "
    + ", ".join(FIELDS)
    + ". Each value is a whole number in pounds, except employees, which is a head count. "
    "Use null if the accounts do not show the figure."
)

_client = OpenAI(base_url="https://api.mubit.ai/openai/v1", api_key=os.environ["MUBIT_API_KEY"])


@dataclass(frozen=True)
class Reply:
    values: dict[str, int | None]
    mreq: str
    ms: int
    tokens_in: int
    tokens_out: int


def _as_int(v: object) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(round(float(str(v).replace(",", "").replace("£", "").strip())))
    except ValueError:
        return None


def extract(company: str, text: str, model: str, *, system: str = SYSTEM,
            store: bool = False, retries: int = 4) -> Reply:
    # store=False keeps the call out of Mubit's training rows; only collection runs store
    headers = {} if store else {"x-middleware-store": "false"}
    for attempt in range(retries):
        t0 = time.perf_counter()
        try:
            raw = _client.chat.completions.with_raw_response.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                # no metadata.session_id: OpenAI refuses metadata unless it stores the call;
                # Mubit sessions each call by its first user message, which is one filing
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": text}],
                extra_headers=headers,
            )
        except APIStatusError as e:
            if e.status_code in (429, 502, 503, 504) and attempt < retries - 1:
                wait = float(e.response.headers.get("retry-after", 2 ** attempt))
                log.warning("company=%s status=%s retry_in=%.1fs", company, e.status_code, wait)
                time.sleep(wait)
                continue
            raise
        ms = int((time.perf_counter() - t0) * 1000)
        resp = raw.parse()
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            data = {}
        return Reply(
            values={f: _as_int(data.get(f)) for f in FIELDS},
            mreq=raw.headers.get("x-middleware-request-id", ""),
            ms=ms,
            tokens_in=resp.usage.prompt_tokens if resp.usage else 0,
            tokens_out=resp.usage.completion_tokens if resp.usage else 0,
        )
    raise RuntimeError(f"no reply for {company} after {retries} tries")
