"""Regression tests for LeadSignal-CS.

Run with either:
    python tests/test_leadsignal.py
    python -m pytest -q tests
No network access is needed: all source adapters are tested with fake clients.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import urllib.error
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from leadsignal import aggregate, evaluate, groundtruth, lexicon, match, synthetic, trend  # noqa: E402
from leadsignal.config import Config  # noqa: E402
from leadsignal.export import SyntheticDataError, export_bundle  # noqa: E402
from leadsignal.health import HealthLog  # noqa: E402
from leadsignal.sources import arxiv, github, openalex  # noqa: E402
from leadsignal.sources.http import PoliteClient, SourceUnavailable  # noqa: E402


def _cfg(tmp):
    return Config(data_dir=str(tmp), end_year=2025)


# ---------------------------------------------------------------- lexicon
def test_lexicon_is_consistent():
    assert lexicon.validate() == []
    assert len(lexicon.LEXICON) == 50
    assert lexicon.counts_by_class() == {"stable": 15, "moderate": 20, "volatile": 15}


# --------------------------------------------------------------- matching
def test_matching_rules():
    L = lexicon.LEXICON
    assert match.match_text("We fine-tune a large language model.", L["large_language_models"])
    assert match.match_text("Two LLMs are compared.", L["large_language_models"])          # plural
    assert not match.match_text("the llm of the text", L["large_language_models"])        # acronym case
    assert match.match_text("chain of thought prompting", L["prompt_engineering"])        # hyphen/space
    assert match.match_text("We use React Native for the app", L["react_framework"])
    assert not match.match_text("a ReAct agent with ReactJS", L["react_framework"])      # exclusion veto
    assert not match.match_text("information diffusion in social graphs, diffusion model",
                                L["diffusion_models"])                                    # exclusion veto
    assert match.match_text("over TCP/IP networks", L["networking_fundamentals"])
    assert not match.match_text("PyTorchX is a toy", L["pytorch"])                        # whole word
    assert match.match_text("Trained in PyTorch.", L["pytorch"])


def test_match_papers_long_table():
    papers = pd.DataFrame({"arxiv_id": ["1", "2"], "title": ["PyTorch study", "Graph theory"],
                           "abstract": ["uses Docker", ""]})
    m = match.match_papers(papers)
    got = set(map(tuple, m[["arxiv_id", "concept_id"]].to_numpy()))
    assert ("1", "pytorch") in got and ("1", "docker") in got and ("2", "discrete_mathematics") in got


# ------------------------------------------------------------- arXiv data
def test_merge_keeps_first_version_date_and_dedupes():
    old = pd.DataFrame([{"arxiv_id": "a", "v1_date": "2019-01-05", "categories": "cs.LG",
                         "title": "old", "abstract": "old", "source": "arxiv_snapshot"}])
    new = pd.DataFrame([{"arxiv_id": "a", "v1_date": "2024-02-01", "categories": "cs.LG",
                         "title": "revised", "abstract": "revised", "source": "arxiv_oai"},
                        {"arxiv_id": "b", "v1_date": "2024-02-02", "categories": "cs.AI",
                         "title": "b", "abstract": "b", "source": "arxiv_oai"}])
    m = arxiv.merge_papers(old, new)
    assert len(m) == 2
    row = m.set_index("arxiv_id").loc["a"]
    assert row["v1_date"] == "2019-01-05" and row["title"] == "revised"


def test_snapshot_filtering(tmp_path=None):
    tmp = Path(tmp_path or tempfile.mkdtemp())
    recs = [
        {"id": "1", "categories": "cs.LG stat.ML", "title": "A", "abstract": "x",
         "versions": [{"version": "v1", "created": "Mon, 2 Apr 2018 19:18:42 GMT"}]},
        {"id": "2", "categories": "math.CO", "title": "B", "abstract": "y",
         "versions": [{"version": "v1", "created": "Mon, 2 Apr 2018 19:18:42 GMT"}]},
        {"id": "3", "categories": "cs.AI", "title": "C", "abstract": "z",
         "versions": [{"version": "v1", "created": "Tue, 3 Apr 2007 10:00:00 GMT"}]},
    ]
    p = tmp / "snap.json"
    p.write_text("\n".join(json.dumps(r) for r in recs))
    out = list(arxiv.iter_snapshot(p, _cfg(tmp)))
    assert [r["arxiv_id"] for r in out] == ["1"] and out[0]["v1_date"] == "2018-04-02"
    import gzip as _gz
    gz = tmp / "snap.jsonl.gz"
    with _gz.open(gz, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in recs))
    assert [r["arxiv_id"] for r in arxiv.iter_snapshot(gz, _cfg(tmp))] == ["1"]


OAI_PAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>
 <record><header><identifier>oai:arXiv.org:2401.00001</identifier><datestamp>2024-01-10</datestamp></header>
  <metadata><arXiv xmlns="http://arxiv.org/OAI/arXiv/"><id>2401.00001</id><created>2024-01-02</created>
   <title>Retrieval  augmented
   generation</title><categories>cs.CL cs.AI</categories><abstract>We study RAG.</abstract></arXiv></metadata></record>
 <record><header><identifier>oai:arXiv.org:1501.00002</identifier><datestamp>2024-01-11</datestamp></header>
  <metadata><arXiv xmlns="http://arxiv.org/OAI/arXiv/"><id>1501.00002</id><created>2015-01-05</created>
   <title>Old paper revised</title><categories>cs.DS</categories><abstract>x</abstract></arXiv></metadata></record>
 <record><header status="deleted"><identifier>oai:arXiv.org:x</identifier><datestamp>2024-01-12</datestamp></header></record>
 <resumptionToken cursor="0" completeListSize="3">TOKEN123</resumptionToken>
</ListRecords></OAI-PMH>"""


def test_oai_parsing():
    recs, token, stamp, err = arxiv.parse_list_records(OAI_PAGE, _cfg(tempfile.mkdtemp()))
    assert err is None and token == "TOKEN123" and stamp == "2024-01-12"
    assert len(recs) == 1 and recs[0]["arxiv_id"] == "2401.00001"
    assert recs[0]["title"] == "Retrieval augmented generation"  # whitespace normalised
    none = b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><error code="noRecordsMatch"/></OAI-PMH>'
    assert arxiv.parse_list_records(none, _cfg(tempfile.mkdtemp()))[3] == "noRecordsMatch"


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_oai_update_with_fake_client():
    tmp = Path(tempfile.mkdtemp())
    cfg = _cfg(tmp)
    pages = [b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><Identify/></OAI-PMH>',
             OAI_PAGE,
             OAI_PAGE.replace(b"TOKEN123", b"").replace(b"2401.00001", b"2401.00009")]
    calls = []

    def opener(req, timeout):
        calls.append(req.full_url)
        return _FakeResp(pages[min(len(calls) - 1, len(pages) - 1)])

    client = PoliteClient("test", min_interval=0, opener=opener)
    log = HealthLog(cfg.path("health_log.csv"))
    arxiv.update_from_oai(cfg, log, client=client)
    papers = arxiv.load_papers(cfg)
    assert set(papers["arxiv_id"]) == {"2401.00001", "2401.00009"}
    # the main table is never rewritten during a harvest: new rows go to small part files
    assert not cfg.path("stage1", "arxiv_papers").with_suffix(".parquet").exists()
    assert list((tmp / "stage1" / "arxiv_parts").glob("part-*.parquet"))
    ckpt = json.loads(cfg.path("stage1", "oai_checkpoint.json").read_text())
    assert ckpt["token"] is None and ckpt["harvested_until"] == "2024-01-12"
    assert "resumptionToken=TOKEN123" in calls[2]

    # A run stopped on purpose after one page must keep the token, and the next run resumes from it.
    tmp2 = Path(tempfile.mkdtemp())
    cfg2 = _cfg(tmp2)
    calls.clear()
    arxiv.update_from_oai(cfg2, HealthLog(cfg2.path("health_log.csv")), client=client, max_pages=1)
    ckpt2 = json.loads(cfg2.path("stage1", "oai_checkpoint.json").read_text())
    assert ckpt2["token"] == "TOKEN123"


# ------------------------------------------------------------------- http
def test_circuit_breaker_and_budget():
    def failing(req, timeout):
        raise urllib.error.URLError("down")
    c = PoliteClient("t", min_interval=0, max_consecutive_failures=2, opener=failing)
    import leadsignal.sources.http as h
    orig = h.time.sleep
    h.time.sleep = lambda s: None
    try:
        try:
            c.get("http://x")
            raise AssertionError("should have raised")
        except SourceUnavailable as exc:
            assert "circuit breaker" in str(exc)
        c2 = PoliteClient("t", min_interval=0, time_budget_seconds=-1, opener=failing)
        try:
            c2.get("http://x")
            raise AssertionError("should have raised")
        except SourceUnavailable as exc:
            assert "budget" in str(exc)
    finally:
        h.time.sleep = orig


# ------------------------------------------------------------- statistics
def test_mann_kendall_matches_pymannkendall():
    try:
        import pymannkendall as pmk
    except ImportError:
        print("  (pymannkendall not installed: cross-check skipped)")
        return
    rng = np.random.default_rng(1)
    checked = 0
    for _ in range(200):
        x = np.cumsum(rng.normal(0.1, 1, rng.integers(8, 30)))
        ours = trend.mann_kendall_hr(x)
        ref = pmk.hamed_rao_modification_test(x)
        if not ours["corrected"] or ref.var_s <= 0:
            continue
        assert abs(ours["p"] - ref.p) < 1e-9 and abs(ours["slope"] - ref.slope) < 1e-12
        checked += 1
    assert checked > 100


def test_benjamini_hochberg():
    p = pd.Series([0.01, 0.04, 0.03, 0.5])
    adj = trend.benjamini_hochberg(p)
    assert np.allclose(adj.to_numpy(), [0.04, 0.0533333, 0.0533333, 0.5], atol=1e-6)


# ------------------------------------------------------ shares and trends
def test_shares_zero_filled_and_normalised():
    papers = pd.DataFrame({"arxiv_id": ["a", "b", "c", "c"],
                           "v1_date": ["2016-01-10", "2016-02-10", "2016-05-01", "2016-05-01"],
                           "title": "", "abstract": ""})
    matches = pd.DataFrame({"arxiv_id": ["a", "c"], "concept_id": ["pytorch", "pytorch"]})
    sh = aggregate.quarterly_shares(papers, matches, 2016, 1, last_quarter="2016Q3",
                                    concepts=["pytorch", "algorithms"])
    s = sh.set_index(["concept_id", "period"])
    assert s.loc[("pytorch", "2016Q1"), "share"] == 0.5
    assert s.loc[("pytorch", "2016Q2"), "share"] == 1.0          # duplicate row counted once
    assert s.loc[("algorithms", "2016Q3"), "count"] == 0 and s.loc[("pytorch", "2016Q3"), "total"] == 0


def _synthetic_run(base=1000):
    papers, events = synthetic.generate(base_papers=base)
    m = match.match_papers(papers)
    shares = aggregate.quarterly_shares(papers, m, 2012, 5, last_quarter="2025Q4")
    return papers, events, shares


_CACHE = {}


def _cached():
    if "run" not in _CACHE:
        _CACHE["run"] = _synthetic_run()
    return _CACHE["run"]


def test_detrending_absorbs_field_wide_surge():
    _, _, shares = _cached()
    cfg = _cfg(tempfile.mkdtemp())
    det = evaluate.run_method(shares, cfg)
    raw = evaluate.run_method(shares, cfg, detrend=False)
    window = lambda t: t[(t["period"] >= "2023Q3") & (t["period"] <= "2024Q2")]
    n_det = (window(det)["label"] == "rising").sum()
    n_raw = (window(raw)["label"] == "rising").sum()
    assert n_raw > 5 * max(n_det, 1), (n_det, n_raw)


def test_planted_leads_are_recovered():
    _, events, shares = _cached()
    cfg = _cfg(tempfile.mkdtemp())
    lt = evaluate.lead_times(evaluate.run_method(shares, cfg), events, cfg)
    rises = lt[lt["event_type"] == "adoption"]
    assert (rises["status"] == "detected").sum() >= 4
    assert rises["lead"].dropna().between(1, 8).all(), rises[["concept_id", "lead"]]
    s = evaluate.summarise(lt, cfg)
    assert s["median_lead_quarters"] > 0


def test_lead_time_rules():
    cfg = _cfg(tempfile.mkdtemp())
    periods = [str(p) for p in pd.period_range("2016Q1", "2019Q4", freq="Q")]
    labels = ["insufficient"] * 4 + ["stable"] * 4 + ["rising", "stable", "rising", "rising"] + ["rising"] * 4
    conf = [False] * 8 + [True, False, True, True] + [True] * 4
    tr = pd.DataFrame({"concept_id": "x", "period": periods, "label": labels, "confirmed": conf,
                       "sparse": False})
    ev = pd.DataFrame([
        {"concept_id": "x", "event_period": "2019Q2", "event_type": "adoption", "citation_status": "sourced"},
        {"concept_id": "x", "event_period": "2016Q3", "event_type": "adoption", "citation_status": "sourced"},
        {"concept_id": "x", "event_period": "2030Q1", "event_type": "adoption", "citation_status": "sourced"},
        {"concept_id": "x", "event_period": "", "event_type": "none", "citation_status": "sourced"},
    ])
    lt = evaluate.lead_times(tr, ev, cfg)
    # 2018Q1 is a one-quarter blip; persistence of 2 makes 2018Q3 the detection.
    assert lt.loc[0, "detect_period"] == "2018Q3" and lt.loc[0, "lead"] == 3
    assert lt.loc[1, "status"].startswith("unevaluable: too little history")
    assert lt.loc[2, "status"].startswith("unevaluable: event after")
    assert lt.loc[3, "status"] == "false_alarm"


def test_volatility_test_runs():
    _, _, shares = _cached()
    cfg = _cfg(tempfile.mkdtemp())
    ch = trend.churn(evaluate.run_method(shares, cfg))
    vt = trend.volatility_test(ch, lexicon.LEXICON)
    assert vt["median_var_e_volatile"] > vt["median_var_e_stable"]


# ----------------------------------------------------- validation sources
class _FakeJSONClient:
    def __init__(self, fn):
        self.fn = fn

    def get_json(self, url, params=None):
        return self.fn(url, params or {})


def test_openalex_snapshot_with_fake_client():
    tmp = Path(tempfile.mkdtemp())
    cfg = _cfg(tmp)
    cfg.start_year = 2023
    def fn(url, params):
        f = params["filter"]
        assert "primary_location.source.type:journal|conference" in f  # preprints excluded
        if "title_and_abstract.search" in f:
            return {"group_by": [{"key": "2023", "count": 10}, {"key": "2024", "count": 30}]}
        return {"group_by": [{"key": "2023", "count": 1000}, {"key": "2024", "count": 1000}]}
    df = openalex.snapshot(cfg, HealthLog(cfg.path("h.csv")), _FakeJSONClient(fn), ["pytorch"])
    assert list(df["share"]) == [0.01, 0.03] and (df["source"] == "openalex").all()


def test_github_snapshot_handles_outage():
    tmp = Path(tempfile.mkdtemp())
    cfg = _cfg(tmp)
    def fn(url, params):
        raise SourceUnavailable("HTTP 403 rate limited")
    log = HealthLog(cfg.path("h.csv"))
    assert github.snapshot(cfg, log, _FakeJSONClient(fn), ["pytorch"]) is None
    assert log.last_status("github") == "unavailable"


def test_health_log_flags_after_repeated_outages():
    log = HealthLog(Path(tempfile.mkdtemp()) / "h.csv")
    for _ in range(3):
        log.record("openalex", "unavailable", "HTTP 429")
    log.record("arxiv", "ok")
    assert log.needs_decision("openalex", 3) and not log.needs_decision("arxiv", 3)


# ------------------------------------------------------------------ export
def test_export_refuses_synthetic():
    cfg = _cfg(tempfile.mkdtemp())
    df = pd.DataFrame({"arxiv_id": ["x"], "source": ["synthetic"]})
    try:
        export_bundle(cfg, {"paper_ids": df}, cfg.path("health_log.csv"))
        raise AssertionError("should have refused")
    except SyntheticDataError:
        pass


def test_export_writes_manifest():
    cfg = _cfg(tempfile.mkdtemp())
    df = pd.DataFrame({"arxiv_id": ["x"], "source": ["arxiv_oai"]})
    out = export_bundle(cfg, {"paper_ids": df}, cfg.path("health_log.csv"))
    man = json.loads((out / "MANIFEST.json").read_text())
    assert "paper_ids.csv" in man["files"] and man["lexicon_version"] == lexicon.LEXICON_VERSION


# ------------------------------------------------- curriculum ground truth
def _mapping(rows):
    df = groundtruth.blank_mapping()
    for cid, s13, e13, s23, e23 in rows:
        i = df.index[df["concept_id"] == cid][0]
        df.loc[i, ["cs2013_status", "cs2013_evidence", "cs2023_status", "cs2023_evidence"]] = [s13, e13, s23, e23]
    return df


def test_change_rule_table():
    d = groundtruth.derive_change
    assert d("absent", "core") == d("minor", "core") == "adoption"
    assert d("absent", "minor") == "expansion"
    assert d("core", "minor") == "reduction"
    assert d("core", "absent") == d("minor", "absent") == "removal"
    assert all(d(s, s) == "none" for s in groundtruth.STATUSES)


def test_mapping_to_events_rules():
    tmp = Path(tempfile.mkdtemp())
    rows = [("large_language_models", "absent", "", "core", "AI-ML 8.b"),
            ("data_structures", "core", "AL p1", "minor", "AL p2"),
            ("quantum_computing", "absent", "searched", "absent", "searched"),
            ("pytorch", "absent", "searched", "absent", "searched"),
            ("algorithms", "core", "AL p1", "core", "AL p2"),
            ("devops", "absent", "", "core", "")]           # evidence missing
    path = tmp / "m.csv"
    _mapping(rows).assign(cs2013_status=lambda d: d["cs2013_status"].str.upper()).to_csv(path, index=False)
    df, warnings = groundtruth.check_mapping(groundtruth.read_mapping(path))  # case-insensitive
    ev, summary = groundtruth.mapping_to_events(df)
    got = dict(zip(ev["concept_id"], ev["event_type"] + "/" + ev["layer"]))
    assert got == {"large_language_models": "adoption/systematic", "data_structures": "decline/systematic",
                   "quantum_computing": "none/negative_control", "devops": "adoption/systematic"}, got
    assert summary["tools_excluded"] == ["pytorch"] and summary["unchanged_present"] == 1
    assert ev.set_index("concept_id").loc["devops", "citation_status"] == "requires_citation"
    assert summary["complete"] == 5 and len(summary["incomplete"]) == 44
    assert list(ev.columns) == evaluate.EVENT_COLUMNS
    evaluate.load_events(_write(ev, tmp / "ev.csv"))  # the analysis accepts it


def _write(df, path):
    df.to_csv(path, index=False)
    return path


def test_second_coder_kappa():
    a = _mapping([("algorithms", "core", "x", "core", "x"), ("devops", "absent", "", "core", "x"),
                  ("pytorch", "absent", "", "absent", "")])
    b = _mapping([("algorithms", "core", "x", "core", "x"), ("devops", "absent", "", "minor", "x"),
                  ("pytorch", "absent", "", "absent", "")])
    out = groundtruth.second_coder_agreement(a, b).set_index("curriculum")
    assert out.loc["CS2013", "percent_agreement"] == 1.0 and out.loc["CS2023", "disagreements"] == "devops"


def test_mapping_workbook_builds_and_reads_back():
    import importlib.util
    if importlib.util.find_spec("openpyxl") is None:
        return  # optional: only where openpyxl is installed (it is on Colab)
    sys.path.insert(0, str(ROOT / "tools"))
    import make_mapping_workbook as mk
    out = Path(tempfile.mkdtemp()) / "w.xlsx"
    mk.build(out)
    mk.build(out)  # second call must not overwrite
    df = groundtruth.read_mapping(out)
    assert len(df) == 50 and set(df["concept_id"]) == set(lexicon.LEXICON)
    chk = Path(tempfile.mkdtemp()) / "c.xlsx"
    mk.build_checking(chk, ROOT / "data" / "ground_truth" / groundtruth.DRAFT_FILE)
    df = groundtruth.read_mapping(chk)
    assert (df["cs2013_status"] != "").all() and (df["check_2013"] == "").all()
    assert (df["claude_draft_2023"] == df["cs2023_status"]).all()


def test_checking_workflow_requires_checks_and_reports_agreement():
    draft = pd.read_csv(ROOT / "data" / "ground_truth" / groundtruth.DRAFT_FILE, dtype=str).fillna("")
    assert len(draft) == 50 and set(draft["concept_id"]) == set(lexicon.LEXICON)
    assert set(draft["cs2013_status"]) <= set(groundtruth.STATUSES)
    assert set(draft["cs2023_status"]) <= set(groundtruth.STATUSES)
    frame = groundtruth.prefilled_mapping(draft)
    df, _ = groundtruth.check_mapping(frame)
    assert (df["problem"] != "").all()                     # nothing counts until checked
    frame["check_2013"] = "OK"
    frame["check_2023"] = "OK"
    i = frame.index[frame["concept_id"] == "agile_methodologies"][0]
    frame.loc[i, ["cs2023_status", "check_2023"]] = ["absent", "changed"]
    tmp = Path(tempfile.mkdtemp()) / "m.csv"
    frame.to_csv(tmp, index=False)
    df, warnings = groundtruth.check_mapping(groundtruth.read_mapping(tmp))
    assert (df["problem"] == "").all() and not warnings, warnings
    ev, summary = groundtruth.mapping_to_events(df)
    assert "agile_methodologies" in set(ev.loc[ev["event_type"] == "decline", "concept_id"])
    agree = groundtruth.draft_agreement(df).set_index("curriculum")
    assert agree.loc["CS2013", "percent_agreement"] == 1.0
    assert agree.loc["CS2023", "disagreements"] == "agile_methodologies"


def test_resume_position_from_token_and_storage_report():
    tok = "verb%3DListRecords%26metadataPrefix%3DarXiv%26from%3D2026-08-24%26set%3Dcs%26skip%3D677"
    assert arxiv._token_date(tok) == "2026-08-24"
    cfg = _cfg(tempfile.mkdtemp())
    assert arxiv._resume_date(cfg, {"token": tok}).isoformat() == "2026-08-24"
    assert arxiv._resume_date(cfg, {}) is None
    arxiv._flush(cfg.path("stage1", "arxiv_papers"), [{"arxiv_id": "a", "v1_date": "2025-03-01", "categories": "cs.LG",
                                                        "title": "t", "abstract": "x", "source": "arxiv_oai"}])
    assert arxiv._resume_date(cfg, {}).isoformat() == "2025-03-01"
    from leadsignal import pipeline
    rep = pipeline.storage_report(cfg)
    assert len(rep) >= 1 and rep["mb"].sum() < 1


# ------------------------------------------------------------- code hygiene
def test_no_silent_exception_handlers():
    bad = []
    for p in (ROOT / "leadsignal").rglob("*.py"):
        src = p.read_text()
        if re.search(r"except[^\n]*:\s*\n\s*pass\b", src):
            bad.append(p.name)
        if re.search(r"\bexcept\s*:", src):
            bad.append(p.name)
    assert not bad, bad


def test_core_needs_only_numpy_pandas_scipy():
    allowed = {"numpy", "pandas", "scipy", "pyarrow", "leadsignal"}
    stdlib = set(sys.stdlib_module_names)
    for p in (ROOT / "leadsignal").rglob("*.py"):
        for mod in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", p.read_text(), re.M):
            assert mod in allowed or mod in stdlib or mod == "__future__", (p.name, mod)


# ------------------------------------------------------------------ runner
if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
        except Exception as exc:  # report every failure, never hide it
            failed += 1
            print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
    print(f"\n  {len(tests) - failed}/{len(tests)} checks passed")
    sys.exit(1 if failed else 0)
