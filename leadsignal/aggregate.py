"""Shares per concept and period.

s(c,t) = distinct matched papers for c in t / distinct in-scope papers in t.
Every concept gets a row for every period (zero-filled), so gaps are
explicit rather than silently missing. The current, still-incomplete quarter
is dropped by default.
"""

from __future__ import annotations

import datetime as _dt
from typing import List, Optional

import pandas as pd

from .lexicon import LEXICON


def quarter_of(dates: pd.Series) -> pd.Series:
    return pd.PeriodIndex(pd.to_datetime(dates), freq="Q").astype(str)


def quarter_range(start_year: int, last: str) -> List[str]:
    return [str(p) for p in pd.period_range(f"{start_year}Q1", last, freq="Q")]


def last_complete_quarter(today: Optional[_dt.date] = None) -> str:
    today = today or _dt.date.today()
    return str(pd.Period(today, freq="Q") - 1)


def quarterly_shares(papers: pd.DataFrame, matches: pd.DataFrame, start_year: int,
                     density_floor: int, last_quarter: Optional[str] = None,
                     concepts: Optional[List[str]] = None) -> pd.DataFrame:
    concepts = concepts or list(LEXICON)
    papers = papers.drop_duplicates("arxiv_id").copy()
    papers["period"] = quarter_of(papers["v1_date"])
    last_quarter = last_quarter or min(last_complete_quarter(), papers["period"].max())
    periods = quarter_range(start_year, last_quarter)
    totals = papers.groupby("period")["arxiv_id"].nunique().reindex(periods, fill_value=0)

    m = matches.merge(papers[["arxiv_id", "period"]], on="arxiv_id", how="inner")
    counts = (m.groupby(["concept_id", "period"])["arxiv_id"].nunique()
              .rename("count").reset_index())
    grid = pd.MultiIndex.from_product([concepts, periods], names=["concept_id", "period"])
    df = (counts.set_index(["concept_id", "period"]).reindex(grid, fill_value=0).reset_index())
    df["total"] = df["period"].map(totals).astype(int)
    df["share"] = df["count"] / df["total"].where(df["total"] > 0)
    df["share"] = df["share"].fillna(0.0)
    df["sparse"] = df["count"] < density_floor
    return df


def to_yearly(quarterly: pd.DataFrame, density_floor: int) -> pd.DataFrame:
    """Collapse a quarterly share table to calendar years (for channel comparison)."""
    q = quarterly.copy()
    q["year"] = q["period"].str[:4]
    counts = q.groupby(["concept_id", "year"])["count"].sum()
    totals = q.drop_duplicates("period").groupby("year")["total"].sum()
    df = counts.rename("count").reset_index().rename(columns={"year": "period"})
    df["total"] = df["period"].map(totals)
    df["share"] = (df["count"] / df["total"]).fillna(0.0)
    df["sparse"] = df["count"] < density_floor
    return df
