"""Stage orchestration.

Stage 0 health check -> 1 acquire -> 2 match -> 3 aggregate -> 4 trend
-> 5 evaluate -> 6 report and export.

Every stage prints OK or FAIL with the error type. Nothing fails silently.
Every stage writes its output under cfg.data_dir, so any stage can be rerun
on its own from the previous stage's file.
"""

from __future__ import annotations

import glob
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd

from . import aggregate, evaluate, groundtruth, match, report, synthetic, trend
from .config import Config
from .export import export_bundle
from .health import HealthLog
from .lexicon import LEXICON, LEXICON_VERSION
from .sources import arxiv, github, openalex
from .sources.http import PoliteClient, SourceUnavailable
from .store import load_table, save_table, write_json

SAMPLE_CONCEPTS = ["pytorch", "transformer_architectures", "algorithms", "kubernetes"]


def _stage(name: str, fn: Callable, *args, **kwargs):
    t0 = time.time()
    try:
        out = fn(*args, **kwargs)
    except Exception as exc:
        print(f"[FAIL] {name:<28} {time.time() - t0:6.1f}s  {type(exc).__name__}: {exc}")
        raise
    print(f"[OK  ] {name:<28} {time.time() - t0:6.1f}s")
    return out


def health_log(cfg: Config) -> HealthLog:
    return HealthLog(cfg.path("health_log.csv"))


# ---------------------------------------------------------------- stage 0
def diagnose(cfg: Config) -> pd.DataFrame:
    """Probe every source once and record the result. Costs no search quota."""
    log = health_log(cfg)
    probe = PoliteClient(cfg.user_agent, 30, 0.0, 2, 120)
    try:
        arxiv.choose_endpoint(cfg, log, probe)
    except SourceUnavailable as exc:  # already written to the health log
        print(f"[diagnose] arXiv: {exc}")
    try:
        params = {"per_page": "1"}
        if cfg.contact_email:
            params["mailto"] = cfg.contact_email
        probe.get_json(f"{cfg.openalex_base}/works", params)
        log.record("openalex", "ok", "works endpoint answered", "", cfg.openalex_base)
    except SourceUnavailable as exc:
        log.record("openalex", "unavailable", str(exc), "validation snapshot will be skipped",
                   cfg.openalex_base)
    try:
        hdr = {"Authorization": f"Bearer {cfg.github_token()}"} if cfg.github_token() else {}
        gh = PoliteClient(cfg.user_agent, 30, 0.0, 2, 120, hdr)
        info = gh.get_json(f"{cfg.github_base}/rate_limit")
        remaining = info.get("resources", {}).get("search", {}).get("remaining", "?")
        log.record("github", "ok", f"search calls remaining: {remaining}",
                   "" if cfg.github_token() else "no token: slower pacing", cfg.github_base)
    except SourceUnavailable as exc:
        log.record("github", "unavailable", str(exc), "validation snapshot will be skipped",
                   cfg.github_base)
    flags = log.flags(["arxiv", "openalex", "github"], cfg.unavailable_runs_before_flag)
    for s in flags:
        print(f"[DECISION NEEDED] {s} has been unavailable for "
              f"{cfg.unavailable_runs_before_flag} consecutive checks. The pipeline will not "
              "substitute another source. Decide whether to wait, replace or drop it, and log it.")
    return log.read().tail(10)


# ---------------------------------------------------------------- stage 1
def build_arxiv(cfg: Config, snapshot_path: Optional[str] = None) -> Path:
    log = health_log(cfg)
    if snapshot_path:
        return _stage("arXiv first build (snapshot)", arxiv.build_from_snapshot, snapshot_path, cfg)
    return _stage("arXiv build via OAI-PMH", arxiv.update_from_oai, cfg, log)


def update_arxiv(cfg: Config) -> Path:
    return _stage("arXiv update (OAI-PMH)", arxiv.update_from_oai, cfg, health_log(cfg))


def pull_openalex(cfg: Config, concepts: Optional[List[str]] = None):
    return _stage("OpenAlex snapshot", openalex.snapshot, cfg, health_log(cfg), None, concepts)


def pull_github(cfg: Config, concepts: Optional[List[str]] = None):
    return _stage("GitHub snapshot", github.snapshot, cfg, health_log(cfg), None, concepts)


def _latest_snapshot(cfg: Config, prefix: str) -> Optional[pd.DataFrame]:
    files = sorted(glob.glob(str(Path(cfg.data_dir) / "stage1" / f"{prefix}_*.parquet")) +
                   glob.glob(str(Path(cfg.data_dir) / "stage1" / f"{prefix}_*.csv.gz")))
    if not files:
        return None
    p = Path(files[-1])
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


# ------------------------------------------------------------ stages 2-6
def yearly_trends(shares_yearly: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    return trend.compute_trends(shares_yearly, lag=1, label_window=2, mk_window=5,
                                threshold=cfg.threshold, epsilon=cfg.epsilon, alpha=cfg.fdr_alpha)


def analyse(cfg: Config, events_path: Optional[str] = None, sample: bool = False,
            last_quarter: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    concepts = SAMPLE_CONCEPTS if sample else list(LEXICON)
    papers = arxiv.load_papers(cfg)
    if papers is None or papers.empty:
        raise FileNotFoundError("no arXiv papers yet: run the build step first")
    if sample:
        papers = papers[papers["v1_date"] >= f"{max(cfg.start_year, 2016)}-01-01"]
        papers = papers.sample(n=min(len(papers), 20000), random_state=cfg.random_seed)
    provenance = ("SYNTHETIC - not evidential" if (papers["source"] == "synthetic").any()
                  else f"real arXiv metadata ({papers['source'].value_counts().to_dict()})")
    print(f"[info] {len(papers):,} papers | lexicon v{LEXICON_VERSION} | {provenance}")

    matches = _stage("2 match concepts", match.match_papers, papers, None, concepts)
    save_table(matches, cfg.path("stage2", "matches"))

    shares = _stage("3 quarterly shares", aggregate.quarterly_shares, papers, matches,
                    cfg.start_year if not sample else 2016, cfg.density_floor, last_quarter, concepts)
    save_table(shares, cfg.path("stage3", "shares_quarterly"))
    yearly = aggregate.to_yearly(shares, cfg.density_floor)
    save_table(yearly, cfg.path("stage3", "shares_yearly"))

    trends_q = _stage("4 quarterly trends", evaluate.run_method, shares, cfg)
    save_table(trends_q, cfg.path("stage4", "trends_quarterly"))
    trends_y = _stage("4 yearly trends (arXiv)", yearly_trends, yearly, cfg)
    save_table(trends_y, cfg.path("stage4", "trends_yearly_arxiv"))

    results: Dict[str, pd.DataFrame] = {"shares_quarterly": shares, "trends_quarterly": trends_q}

    churn_df = trend.churn(trends_q)
    vt = trend.volatility_test(churn_df, LEXICON)
    save_table(churn_df, cfg.path("stage5", "churn"))
    write_json(cfg.path("stage5", "volatility_test.json"), vt)
    print(f"[info] H1b volatility test: {vt}")

    channel_trends = {"arxiv": trends_y}
    agreements = []
    for name in ("openalex", "github"):
        snap = _latest_snapshot(cfg, name)
        if snap is None:
            print(f"[info] no {name} snapshot yet: cross-channel check skipped for {name}")
            continue
        snap = snap[snap["concept_id"].isin(concepts)].copy()
        snap["sparse"] = snap["count"] < cfg.density_floor
        tr = yearly_trends(snap, cfg)
        channel_trends[name] = tr
        agreements.append(evaluate.channel_agreement(trends_y, tr, name))
    if agreements:
        agr = pd.concat(agreements, ignore_index=True)
        save_table(agr, cfg.path("stage5", "channel_agreement"))
        save_table(evaluate.order_of_arrival(channel_trends, concepts),
                   cfg.path("stage5", "order_of_arrival"))
        results["channel_agreement"] = agr

    if events_path:
        # Results are named after the events file, so the RQ1 check
        # (known_shift_events) and the RQ2 test (curriculum_events) never
        # overwrite each other.
        tag = _event_tag(events_path)
        events = evaluate.load_events(events_path)
        events = events[events["concept_id"].isin(concepts)]
        lt = _stage("5 lead times", evaluate.lead_times, trends_q, events, cfg)
        save_table(lt, cfg.path("stage5", f"lead_times_{tag}"))
        summary = evaluate.summarise(lt, cfg)
        write_json(cfg.path("stage5", f"lead_time_summary_{tag}.json"), summary)
        print(f"[info] lead-time summary for {tag} (sourced events only): {summary}")
        if not sample:
            save_table(_stage("5 baselines", evaluate.baselines, shares, events, cfg),
                       cfg.path("stage5", f"baselines_{tag}"))
            save_table(_stage("5 threshold sensitivity", evaluate.sensitivity, shares, events, cfg),
                       cfg.path("stage5", f"sensitivity_{tag}"))
        results["lead_times"] = lt

    md = report.render_markdown(trends_q, provenance, str(papers["v1_date"].max()))
    rp = cfg.path("stage6", "curriculum_review_report.md")
    rp.write_text(md)
    print(f"[OK  ] 6 report written to {rp}")
    results["papers_source"] = papers[["source"]].drop_duplicates()
    return results


def _event_tag(events_path: str) -> str:
    stem = Path(events_path).stem.lower()
    return "".join(ch if ch.isalnum() else "_" for ch in stem).strip("_") or "events"


def export(cfg: Config) -> Path:
    papers = arxiv.load_papers(cfg)
    tables = {"paper_ids": papers[["arxiv_id", "v1_date", "categories", "source"]]}
    lead_tables = sorted({p.name.split(".")[0] for p in (Path(cfg.data_dir) / "stage5").glob("lead_times_*")})
    for name, stage in ([("shares_quarterly", "stage3"), ("trends_quarterly", "stage4"),
                         ("channel_agreement", "stage5")] + [(n, "stage5") for n in lead_tables]):
        df = load_table(cfg.path(stage, name))
        if df is not None:
            tables[name] = df
    for prefix in ("openalex", "github"):
        snap = _latest_snapshot(cfg, prefix)
        if snap is not None:
            tables[f"{prefix}_snapshot"] = snap
    return export_bundle(cfg, tables, cfg.path("health_log.csv"))


# ------------------------------------------------------------------ demo
def demo(cfg: Config, base_papers: int = 1000) -> Dict[str, pd.DataFrame]:
    """Full dry run on synthetic data with planted signals. Not evidential."""
    papers, events = synthetic.generate(start_year=cfg.start_year, base_papers=base_papers)
    save_table(papers, cfg.path("stage1", "arxiv_papers"))
    ev_path = cfg.path("ground_truth", "synthetic_events.csv")
    events.to_csv(ev_path, index=False)
    print("[info] SYNTHETIC DEMO: numbers below test the machinery only; they are not findings.")
    return analyse(cfg, str(ev_path), last_quarter="2025Q4")


# ------------------------------------------------------- precision audit
def _excel_ok() -> bool:
    """True if pandas can write .xlsx (openpyxl is preinstalled on Colab)."""
    import importlib.util
    return importlib.util.find_spec("openpyxl") is not None


def audit_sheets(cfg: Config, n: int = 30, concepts: Optional[List[str]] = None) -> Path:
    """Write one sheet per concept with n random matched papers to judge by hand.

    Sheets are .xlsx when possible, because Google Drive can edit an .xlsx file
    in place (double-click it in Drive) and save straight back to the same file.
    Existing sheets are never overwritten, so your judgements are safe."""
    papers = arxiv.load_papers(cfg)
    matches = load_table(cfg.path("stage2", "matches"))
    if papers is None or matches is None:
        raise FileNotFoundError("run build and analyse before creating audit sheets")
    out_dir = Path(cfg.data_dir) / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = ".xlsx" if _excel_ok() else ".csv"
    written = 0
    for cid in concepts or list(LEXICON):
        if any((out_dir / f"{cid}{e}").exists() for e in (".xlsx", ".csv")):
            print(f"[audit] {cid}: sheet exists; not overwritten (your judgements are kept)")
            continue
        sheet = match.audit_sample(papers, matches, cid, n=n, seed=cfg.random_seed)
        path = out_dir / f"{cid}{ext}"
        if ext == ".xlsx":
            sheet.to_excel(path, index=False)
        else:
            sheet.to_csv(path, index=False)
        written += 1
    print(f"[audit] {written} new sheets in {out_dir}: type 1 (relevant) or 0 (not relevant) "
          "in the 'relevant' column")
    return out_dir


def audit_precision(cfg: Config) -> pd.DataFrame:
    """Precision per concept from the filled audit sheets (.xlsx or .csv)."""
    rows = []
    folder = Path(cfg.data_dir) / "audit"
    for p in sorted(list(folder.glob("*.xlsx")) + list(folder.glob("*.csv"))):
        if p.stem not in LEXICON:      # skip helper files such as human_check_150.xlsx
            continue
        df = pd.read_excel(p) if p.suffix == ".xlsx" else pd.read_csv(p)
        judged = pd.to_numeric(df["relevant"], errors="coerce").dropna()
        rows.append({"concept_id": p.stem, "judged": len(judged),
                     "precision": float(judged.mean()) if len(judged) else float("nan")})
    out = pd.DataFrame(rows, columns=["concept_id", "judged", "precision"])
    save_table(out, cfg.path("stage2", "audit_precision"))
    return out


# ------------------------------------------------ curriculum ground truth
def _find_mapping(cfg: Config, mapping_path: Optional[str]) -> Path:
    if mapping_path:
        return Path(mapping_path)
    folder = Path(cfg.data_dir) / "ground_truth"
    for name in ("cs2013_cs2023_mapping.xlsx", "cs2013_cs2023_mapping.csv"):
        if (folder / name).exists():
            return folder / name
    raise FileNotFoundError(
        f"no mapping found in {folder}. Put your filled cs2013_cs2023_mapping.xlsx there "
        "(see the Curriculum Mapping Guide), or pass --mapping <path>")


def build_events(cfg: Config, mapping_path: Optional[str] = None,
                 second_coder: Optional[str] = None) -> Path:
    """Read the hand-filled mapping and write ground_truth/curriculum_events.csv.

    Safe to run while the mapping is only partly filled: it reports progress,
    lists what is missing, and writes events only for completed rows."""
    src = _find_mapping(cfg, mapping_path)
    df, warnings = groundtruth.check_mapping(groundtruth.read_mapping(src))
    events, summary = groundtruth.mapping_to_events(df)
    out = cfg.path("ground_truth", "curriculum_events.csv")
    events.to_csv(out, index=False)
    checked = df[["concept_id", "cs2013_status", "cs2023_status", "derived_change", "problem"]]
    checked.to_csv(cfg.path("ground_truth", "mapping_check.csv"), index=False)

    print(f"[mapping] read {src}")
    print(f"[mapping] progress: {summary['complete']} of {summary['concepts_in_mapping']} concepts fully done (status and evidence)")
    print(f"[mapping] adoption events: {summary['adoption_events']}   decline events: "
          f"{summary['decline_events']}   negative controls: {summary['negative_controls']}   "
          f"unchanged (present in both): {summary['unchanged_present']}")
    if summary["tools_excluded"]:
        print(f"[mapping] tools absent from both curricula, excluded from controls: "
              f"{', '.join(summary['tools_excluded'])}")
    if summary["incomplete"]:
        print(f"[mapping] still to fill ({len(summary['incomplete'])}): {', '.join(summary['incomplete'])}")
    if summary["missing_evidence"]:
        print(f"[mapping] status given but evidence column empty (not counted as findings until filled): "
              f"{', '.join(summary['missing_evidence'])}")
    for w in warnings:
        print(f"[mapping] note: {w}")
    agree_ai = groundtruth.draft_agreement(df)
    if len(agree_ai) and agree_ai["concepts_compared"].sum():
        agree_ai.to_csv(cfg.path("ground_truth", "draft_agreement.csv"), index=False)
        print("[mapping] agreement between Claude's draft and your checked decisions:")
        print(agree_ai.to_string(index=False))
    if second_coder:
        other, _ = groundtruth.check_mapping(groundtruth.read_mapping(second_coder))
        agree = groundtruth.second_coder_agreement(df, other)
        agree.to_csv(cfg.path("ground_truth", "coder_agreement.csv"), index=False)
        print("[mapping] agreement with second coder:")
        print(agree.to_string(index=False))
    print(f"[mapping] wrote {out}")
    return out


# ------------------------------------------------------------- storage
STORAGE_LIMIT_GB = 10.0     # the owner's rule for a free 15 GB Google Drive
STORAGE_WARN_GB = 8.0


def storage_report(cfg: Config) -> pd.DataFrame:
    """Size of everything the system keeps in the data folder, largest first.

    Google Drive also counts its Trash, which this cannot see: empty the Trash
    of old LeadSignal files from time to time (Drive > Trash > search 'leadsignal')."""
    rows = []
    for p in Path(cfg.data_dir).rglob("*"):
        if p.is_file():
            rows.append({"file": str(p.relative_to(cfg.data_dir)), "mb": round(p.stat().st_size / 1e6, 2)})
    df = pd.DataFrame(rows, columns=["file", "mb"]).sort_values("mb", ascending=False).reset_index(drop=True)
    total_gb = df["mb"].sum() / 1000
    print(f"[storage] LeadSignal data folder: {total_gb:.2f} GB in {len(df)} files "
          f"(your limit {STORAGE_LIMIT_GB:.0f} GB)")
    if total_gb >= STORAGE_WARN_GB:
        print(f"[storage] WARNING: above {STORAGE_WARN_GB:.0f} GB. Stop and tell Claude before running anything else.")
    leftovers = df[df["file"].str.endswith(".tmp")]
    if len(leftovers):
        print(f"[storage] {len(leftovers)} unfinished .tmp file(s) from an interrupted save can be deleted: "
              f"{', '.join(leftovers['file'])}")
    print("[storage] Reminder: Google Drive also counts the Trash. Empty old LeadSignal files from it now and then.")
    return df
