"""Detrending, trend labels and statistical confirmation (proposal Section 4.3).

For concept c and period t:
  rel(c,t)  = ln(s(c,t)+eps) - median over concepts of ln(s(.,t)+eps)
              the concept's log share relative to the field in that period;
              a field-wide surge moves the median and cancels out.
  e(c,t)    = rel(c,t) - rel(c,t-lag)       excess growth (lag 4 = year over year)
  ebar(c,t) = mean of e over the last `label_window` periods
  label     = rising if ebar > threshold, declining if ebar < -threshold, else stable
  confirmed = the Hamed-Rao modified Mann-Kendall test on the last `mk_window`
              values of rel agrees in direction and is significant after
              Benjamini-Hochberg correction across concepts in that period.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.stats import kruskal, norm, rankdata


# ------------------------------------------------------------- statistics
def sens_slope(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    n = len(x)
    i, j = np.triu_indices(n, k=1)
    return float(np.median((x[j] - x[i]) / (j - i))) if n > 1 else 0.0


def mann_kendall_hr(x, alpha: float = 0.05) -> Dict[str, float]:
    """Mann-Kendall trend test with the Hamed and Rao (1998) variance correction.

    Mirrors pymannkendall.hamed_rao_modification_test so results can be
    cross-checked; adds a guard for the rare case where the correction factor
    is not positive in very short series (then the uncorrected variance is used
    and 'corrected' is reported as 0)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 4 or np.all(x == x[0]):
        return {"s": 0.0, "var_s": np.nan, "z": 0.0, "p": 1.0, "slope": 0.0, "corrected": 0}
    i, j = np.triu_indices(n, k=1)
    s = float(np.sign(x[j] - x[i]).sum())
    uniq, counts = np.unique(x, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18.0
    slope = sens_slope(x)
    detr = x - np.arange(1, n + 1) * slope
    ranks = rankdata(detr)
    y = ranks - ranks.mean()
    acov = np.correlate(y, y, "full")[n - 1:] / n
    acf = acov / acov[0]
    bound = norm.ppf(1 - alpha / 2) / np.sqrt(n)
    sni = sum((n - k) * (n - k - 1) * (n - k - 2) * acf[k]
              for k in range(1, n) if abs(acf[k]) > bound)
    n_ns = 1 + (2 / (n * (n - 1) * (n - 2))) * sni
    corrected = 1
    if n_ns <= 0:
        n_ns, corrected = 1.0, 0
    var_c = var_s * n_ns
    z = 0.0 if s == 0 else (s - np.sign(s)) / np.sqrt(var_c)
    p = float(2 * (1 - norm.cdf(abs(z))))
    return {"s": s, "var_s": float(var_c), "z": float(z), "p": p, "slope": slope,
            "corrected": corrected}


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    """Adjusted p-values (step-up), NaNs left as NaN."""
    p = pd.Series(p, dtype=float)
    ok = p.dropna()
    m = len(ok)
    if m == 0:
        return p
    order = ok.sort_values()
    ranks = np.arange(1, m + 1)
    adj = (order.to_numpy() * m / ranks)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = pd.Series(np.minimum(adj, 1.0), index=order.index)
    return out.reindex(p.index)


# -------------------------------------------------------------- pipeline
def _long(wide: pd.DataFrame, name: str) -> pd.DataFrame:
    df = wide.copy()
    df.index.name = "period"
    df.columns.name = None
    return df.reset_index().melt(id_vars="period", var_name="concept_id", value_name=name)


def compute_trends(shares: pd.DataFrame, lag: int, label_window: int, mk_window: int,
                   threshold: float, epsilon: float, alpha: float,
                   concepts_for_median: Optional[list] = None, detrend: bool = True,
                   value_col: str = "share") -> pd.DataFrame:
    """shares: long table with concept_id, period, count, share, sparse.
    Returns one row per concept-period with rel, e, ebar, label, p, p_adj, confirmed.

    detrend=False and value_col="count" exist only for the baselines in
    evaluate.py; the method itself always uses shares with detrending."""
    wide = shares.pivot(index="period", columns="concept_id", values=value_col).sort_index()
    wide = wide.astype(float)
    logs = np.log(wide + epsilon)
    ref_cols = concepts_for_median or list(wide.columns)
    rel = logs.sub(logs[ref_cols].median(axis=1), axis=0) if detrend else logs
    e = rel - rel.shift(lag)
    ebar = e.rolling(label_window, min_periods=label_window).mean()

    label = pd.DataFrame("insufficient", index=wide.index, columns=wide.columns)
    label[ebar > threshold] = "rising"
    label[ebar < -threshold] = "declining"
    label[(ebar.abs() <= threshold)] = "stable"

    # Build p-values and slopes in plain arrays (safe under pandas copy-on-write).
    pv = np.full(wide.shape, np.nan)
    sl = np.full(wide.shape, np.nan)
    rel_arr, ebar_arr = rel.to_numpy(), ebar.to_numpy()
    for j in range(wide.shape[1]):
        series = rel_arr[:, j]
        for k in range(mk_window - 1, len(series)):
            if np.isnan(ebar_arr[k, j]):
                continue
            res = mann_kendall_hr(series[k - mk_window + 1:k + 1], alpha)
            pv[k, j], sl[k, j] = res["p"], res["slope"]
    pvals = pd.DataFrame(pv, index=wide.index, columns=wide.columns)
    slopes = pd.DataFrame(sl, index=wide.index, columns=wide.columns)
    padj = pvals.apply(benjamini_hochberg, axis=1)

    parts = [_long(rel, "rel"), _long(e, "e"), _long(ebar, "ebar"), _long(label, "label"),
             _long(pvals, "p"), _long(padj, "p_adj"), _long(slopes, "sen_slope")]
    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on=["period", "concept_id"])
    sig = out["p_adj"] < alpha
    out["confirmed"] = ((out["label"] == "rising") & sig & (out["sen_slope"] > 0)) | \
                       ((out["label"] == "declining") & sig & (out["sen_slope"] < 0))
    out = out.merge(shares[["concept_id", "period", "count", "share", "sparse"]],
                    on=["concept_id", "period"], how="left")
    return out.sort_values(["concept_id", "period"]).reset_index(drop=True)


def churn(trends: pd.DataFrame) -> pd.DataFrame:
    """Per-concept churn for H1b: variance of e and number of label changes."""
    rows = []
    for cid, g in trends.groupby("concept_id"):
        g = g.sort_values("period")
        labels = g.loc[g["label"] != "insufficient", "label"]
        flips = int((labels != labels.shift()).sum() - 1) if len(labels) else 0
        rows.append({"concept_id": cid, "var_e": float(np.nanvar(g["e"])),
                     "label_changes": max(flips, 0)})
    return pd.DataFrame(rows)


def volatility_test(churn_df: pd.DataFrame, lexicon: Dict[str, Dict]) -> Dict[str, float]:
    """Kruskal-Wallis across volatility classes, with epsilon-squared effect size."""
    df = churn_df.copy()
    df["volatility"] = df["concept_id"].map(lambda c: lexicon[c]["volatility"])
    groups = [g["var_e"].dropna().to_numpy() for _, g in df.groupby("volatility")]
    groups = [g for g in groups if len(g) > 1]
    if len(groups) < 2:
        return {"H": np.nan, "p": np.nan, "epsilon_sq": np.nan}
    H, p = kruskal(*groups)
    n = sum(len(g) for g in groups)
    eps2 = (H - len(groups) + 1) / (n - len(groups)) if n > len(groups) else np.nan
    medians = df.groupby("volatility")["var_e"].median().to_dict()
    return {"H": float(H), "p": float(p), "epsilon_sq": float(eps2),
            **{f"median_var_e_{k}": float(v) for k, v in medians.items()}}
