"""Synthetic data for dry runs and tests.

Everything produced here carries source == "synthetic". The exporter refuses
to publish any bundle that contains synthetic rows, so synthetic numbers can
never be presented as findings.

The generator plants known structure so the pipeline can be checked:
  * steady growth in the number of papers (tests share normalisation);
  * planted rises with an adoption event a fixed number of quarters later
    (tests lead-time detection);
  * a field-wide surge in 2022Q4 that lifts every concept (tests detrending);
  * "hype" concepts that rise then fade with no adoption (negative controls);
  * more random churn for volatile concepts (tests H1b).
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .aggregate import quarter_range
from .lexicon import LEXICON

_FILLER = ("study", "method", "results", "evaluation", "approach", "framework", "analysis",
           "benchmark", "empirical", "proposed", "novel", "efficient", "scalable", "setting")

PLANTED_RISES = {  # concept -> (rise start quarter, adoption event quarter)
    "pytorch": ("2016Q3", "2018Q3"),
    "transformer_architectures": ("2017Q3", "2019Q3"),
    "kubernetes": ("2016Q1", "2018Q1"),
    "mlops": ("2019Q1", "2021Q1"),
    "federated_learning": ("2017Q1", "2019Q1"),
}
PLANTED_DECLINES = {"tensorflow": ("2019Q1", "2021Q1")}
HYPE = {"quantum_computing": "2018Q1", "edge_computing": "2019Q1"}  # rise then fade, no event
SURGE_PERIOD = "2022Q4"


def _qi(period: str) -> int:
    return int(period[:4]) * 4 + int(period[-1]) - 1


def generate(start_year: int = 2012, last_quarter: str = "2025Q4", base_papers: int = 300,
             seed: int = 7) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    periods = quarter_range(start_year, last_quarter)
    concepts = list(LEXICON)
    sd = {"stable": 0.02, "moderate": 0.05, "volatile": 0.10}
    base = {c: rng.uniform(0.02, 0.06) for c in concepts}
    walk = {c: 0.0 for c in concepts}
    rows = []
    pid = 0
    for t, per in enumerate(periods):
        n = int(base_papers * np.exp(0.03 * t))
        probs = {}
        for c in concepts:
            walk[c] += rng.normal(0, sd[LEXICON[c]["volatility"]])
            walk[c] *= 0.85  # mean-reverting churn
            mult = np.exp(walk[c])
            if c in PLANTED_RISES:
                k = _qi(per) - _qi(PLANTED_RISES[c][0])
                mult *= 1 + 5 / (1 + np.exp(-0.9 * (k - 3)))
            if c in PLANTED_DECLINES:
                k = _qi(per) - _qi(PLANTED_DECLINES[c][0])
                mult *= 1 - 0.7 / (1 + np.exp(-0.9 * (k - 3)))
            if c in HYPE:
                k = _qi(per) - _qi(HYPE[c])
                mult *= 1 + 4 * np.exp(-((k - 4) ** 2) / 8)
            if _qi(per) >= _qi(SURGE_PERIOD):
                mult *= 1.8  # field-wide surge hits every concept
            probs[c] = min(0.9, base[c] * mult)
        month = {"1": 2, "2": 5, "3": 8, "4": 11}[per[-1]]
        for _ in range(n):
            words = list(rng.choice(_FILLER, 6))
            for c in concepts:
                if rng.random() < probs[c]:
                    words.append(LEXICON[c]["aliases"][0])
            rng.shuffle(words)
            rows.append({"arxiv_id": f"synthetic.{pid:07d}", "v1_date": f"{per[:4]}-{month:02d}-15",
                         "categories": "cs.LG", "title": " ".join(words[:4]),
                         "abstract": " ".join(words), "source": "synthetic"})
            pid += 1
    papers = pd.DataFrame(rows)

    ev = []
    for c, (_, event) in PLANTED_RISES.items():
        ev.append({"concept_id": c, "event_period": event, "event_type": "adoption",
                   "layer": "synthetic", "source_citation": "synthetic ground truth",
                   "citation_status": "sourced", "notes": "planted rise"})
    for c, (_, event) in PLANTED_DECLINES.items():
        ev.append({"concept_id": c, "event_period": event, "event_type": "decline",
                   "layer": "synthetic", "source_citation": "synthetic ground truth",
                   "citation_status": "sourced", "notes": "planted decline"})
    for c in HYPE:
        ev.append({"concept_id": c, "event_period": "", "event_type": "none",
                   "layer": "negative_control", "source_citation": "synthetic ground truth",
                   "citation_status": "sourced", "notes": "planted hype, never adopted"})
    return papers, pd.DataFrame(ev)


def expected_leads() -> Dict[str, int]:
    """Planted lead in quarters between rise start and event."""
    return {c: _qi(e) - _qi(s) for c, (s, e) in {**PLANTED_RISES, **PLANTED_DECLINES}.items()}
