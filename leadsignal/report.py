"""Curriculum-review report: advisory, never a decision.

Lists concepts whose research attention is rising or declining relative to the
field in the most recent quarter, with the evidence behind each flag.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import pandas as pd

from .lexicon import LEXICON, LEXICON_VERSION


def current_flags(trends: pd.DataFrame, period: Optional[str] = None) -> pd.DataFrame:
    period = period or trends.loc[trends["label"] != "insufficient", "period"].max()
    cur = trends[trends["period"] == period].copy()
    cur["concept"] = cur["concept_id"].map(lambda c: LEXICON[c]["label"])
    cur["volatility"] = cur["concept_id"].map(lambda c: LEXICON[c]["volatility"])
    order = {"rising": 0, "declining": 1, "stable": 2, "insufficient": 3}
    cur = cur.sort_values(by=["label", "ebar"], key=lambda s: s.map(order) if s.name == "label" else -s)
    return cur[["period", "concept", "concept_id", "volatility", "label", "confirmed",
                "ebar", "p_adj", "count", "share", "sparse"]]


def render_markdown(trends: pd.DataFrame, provenance: str, data_until: str,
                    period: Optional[str] = None) -> str:
    flags = current_flags(trends, period)
    per = flags["period"].iloc[0] if len(flags) else "n/a"
    lines = [
        "# LeadSignal-CS curriculum-review report",
        "",
        f"Generated {_dt.date.today().isoformat()} | quarter assessed: {per} | "
        f"data until: {data_until} | lexicon v{LEXICON_VERSION}",
        "",
        f"**Provenance:** {provenance}",
        "",
        "> This report is advisory. A flag means research attention to a concept is moving "
        "relative to the rest of the field. It is not a recommendation to add or remove "
        "teaching content. Review the evidence and local context before acting.",
        "",
    ]
    for label, title in (("rising", "Rising attention"), ("declining", "Declining attention")):
        sub = flags[flags["label"] == label]
        lines += [f"## {title} ({len(sub)})", ""]
        if sub.empty:
            lines += ["None this quarter.", ""]
            continue
        lines += ["| Concept | Class | Confirmed | Excess growth (4q mean) | Adjusted p | Papers |",
                  "|---|---|---|---|---|---|"]
        for _, r in sub.iterrows():
            lines.append(f"| {r['concept']} | {r['volatility']} | {'yes' if r['confirmed'] else 'no'} | "
                         f"{r['ebar']:+.2f} | {r['p_adj']:.3f} | {int(r['count'])} |")
        lines.append("")
    sparse = flags[flags["sparse"]]
    if len(sparse):
        lines += ["## Too sparse to judge", "", ", ".join(sparse["concept"]), ""]
    return "\n".join(lines)
