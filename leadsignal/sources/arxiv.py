"""arXiv: the one live source.

Two independent routes to the same data:
  1. First build from Cornell's official metadata snapshot
     (arxiv-metadata-oai-snapshot.json, Kaggle dataset Cornell-University/arxiv).
     One file, no harvesting, no credentials.
  2. Incremental updates through OAI-PMH (metadataPrefix=arXiv), which needs
     no credentials either. OAI-PMH returns records by the date they were last
     modified, so revised old papers reappear: every merge de-duplicates by
     arXiv ID and keeps the FIRST-VERSION date.

Paper table columns: arxiv_id, v1_date (YYYY-MM-DD), categories, title,
abstract, source.
"""

from __future__ import annotations

import datetime as _dt
import email.utils
import gzip
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

import pandas as pd

from ..config import Config
from ..health import HealthLog
from ..store import load_table, read_json, save_table, write_json
from .http import PoliteClient, SourceUnavailable

PAPER_COLUMNS = ["arxiv_id", "v1_date", "categories", "title", "abstract", "source"]
OAI_NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "ax": "http://arxiv.org/OAI/arXiv/"}


# --------------------------------------------------------------------- helpers
def _clean(text: Optional[str]) -> str:
    return " ".join((text or "").split())


def _in_scope(categories: str, wanted: Iterable[str]) -> bool:
    cats = set(categories.split())
    return any(w in cats for w in wanted)


def _parse_created(value: str) -> Optional[str]:
    """Kaggle snapshot dates look like 'Mon, 2 Apr 2007 19:18:42 GMT'."""
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def merge_papers(old: Optional[pd.DataFrame], new: pd.DataFrame) -> pd.DataFrame:
    """Union of two paper tables, one row per arXiv ID.

    Keeps the earliest v1_date (a revision never moves a paper forward in time)
    and the most recent title/abstract text.
    """
    frames = [f for f in (old, new) if f is not None and len(f)]
    if not frames:
        return pd.DataFrame(columns=PAPER_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df["v1_date"] = df["v1_date"].astype(str)
    first_date = df.groupby("arxiv_id")["v1_date"].min()
    latest = df.drop_duplicates("arxiv_id", keep="last").set_index("arxiv_id")
    latest["v1_date"] = first_date
    return latest.reset_index()[PAPER_COLUMNS].sort_values(["v1_date", "arxiv_id"]).reset_index(drop=True)


# ------------------------------------------------------ route 1: the snapshot
def iter_snapshot(path: Path, cfg: Config) -> Iterator[dict]:
    """Stream the snapshot line by line, keeping only in-scope papers.
    Accepts the plain .json/.jsonl file or a gzip-compressed .gz file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"snapshot file not found: {path}")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            cats = rec.get("categories", "")
            if not _in_scope(cats, cfg.categories):
                continue
            versions = rec.get("versions") or []
            v1 = _parse_created(versions[0]["created"]) if versions else None
            if v1 is None or int(v1[:4]) < cfg.start_year:
                continue
            yield {
                "arxiv_id": str(rec["id"]), "v1_date": v1, "categories": cats,
                "title": _clean(rec.get("title")), "abstract": _clean(rec.get("abstract")),
                "source": "arxiv_snapshot",
            }


def build_from_snapshot(snapshot_path: Path, cfg: Config, chunk: int = 100_000) -> Path:
    """Filter the snapshot into the paper table. Safe to rerun."""
    base = cfg.path("stage1", "arxiv_papers")
    parts: List[pd.DataFrame] = []
    buf: List[dict] = []
    n = 0
    for rec in iter_snapshot(Path(snapshot_path), cfg):
        buf.append(rec)
        n += 1
        if len(buf) >= chunk:
            parts.append(pd.DataFrame(buf, columns=PAPER_COLUMNS))
            buf = []
            print(f"[arxiv] snapshot: {n:,} in-scope papers so far")
    if buf:
        parts.append(pd.DataFrame(buf, columns=PAPER_COLUMNS))
    new = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=PAPER_COLUMNS)
    merged = merge_papers(load_table(base), new)
    path = save_table(merged, base)
    # The snapshot's newest first-version date seeds the OAI-PMH checkpoint.
    ckpt = read_json(cfg.path("stage1", "oai_checkpoint.json"), {}) or {}
    if len(merged):
        ckpt["harvested_until"] = max(ckpt.get("harvested_until", "0000"), merged["v1_date"].max())
    write_json(cfg.path("stage1", "oai_checkpoint.json"), ckpt)
    print(f"[arxiv] snapshot build complete: {len(merged):,} papers -> {path}")
    return path


# ------------------------------------------------------- route 2: OAI-PMH
def choose_endpoint(cfg: Config, log: HealthLog, client: Optional[PoliteClient] = None) -> str:
    """Probe each configured OAI-PMH endpoint with Identify and pick the first
    one that answers. Every probe result is written to the health log."""
    client = client or PoliteClient(cfg.user_agent, cfg.request_timeout, 0.0, 2, 120)
    for ep in cfg.arxiv_oai_endpoints:
        try:
            body = client.get(ep, {"verb": "Identify"})
            if b"<Identify>" in body or b"Identify" in body:
                log.record("arxiv", "ok", "Identify answered", "using this endpoint", ep)
                return ep
            log.record("arxiv", "degraded", "unexpected Identify response", "trying next", ep)
        except SourceUnavailable as exc:
            log.record("arxiv", "unavailable", str(exc), "trying next", ep)
    raise SourceUnavailable("no arXiv OAI-PMH endpoint answered")


def parse_list_records(xml_bytes: bytes, cfg: Config):
    """Return (records, resumption_token, max_datestamp, error_code)."""
    root = ET.fromstring(xml_bytes)
    err = root.find("oai:error", OAI_NS)
    if err is not None:
        return [], None, None, err.get("code")
    records, max_stamp = [], None
    for rec in root.iterfind(".//oai:record", OAI_NS):
        stamp = rec.findtext("oai:header/oai:datestamp", default="", namespaces=OAI_NS)
        max_stamp = max(max_stamp or stamp, stamp)
        meta = rec.find("oai:metadata/ax:arXiv", OAI_NS)
        if meta is None:
            continue  # deleted record
        cats = meta.findtext("ax:categories", default="", namespaces=OAI_NS)
        created = meta.findtext("ax:created", default="", namespaces=OAI_NS)
        if not created or not _in_scope(cats, cfg.categories) or int(created[:4]) < cfg.start_year:
            continue
        records.append({
            "arxiv_id": meta.findtext("ax:id", default="", namespaces=OAI_NS),
            "v1_date": created[:10], "categories": cats,
            "title": _clean(meta.findtext("ax:title", default="", namespaces=OAI_NS)),
            "abstract": _clean(meta.findtext("ax:abstract", default="", namespaces=OAI_NS)),
            "source": "arxiv_oai",
        })
    tok_el = root.find(".//oai:resumptionToken", OAI_NS)
    token = tok_el.text.strip() if tok_el is not None and tok_el.text else None
    return records, token, max_stamp, None


def _token_date(token: Optional[str]) -> Optional[str]:
    """arXiv resumption tokens carry the harvest position as from=YYYY-MM-DD."""
    if not token:
        return None
    m = re.search(r"from=(\d{4}-\d{2}-\d{2})", urllib.parse.unquote(token))
    return m.group(1) if m else None


def _resume_date(cfg: Config, ckpt: dict) -> Optional[_dt.date]:
    """Where to restart if there is no usable token: the last completed harvest,
    else the position stored in the last token, else the newest paper we hold."""
    for value in (ckpt.get("harvested_until"), ckpt.get("position_date"), _token_date(ckpt.get("token"))):
        if value:
            return _dt.date.fromisoformat(str(value)[:10])
    papers = load_papers(cfg)
    if papers is not None and len(papers):
        return _dt.date.fromisoformat(str(papers["v1_date"].max())[:10])
    return None


def update_from_oai(cfg: Config, log: HealthLog, overlap_days: int = 7,
                    client: Optional[PoliteClient] = None, max_pages: Optional[int] = None) -> Path:
    """Fetch records changed since the last checkpoint, merge, save.

    The checkpoint stores the resumption token after every page, so an
    interrupted run continues where it stopped. If the token has expired the
    run restarts from the date, and de-duplication absorbs the overlap.
    """
    ckpt_path = cfg.path("stage1", "oai_checkpoint.json")
    ckpt = read_json(ckpt_path, {}) or {}
    base = cfg.path("stage1", "arxiv_papers")
    client = client or PoliteClient(cfg.user_agent, cfg.request_timeout, cfg.arxiv_delay_seconds,
                                    cfg.max_consecutive_failures, cfg.time_budget_seconds)
    endpoint = ckpt.get("endpoint") if ckpt.get("token") else None
    endpoint = endpoint or choose_endpoint(cfg, log, client)

    start = _resume_date(cfg, ckpt)
    start = start - _dt.timedelta(days=overlap_days) if start else _dt.date(cfg.start_year, 1, 1)
    frm = start.isoformat()
    token = ckpt.get("token")
    pages, new_rows, max_stamp = 0, [], ckpt.get("harvested_until")
    tried_date = False
    print(f"[arxiv] OAI-PMH update from {frm} via {endpoint}" + (" (resuming token)" if token else ""))

    try:
        while True:
            params = ({"verb": "ListRecords", "resumptionToken": token} if token else
                      {"verb": "ListRecords", "metadataPrefix": "arXiv", "set": "cs", "from": frm})
            try:
                body = client.get(endpoint, params)
            except SourceUnavailable as exc:
                # A stored token from an earlier run may have expired. arXiv either
                # rejects it (HTTP 4xx) or lets the request hang, so on the first
                # page of a run any failure with a stored token restarts from the date.
                if token and ("HTTP 4" in str(exc) or (pages == 0 and not tried_date)):
                    print("[arxiv] resumption token not accepted; restarting from the checkpoint date")
                    token, tried_date = None, True
                    if hasattr(client, "_failures"):
                        client._failures = 0
                    continue
                raise
            records, token, stamp, err = parse_list_records(body, cfg)
            if err == "noRecordsMatch":
                break
            if err:
                raise SourceUnavailable(f"OAI-PMH error {err}")
            new_rows.extend(records)
            if stamp:
                max_stamp = max(max_stamp or stamp, stamp)
            pages += 1
            if pages % 10 == 0 or not token:
                _flush(base, new_rows)
                new_rows = []
                ckpt.update({"endpoint": endpoint, "token": token, "pages_this_run": pages,
                             "position_date": _token_date(token) or ckpt.get("position_date")})
                write_json(ckpt_path, ckpt)
                print(f"[arxiv] {pages} pages processed")
            if not token or (max_pages and pages >= max_pages):
                break
    except SourceUnavailable as exc:
        _flush(base, new_rows)
        log.record("arxiv", "degraded", f"stopped early: {exc}", "rerun update to resume", endpoint)
        raise
    _flush(base, new_rows)
    if token:  # stopped early on purpose (max_pages): keep the token so the next run resumes
        ckpt.update({"endpoint": endpoint, "token": token, "pages_this_run": pages,
                     "position_date": _token_date(token) or ckpt.get("position_date")})
    else:
        ckpt.update({"token": None, "harvested_until": max_stamp or frm,
                     "last_completed_utc": _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
                     .isoformat(timespec="seconds")})
    write_json(ckpt_path, ckpt)
    log.record("arxiv", "ok", f"update finished: {pages} pages", "", endpoint)
    return base


def _parts_dir(base: Path) -> Path:
    return Path(base).parent / "arxiv_parts"


def _flush(base: Path, rows: List[dict]) -> None:
    """Save new rows as a small new part file.

    The main table is never rewritten during a harvest. On Google Drive every
    rewrite of a large file leaves the old copy in the Trash, which filled the
    owner's storage during the first real run (2026-10-30)."""
    if not rows:
        return
    folder = _parts_dir(base)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    save_table(merge_papers(None, pd.DataFrame(rows, columns=PAPER_COLUMNS)), folder / f"part-{stamp}")


def load_papers(cfg: Config) -> Optional[pd.DataFrame]:
    """The full paper table: the main file plus every part saved since, de-duplicated."""
    base = cfg.path("stage1", "arxiv_papers")
    frames = [load_table(base)]
    folder = _parts_dir(base)
    if folder.exists():
        for p in sorted(folder.glob("part-*")):
            if p.name.endswith(".tmp"):
                continue
            frames.append(pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, dtype=str))
    frames = [f for f in frames if f is not None and len(f)]
    if not frames:
        return None
    out = frames[0]
    for f in frames[1:]:
        out = merge_papers(out, f)
    return out
