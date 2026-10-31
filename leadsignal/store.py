"""Storage helpers.

Every stage reads the previous stage's file and writes its own, so a failed
stage restarts from the last good file instead of from zero. Files are
parquet when pyarrow is available (it is on Colab) and gzip CSV otherwise.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

try:  # pragma: no cover - depends on environment
    import pyarrow  # noqa: F401
    _HAS_PARQUET = True
except Exception:  # pragma: no cover
    _HAS_PARQUET = False


def table_path(base: Path) -> Path:
    base = Path(base)
    return base.with_suffix(".parquet" if _HAS_PARQUET else ".csv.gz")


def save_table(df: pd.DataFrame, base: Path) -> Path:
    path = table_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if _HAS_PARQUET:
        df.to_parquet(tmp, index=False)
    else:
        df.to_csv(tmp, index=False, compression="gzip")
    tmp.replace(path)  # atomic: a crash never leaves a half-written file
    return path


def load_table(base: Path) -> Optional[pd.DataFrame]:
    for suffix in (".parquet", ".csv.gz"):
        p = Path(base).with_suffix(suffix)
        if p.exists():
            return pd.read_parquet(p) if suffix == ".parquet" else pd.read_csv(p)
    return None


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_hash(df: pd.DataFrame) -> str:
    """Order-independent content hash of a table."""
    if df is None or len(df) == 0:
        return hashlib.sha256(b"empty").hexdigest()
    rows = pd.util.hash_pandas_object(df.reset_index(drop=True), index=False)
    ordered = rows.astype("uint64").sort_values().to_numpy()
    header = ",".join(map(str, df.columns)).encode()
    return hashlib.sha256(header + ordered.tobytes()).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        # A corrupt checkpoint is moved aside, not silently ignored.
        bad = p.with_name(p.name + f".corrupt-{_dt.datetime.now():%Y%m%d%H%M%S}")
        p.replace(bad)
        print(f"[store] corrupt JSON moved to {bad}; starting from default")
        return default


def write_json(path: Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    tmp.replace(p)


def manifest_entry(stage: str, outputs: Dict[str, Path], **extra: Any) -> Dict[str, Any]:
    return {
        "stage": stage,
        "time_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "outputs": {k: {"path": str(v), "sha256": file_hash(v)} for k, v in outputs.items()},
        **extra,
    }
