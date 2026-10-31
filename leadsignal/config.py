"""Run configuration.

Every numeric setting that affects results lives here, with its status.
"provisional" means it is set for development and will be fixed during the
pilot from real data. Nothing here should be reported as a finding.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


def _this_year() -> int:
    return _dt.date.today().year


@dataclass
class Config:
    # ---- storage -------------------------------------------------------
    # On Colab point this at Google Drive, e.g. /content/drive/MyDrive/leadsignal
    data_dir: str = "leadsignal_data"

    # ---- scope ---------------------------------------------------------
    categories: List[str] = field(default_factory=lambda: [
        "cs.AI", "cs.LG", "cs.CL", "cs.CY", "cs.SE", "cs.CR",
    ])
    start_year: int = 2012              # justified: start of deep learning era
    github_start_year: int = 2017       # justified: GitHub topics introduced
    end_year: int = field(default_factory=_this_year)

    # ---- measurement (provisional unless noted) ------------------------
    epsilon: float = 1e-4               # added before logs; sensitivity-checked
    growth_lag_quarters: int = 4        # year-over-year (removes seasonality)
    label_window: int = 4               # quarters averaged for the primary rule
    threshold: float = 0.20             # primary rule threshold (provisional)
    threshold_grid: List[float] = field(default_factory=lambda: [
        0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40,
    ])
    mk_window: int = 8                  # quarters used by Mann-Kendall
    fdr_alpha: float = 0.05             # Benjamini-Hochberg level
    persistence: int = 2                # consecutive rising quarters to detect
    density_floor: int = 5              # min matched papers per concept-quarter (provisional)
    min_history_before_event: int = 4   # valid-label quarters needed before an event
    detection_horizon_after: int = 8    # quarters after an event still searched
    bootstrap_reps: int = 2000
    random_seed: int = 20260925

    # ---- network etiquette ---------------------------------------------
    user_agent: str = "LeadSignal-CS/0.1 (academic research; contact via config)"
    contact_email: Optional[str] = None  # sent to OpenAlex if set; not a credential
    arxiv_oai_endpoints: List[str] = field(default_factory=lambda: [
        "https://oaipmh.arxiv.org/oai",
        "https://export.arxiv.org/oai2",
    ])
    arxiv_delay_seconds: float = 3.0
    openalex_base: str = "https://api.openalex.org"
    github_base: str = "https://api.github.com"
    request_timeout: float = 60.0
    max_consecutive_failures: int = 5
    time_budget_seconds: float = 3 * 3600

    # ---- source health -------------------------------------------------
    unavailable_runs_before_flag: int = 3

    def path(self, *parts: str) -> Path:
        p = Path(self.data_dir).joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Config":
        return cls(**json.loads(text))

    @staticmethod
    def github_token() -> Optional[str]:
        """Read-only GitHub token from the environment. Never stored on disk."""
        return os.environ.get("GITHUB_TOKEN") or None

    @staticmethod
    def openalex_key() -> Optional[str]:
        """Optional free OpenAlex API key from the environment."""
        return os.environ.get("OPENALEX_API_KEY") or None
