"""Citable export bundle (proposal Section 9).

The bundle contains the aggregate tables, a data dictionary, the lexicon
version, the source health log, the configuration, a manifest of SHA-256
hashes, a licence and a citation file. Paper titles and abstracts are NOT
redistributed: only identifiers and counts.

The exporter refuses to write a bundle if any input is synthetic.
"""

from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path
from typing import Dict

import pandas as pd

from . import __version__
from .config import Config
from .lexicon import LEXICON_VERSION, to_json
from .store import file_hash, write_json

DICTIONARY = """# Data dictionary

## shares_quarterly.csv (arXiv)
- concept_id: lexicon identifier (see lexicon.json)
- period: calendar quarter, e.g. 2019Q3, of the paper's FIRST version
- count: distinct arXiv papers matched to the concept in that quarter
- total: distinct in-scope arXiv papers in that quarter
- share: count / total
- sparse: true if count is below the density floor in config.json

## trends_quarterly.csv
- rel: log share relative to the median concept in that quarter
- e: excess growth, rel minus rel four quarters earlier
- ebar: mean of e over the last four quarters
- label: rising | stable | declining | insufficient
- p, p_adj: Hamed-Rao Mann-Kendall p-value and its Benjamini-Hochberg adjustment
- sen_slope: Sen slope of rel over the test window
- confirmed: label direction agrees with a significant test

## openalex_*.csv, github_*.csv (validation snapshots, yearly)
- same columns as shares, one file per dated snapshot

## health_log.csv
- one row per source check: time, source, endpoint, status, reason, action
"""

CITATION = """cff-version: 1.2.0
message: "If you use this dataset, please cite it as below."
title: "LeadSignal-CS: concept-level research attention in computer science"
authors:
  - name: "Mazid"
version: "{version}"
date-released: "{date}"
license: CC-BY-4.0
"""

LICENCE = """Aggregate data in this bundle: Creative Commons Attribution 4.0 (CC BY 4.0).
Underlying sources: arXiv metadata (CC0), OpenAlex (CC0), GitHub aggregate search
counts (GitHub Terms of Service). No paper text, usernames or repository contents
are included.
"""


class SyntheticDataError(RuntimeError):
    pass


def export_bundle(cfg: Config, tables: Dict[str, pd.DataFrame], health_log: Path) -> Path:
    for name, df in tables.items():
        if "source" in df.columns and (df["source"] == "synthetic").any():
            raise SyntheticDataError(f"refusing to export: table {name!r} contains synthetic rows")
    date = _dt.date.today().isoformat()
    out = Path(cfg.data_dir) / "exports" / f"leadsignal_cs_{date}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"created": date, "software_version": __version__,
                "lexicon_version": LEXICON_VERSION, "files": {}}
    for name, df in tables.items():
        p = out / f"{name}.csv"
        df.to_csv(p, index=False)
        manifest["files"][p.name] = file_hash(p)
    (out / "lexicon.json").write_text(to_json())
    (out / "config.json").write_text(cfg.to_json())
    (out / "DATA_DICTIONARY.md").write_text(DICTIONARY)
    (out / "LICENSE.txt").write_text(LICENCE)
    (out / "CITATION.cff").write_text(CITATION.format(version=__version__, date=date))
    if Path(health_log).exists():
        shutil.copy(health_log, out / "health_log.csv")
    for extra in ("lexicon.json", "config.json", "DATA_DICTIONARY.md", "LICENSE.txt",
                  "CITATION.cff", "health_log.csv"):
        if (out / extra).exists():
            manifest["files"][extra] = file_hash(out / extra)
    write_json(out / "MANIFEST.json", manifest)
    print(f"[export] bundle written to {out} (upload this folder to Zenodo for a DOI)")
    return out
