"""OpenAlex: bounded, hand-run validation snapshot.

Measures published journal and conference output in the Computer Science
field, with preprint servers EXCLUDED so this channel stays independent of
arXiv. Counts works, not citations (citations lag for recent papers).

One grouped call per concept plus one for the yearly totals, so a full
snapshot is about 51 calls: well inside the free anonymous daily allowance.
No key is required; an optional free key and a contact email are used if set.

Items to confirm in the pilot (open items in the proposal):
  * boolean OR inside title_and_abstract.search behaves as expected;
  * field id 17 is Computer Science in the OpenAlex topic taxonomy.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

import pandas as pd

from ..config import Config
from ..health import HealthLog
from ..lexicon import LEXICON
from ..store import save_table
from .http import PoliteClient, SourceUnavailable

CS_FIELD_FILTER = "primary_topic.field.id:17"
VENUE_FILTER = "primary_location.source.type:journal|conference"


def _query(aliases: List[str]) -> str:
    return " OR ".join(f'"{a}"' if " " in a or "-" in a else a for a in aliases)


def _base_filters(cfg: Config) -> List[str]:
    return [f"publication_year:{cfg.start_year}-{cfg.end_year}", VENUE_FILTER, CS_FIELD_FILTER]


def _params(cfg: Config, filters: List[str]) -> Dict[str, str]:
    p = {"filter": ",".join(filters), "group_by": "publication_year"}
    if cfg.contact_email:
        p["mailto"] = cfg.contact_email
    key = cfg.openalex_key()
    if key:
        p["api_key"] = key
    return p


def _groups(payload: dict) -> Dict[int, int]:
    out = {}
    for g in payload.get("group_by", []):
        try:
            out[int(g["key"])] = int(g["count"])
        except (KeyError, ValueError, TypeError):
            continue
    return out


def snapshot(cfg: Config, log: HealthLog, client: Optional[PoliteClient] = None,
             concepts: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
    client = client or PoliteClient(cfg.user_agent, cfg.request_timeout, 0.2,
                                    cfg.max_consecutive_failures, 1800)
    url = f"{cfg.openalex_base}/works"
    try:
        totals = _groups(client.get_json(url, _params(cfg, _base_filters(cfg))))
    except SourceUnavailable as exc:
        log.record("openalex", "unavailable", str(exc), "snapshot skipped this run", url)
        return None
    if not totals:
        log.record("openalex", "degraded", "empty totals", "snapshot skipped this run", url)
        return None

    rows, failed = [], []
    for cid in concepts or list(LEXICON):
        c = LEXICON[cid]
        filters = _base_filters(cfg) + [f"title_and_abstract.search:{_query(c['aliases'])}"]
        try:
            counts = _groups(client.get_json(url, _params(cfg, filters)))
        except SourceUnavailable as exc:
            failed.append(cid)
            print(f"[openalex] {cid}: {exc}")
            continue
        for year, total in totals.items():
            n = counts.get(year, 0)
            rows.append({"concept_id": cid, "period": str(year), "count": n, "total": total,
                         "share": n / total if total else 0.0})
    status = "ok" if not failed else "degraded"
    log.record("openalex", status, f"{len(rows)} rows; {len(failed)} concepts failed",
               "" if not failed else f"failed: {','.join(failed)}", url)
    df = pd.DataFrame(rows)
    df["source"] = "openalex"
    df["snapshot_date"] = _dt.date.today().isoformat()
    save_table(df, cfg.path("stage1", f"openalex_{df['snapshot_date'].iloc[0]}"))
    return df
