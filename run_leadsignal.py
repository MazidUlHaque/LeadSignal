"""Command-line entry point for LeadSignal-CS.

Examples (Colab cells prefix these with !):
  python run_leadsignal.py demo
  python run_leadsignal.py diagnose  --data-dir /content/drive/MyDrive/leadsignal
  python run_leadsignal.py build     --data-dir ... --snapshot /path/arxiv-metadata-oai-snapshot.json
  python run_leadsignal.py update    --data-dir ...
  python run_leadsignal.py openalex  --data-dir ... --email you@example.com
  python run_leadsignal.py github    --data-dir ...
  python run_leadsignal.py analyse   --data-dir ... [--events data/ground_truth/curated_events.csv] [--sample]
  python run_leadsignal.py audit     --data-dir ...   (writes precision-audit sheets)
  python run_leadsignal.py precision --data-dir ...   (reads the filled sheets)
  python run_leadsignal.py events    --data-dir ... [--mapping file.xlsx] [--second-coder file.xlsx]
                                     (turns the filled CS2013/CS2023 mapping into curriculum events)
  python run_leadsignal.py storage   --data-dir ...   (how much Drive space the data uses)
  python run_leadsignal.py export    --data-dir ...
"""

import argparse
import sys

from leadsignal import pipeline
from leadsignal.config import Config
from leadsignal.export import SyntheticDataError
from leadsignal.sources.http import SourceUnavailable


def main(argv=None):
    ap = argparse.ArgumentParser(description="LeadSignal-CS")
    ap.add_argument("mode", choices=["demo", "diagnose", "build", "update", "openalex",
                                     "github", "analyse", "audit", "precision", "events", "export", "storage"])
    ap.add_argument("--data-dir", default="leadsignal_data")
    ap.add_argument("--snapshot", default=None, help="path to arxiv-metadata-oai-snapshot.json")
    ap.add_argument("--events", default=None, help="ground-truth events CSV")
    ap.add_argument("--mapping", default=None, help="filled CS2013/CS2023 mapping (.xlsx or .csv)")
    ap.add_argument("--second-coder", default=None, help="a colleague's independent mapping, for agreement")
    ap.add_argument("--email", default=None, help="contact email for OpenAlex (not a credential)")
    ap.add_argument("--sample", action="store_true", help="small, fast run on a few concepts")
    ap.add_argument("--start-year", type=int, default=None)
    a = ap.parse_args(argv)

    cfg = Config(data_dir=a.data_dir, contact_email=a.email)
    if a.start_year:
        cfg.start_year = a.start_year
    concepts = pipeline.SAMPLE_CONCEPTS if a.sample else None

    if a.mode == "demo":
        pipeline.demo(cfg)
    elif a.mode == "diagnose":
        print(pipeline.diagnose(cfg).to_string(index=False))
    elif a.mode == "build":
        pipeline.build_arxiv(cfg, a.snapshot)
    elif a.mode == "update":
        pipeline.update_arxiv(cfg)
    elif a.mode == "openalex":
        pipeline.pull_openalex(cfg, concepts)
    elif a.mode == "github":
        pipeline.pull_github(cfg, concepts)
    elif a.mode == "analyse":
        pipeline.analyse(cfg, a.events, sample=a.sample)
    elif a.mode == "audit":
        pipeline.audit_sheets(cfg)
    elif a.mode == "precision":
        print(pipeline.audit_precision(cfg).to_string(index=False))
    elif a.mode == "events":
        pipeline.build_events(cfg, a.mapping, a.second_coder)
    elif a.mode == "storage":
        print(pipeline.storage_report(cfg).head(10).to_string(index=False))
    elif a.mode == "export":
        pipeline.export(cfg)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SyntheticDataError, SourceUnavailable, FileNotFoundError, ValueError) as exc:
        print(f"\n[STOPPED] {type(exc).__name__}: {exc}")
        print("See RUNBOOK.md for what this means and what to do next.")
        sys.exit(2)
