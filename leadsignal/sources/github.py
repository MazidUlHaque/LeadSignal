"""GitHub: bounded, hand-run validation snapshot.

Measures practitioner attention as the share of repositories created each
year that carry the concept's topic tag. Topics were introduced around 2017,
so the series starts then. Only aggregate counts are requested and stored:
no repository names, owners or contents.

A read-only personal access token (environment variable GITHUB_TOKEN) is
recommended but optional. Requests are paced to stay inside the search limits
(roughly 10 per minute without a token, 30 per minute with one).
"""

from __future__ import annotations

import datetime as _dt
from typing import List, Optional

import pandas as pd

from ..config import Config
from ..health import HealthLog
from ..lexicon import LEXICON
from ..store import save_table
from .http import PoliteClient, SourceUnavailable


def _client(cfg: Config) -> PoliteClient:
    token = cfg.github_token()
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    interval = 2.2 if token else 6.5
    return PoliteClient(cfg.user_agent, cfg.request_timeout, interval,
                        cfg.max_consecutive_failures, 3 * 3600, headers)


def _count(client: PoliteClient, cfg: Config, query: str):
    data = client.get_json(f"{cfg.github_base}/search/repositories",
                           {"q": query, "per_page": "1"})
    return int(data.get("total_count", 0)), bool(data.get("incomplete_results", False))


def concept_query(cid: str) -> str:
    c = LEXICON[cid]
    if c.get("github_topic"):
        return f"topic:{c['github_topic']}"
    return f'"{c["aliases"][0]}" in:name,description,topics'


def snapshot(cfg: Config, log: HealthLog, client: Optional[PoliteClient] = None,
             concepts: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
    client = client or _client(cfg)
    years = list(range(cfg.github_start_year, cfg.end_year + 1))
    rows, incomplete = [], 0
    try:
        totals = {}
        for y in years:
            totals[y], inc = _count(client, cfg, f"created:{y}-01-01..{y}-12-31")
            incomplete += inc
        for cid in concepts or list(LEXICON):
            q = concept_query(cid)
            for y in years:
                n, inc = _count(client, cfg, f"{q} created:{y}-01-01..{y}-12-31")
                incomplete += inc
                rows.append({"concept_id": cid, "period": str(y), "count": n, "total": totals[y],
                             "share": n / totals[y] if totals[y] else 0.0, "incomplete": inc})
    except SourceUnavailable as exc:
        log.record("github", "unavailable" if not rows else "degraded", str(exc),
                   "partial snapshot kept" if rows else "snapshot skipped this run",
                   cfg.github_base)
        if not rows:
            return None
    else:
        log.record("github", "ok" if not incomplete else "degraded",
                   f"{len(rows)} rows; {incomplete} incomplete counts flagged", "", cfg.github_base)
    df = pd.DataFrame(rows)
    df["source"] = "github"
    df["snapshot_date"] = _dt.date.today().isoformat()
    save_table(df, cfg.path("stage1", f"github_{df['snapshot_date'].iloc[0]}"))
    return df
