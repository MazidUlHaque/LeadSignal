"""Lead-time evaluation, baselines, sensitivity and cross-channel validation
(proposal Section 4.4).

Ground-truth event file columns:
  concept_id, event_period (e.g. 2024Q1), event_type (adoption | decline),
  layer (systematic | curated | negative_control), source_citation,
  citation_status (sourced | requires_citation), notes

Negative controls use event_type "none": any persistent rising detection for
them inside the window counts as a false alarm.

Only events with citation_status == "sourced" count as findings. Others are
reported separately as diagnostics.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import Config
from .trend import compute_trends

EVENT_COLUMNS = ["concept_id", "event_period", "event_type", "layer",
                 "source_citation", "citation_status", "notes"]


def load_events(path) -> pd.DataFrame:
    ev = pd.read_csv(path, dtype=str).fillna("")
    missing = set(EVENT_COLUMNS) - set(ev.columns)
    if missing:
        raise ValueError(f"event file is missing columns: {sorted(missing)}")
    return ev


def _series(trends: pd.DataFrame, cid: str) -> pd.DataFrame:
    return trends[trends["concept_id"] == cid].sort_values("period").reset_index(drop=True)


def first_detection(g: pd.DataFrame, direction: str, start: int, end: int,
                    persistence: int) -> Optional[int]:
    labels = g["label"].to_numpy()
    confirmed = g["confirmed"].to_numpy()
    for k in range(max(start, 0), min(end, len(g) - persistence + 1)):
        if labels[k] == direction and confirmed[k] and all(labels[k + d] == direction
                                                           for d in range(persistence)):
            return k
    return None


def lead_times(trends: pd.DataFrame, events: pd.DataFrame, cfg: Config,
               last_period: Optional[str] = None) -> pd.DataFrame:
    rows = []
    for _, ev in events.iterrows():
        cid = ev["concept_id"]
        g = _series(trends, cid)
        row = {**ev.to_dict(), "status": "", "detect_period": None, "lead": np.nan}
        if g.empty:
            rows.append({**row, "status": "unevaluable: concept not in data"})
            continue
        periods = g["period"].tolist()
        valid = np.flatnonzero((g["label"] != "insufficient").to_numpy())
        first_valid = int(valid[0]) if len(valid) else None
        direction = "declining" if ev["event_type"] == "decline" else "rising"

        if ev["event_type"] == "none":  # negative control: search the whole window
            k = first_detection(g, "rising", first_valid or 0, len(g), cfg.persistence)
            row["status"] = "false_alarm" if k is not None else "correct_rejection"
            row["detect_period"] = periods[k] if k is not None else None
            rows.append(row)
            continue

        if ev["event_period"] not in periods:
            status = ("unevaluable: event after latest data"
                      if ev["event_period"] > periods[-1] else "unevaluable: event before window")
            rows.append({**row, "status": status})
            continue
        e_idx = periods.index(ev["event_period"])
        if first_valid is None or e_idx - first_valid < cfg.min_history_before_event:
            rows.append({**row, "status": "unevaluable: too little history before event"})
            continue
        around = g.iloc[max(0, e_idx - 4):e_idx + 1]["sparse"]
        if around.mean() > 0.5:
            rows.append({**row, "status": "unevaluable: concept sparse around event"})
            continue
        k = first_detection(g, direction, first_valid, e_idx + cfg.detection_horizon_after + 1,
                            cfg.persistence)
        if k is None:
            rows.append({**row, "status": "not_detected"})
            continue
        rows.append({**row, "status": "detected", "detect_period": periods[k],
                     "lead": float(e_idx - k)})
    return pd.DataFrame(rows)


def bootstrap_median_ci(values: np.ndarray, reps: int, seed: int, level: float = 0.95):
    values = np.asarray(values, float)
    if len(values) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    meds = np.median(rng.choice(values, size=(reps, len(values)), replace=True), axis=1)
    lo, hi = np.quantile(meds, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def summarise(lt: pd.DataFrame, cfg: Config, sourced_only: bool = True) -> Dict[str, float]:
    df = lt.copy()
    if sourced_only:
        df = df[(df["citation_status"] == "sourced") | (df["event_type"] == "none")]
    real = df[df["event_type"] != "none"]
    evaluable = real[~real["status"].str.startswith("unevaluable")]
    detected = evaluable[evaluable["status"] == "detected"]
    leads = detected["lead"].to_numpy()
    lo, hi = bootstrap_median_ci(leads, cfg.bootstrap_reps, cfg.random_seed)
    neg = df[df["event_type"] == "none"]
    fa = (neg["status"] == "false_alarm").mean() if len(neg) else np.nan
    return {
        "events_total": int(len(real)), "events_evaluable": int(len(evaluable)),
        "events_detected": int(len(detected)),
        "detection_rate": float(len(detected) / len(evaluable)) if len(evaluable) else np.nan,
        "median_lead_quarters": float(np.median(leads)) if len(leads) else np.nan,
        "median_lead_ci_low": lo, "median_lead_ci_high": hi,
        "share_positive_lead": float((leads > 0).mean()) if len(leads) else np.nan,
        "negative_controls": int(len(neg)), "false_alarm_rate": float(fa) if fa == fa else np.nan,
    }


# ------------------------------------------------------------ baselines
def run_method(shares: pd.DataFrame, cfg: Config, threshold: Optional[float] = None,
               detrend: bool = True, value_col: str = "share") -> pd.DataFrame:
    return compute_trends(shares, lag=cfg.growth_lag_quarters, label_window=cfg.label_window,
                          mk_window=cfg.mk_window, threshold=threshold or cfg.threshold,
                          epsilon=cfg.epsilon if value_col == "share" else 1.0,
                          alpha=cfg.fdr_alpha, detrend=detrend, value_col=value_col)


def baselines(shares: pd.DataFrame, events: pd.DataFrame, cfg: Config,
              sourced_only: bool = True) -> pd.DataFrame:
    variants = {
        "method (share, detrended)": dict(detrend=True, value_col="share"),
        "baseline 1: share, no detrending": dict(detrend=False, value_col="share"),
        "baseline 2: raw counts": dict(detrend=False, value_col="count"),
    }
    rows = []
    for name, kw in variants.items():
        tr = run_method(shares, cfg, **kw)
        rows.append({"variant": name, **summarise(lead_times(tr, events, cfg), cfg, sourced_only)})
    return pd.DataFrame(rows)


def sensitivity(shares: pd.DataFrame, events: pd.DataFrame, cfg: Config,
                sourced_only: bool = True) -> pd.DataFrame:
    rows = []
    for th in cfg.threshold_grid:
        tr = run_method(shares, cfg, threshold=th)
        rows.append({"threshold": th, **summarise(lead_times(tr, events, cfg), cfg, sourced_only)})
    return pd.DataFrame(rows)


# ------------------------------------------------------ cross-channel
def cohen_kappa(a: pd.Series, b: pd.Series) -> float:
    a, b = a.astype(str), b.astype(str)
    cats = sorted(set(a) | set(b))
    if len(a) == 0:
        return np.nan
    po = float((a.to_numpy() == b.to_numpy()).mean())
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else np.nan


def channel_agreement(primary: pd.DataFrame, other: pd.DataFrame, channel: str) -> pd.DataFrame:
    """primary and other: yearly trend tables from compute_trends (lag=1)."""
    cols = ["concept_id", "period", "e", "label"]
    m = primary[cols].merge(other[cols], on=["concept_id", "period"], suffixes=("_arxiv", "_other"))
    m = m.dropna(subset=["e_arxiv", "e_other"])
    rows = []
    for cid, g in m.groupby("concept_id"):
        rho, p = (spearmanr(g["e_arxiv"], g["e_other"]) if len(g) >= 4 else (np.nan, np.nan))
        valid = g[(g["label_arxiv"] != "insufficient") & (g["label_other"] != "insufficient")]
        rows.append({"channel": channel, "concept_id": cid, "n_years": len(g),
                     "spearman_rho": float(rho) if rho == rho else np.nan,
                     "spearman_p": float(p) if p == p else np.nan,
                     "kappa": cohen_kappa(valid["label_arxiv"], valid["label_other"])})
    return pd.DataFrame(rows)


def order_of_arrival(channel_trends: Dict[str, pd.DataFrame], concepts: List[str]) -> pd.DataFrame:
    """For each concept, the first year each channel showed a rising label."""
    rows = []
    for cid in concepts:
        row = {"concept_id": cid}
        for ch, tr in channel_trends.items():
            g = tr[(tr["concept_id"] == cid) & (tr["label"] == "rising")].sort_values("period")
            row[f"first_rising_{ch}"] = g["period"].iloc[0] if len(g) else None
        rows.append(row)
    return pd.DataFrame(rows)
