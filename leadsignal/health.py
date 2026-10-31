"""Source health log.

Each pull starts with a health check. The log records the date, source,
status (ok, degraded, unavailable), reason and action. A source that is
unavailable for N consecutive runs is flagged for a human decision: the
system never swaps in a different source on its own.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional

import pandas as pd

STATUSES = ("ok", "degraded", "unavailable")
COLUMNS = ["time_utc", "source", "endpoint", "status", "reason", "action"]


class HealthLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> pd.DataFrame:
        if self.path.exists():
            return pd.read_csv(self.path)
        return pd.DataFrame(columns=COLUMNS)

    def record(self, source: str, status: str, reason: str = "", action: str = "",
               endpoint: str = "") -> dict:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        row = {
            "time_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "source": source, "endpoint": endpoint, "status": status,
            "reason": reason, "action": action,
        }
        df = pd.concat([self.read(), pd.DataFrame([row])], ignore_index=True)
        df.to_csv(self.path, index=False)
        print(f"[health] {source:<9} {status:<11} {reason} {('-> ' + action) if action else ''}")
        return row

    def needs_decision(self, source: str, n: int) -> bool:
        """True if the last n entries for this source are all 'unavailable'."""
        df = self.read()
        df = df[df["source"] == source]
        if len(df) < n:
            return False
        return bool((df.tail(n)["status"] == "unavailable").all())

    def flags(self, sources: List[str], n: int) -> List[str]:
        return [s for s in sources if self.needs_decision(s, n)]

    def last_status(self, source: str) -> Optional[str]:
        df = self.read()
        df = df[df["source"] == source]
        return None if df.empty else str(df.iloc[-1]["status"])
