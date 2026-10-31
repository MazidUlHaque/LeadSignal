"""Curriculum ground truth: turn the hand-filled CS2013 -> CS2023 mapping into
an events file (proposal Section 4.4, Layer 1).

You fill ONE thing by hand: the mapping workbook
(cs2013_cs2023_mapping.xlsx, sheet "Mapping"). For every concept you record
its status in each curriculum (absent, minor or core) and where you found it.
Everything after that is mechanical and done here, so no rule can be bent
after seeing results:

  * change  = derived from the two statuses (your typed value is only checked)
  * adoption / expansion      -> event_type "adoption"
  * reduction / removal       -> event_type "decline"
  * absent in both, kind topic -> negative control (event_type "none")
  * absent in both, kind tool  -> excluded (curriculum guidelines do not name
    products by design, so a tool's absence is not evidence of non-adoption)

Rule amendment 2026-09-25 (before any lead-time analysis): tools are no longer
used as negative controls. See data/ground_truth/README.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .evaluate import EVENT_COLUMNS, cohen_kappa
from .lexicon import LEXICON

STATUSES = ("absent", "minor", "core")
RANK = {s: i for i, s in enumerate(STATUSES)}
CHANGES = ("adoption", "expansion", "reduction", "removal", "none")
EVENT_PERIOD = "2024Q1"  # CS2023 final report, endorsed January-February 2024

# Same wording as the proposal's reference list.
CITATION_2013 = ("ACM/IEEE-CS Joint Task Force on Computing Curricula. (2013). "
                 "Computer science curricula 2013. https://doi.org/10.1145/2534860")
CITATION_2023 = ("ACM/IEEE-CS/AAAI Joint Task Force. (2024). "
                 "Computer science curricula 2023. https://doi.org/10.1145/3664191")

# Products and frameworks. Curriculum guidelines avoid naming these on purpose.
TOOL_CONCEPTS = {"tensorflow", "pytorch", "kubernetes", "docker", "react_framework", "aws_services"}

# Words to type into Ctrl+F when reading the two curriculum PDFs.
SEARCH_TERMS: Dict[str, str] = {
    "algorithms": "algorithm; algorithmic strategies; sorting; searching",
    "data_structures": "data structure; stack; queue; hash table; tree; graph",
    "computational_complexity": "complexity; asymptotic; Big O; NP-complete; P vs NP",
    "discrete_mathematics": "discrete; logic; sets; relations; combinatorics; proof",
    "formal_languages": "automata; regular expression; context-free; Turing machine; formal language",
    "computer_architecture": "architecture; processor; pipelining; memory hierarchy; instruction set",
    "operating_systems": "operating system; process; scheduling; virtual memory; file system",
    "networking_fundamentals": "network; protocol; TCP; routing; layering",
    "database_theory": "database; relational; SQL; normalization; transaction",
    "software_engineering": "software engineering; requirements; testing; software process",
    "object_oriented_programming": "object-oriented; class; inheritance; polymorphism",
    "functional_programming": "functional programming; higher-order; lambda; immutable",
    "compiler_design": "compiler; parsing; code generation; lexical analysis",
    "linear_algebra": "linear algebra; matrix; vector; eigen",
    "probability_statistics": "probability; statistics; random variable; distribution",
    "machine_learning": "machine learning; supervised; classification; training data",
    "deep_learning": "deep learning; neural network; convolutional",
    "natural_language_processing": "natural language; NLP; language model; text processing",
    "computer_vision": "computer vision; image; perception; object recognition",
    "cloud_computing": "cloud; IaaS; PaaS; SaaS; virtualization",
    "devops": "DevOps; continuous integration; continuous delivery; deployment",
    "agile_methodologies": "agile; Scrum; sprint; Kanban; extreme programming",
    "microservices": "microservice; service-oriented; SOA",
    "containerisation": "container; containerization",
    "cybersecurity": "security; cryptography; threat; attack; vulnerability",
    "data_engineering": "data pipeline; ETL; data warehouse; big data; data engineering",
    "nosql_databases": "NoSQL; key-value; document store; non-relational",
    "api_design": "API; application programming interface; REST; web service",
    "parallel_computing": "parallel; concurrency; GPU; multicore; speedup",
    "distributed_systems": "distributed; consensus; fault tolerance; replication",
    "reinforcement_learning": "reinforcement learning; Markov decision; reward; policy",
    "explainable_ai": "explainable; explainability; interpretab; transparency",
    "graph_neural_networks": "graph neural network; GNN; graph embedding",
    "quantum_computing": "quantum; qubit",
    "ai_ethics": "ethics; bias; fairness; responsible AI",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "kubernetes": "Kubernetes; orchestration",
    "docker": "Docker",
    "react_framework": "React; front-end framework",
    "large_language_models": "large language model; LLM; generative",
    "transformer_architectures": "transformer; attention mechanism; BERT; GPT",
    "prompt_engineering": "prompt; prompt engineering",
    "aws_services": "AWS; Amazon Web Services",
    "mlops": "MLOps; model deployment; machine learning operations",
    "vector_databases": "vector database; embedding; similarity search",
    "retrieval_augmented_generation": "retrieval-augmented; RAG; retrieval",
    "diffusion_models": "diffusion model; image generation; generative model",
    "edge_computing": "edge computing; fog computing; IoT",
    "federated_learning": "federated learning; privacy-preserving learning",
}

MAPPING_COLUMNS = ["concept_id", "label", "concept_kind", "search_terms",
                   "cs2013_knowledge_area", "cs2013_status", "cs2013_evidence",
                   "cs2023_knowledge_area", "cs2023_status", "cs2023_evidence",
                   "change", "event_period", "notes"]

# Extra columns of the checking workbook (a draft prepared by Claude and
# checked row by row by the researcher). The draft columns are kept so the
# agreement between draft and final decision can be reported.
CHECK_COLUMNS = ["check_first", "cs2013_quote", "check_2013", "cs2023_quote", "check_2023",
                 "claude_draft_2013", "claude_draft_2023"]
CHECK_VALUES = ("ok", "changed")
DRAFT_FILE = "claude_draft_mapping.csv"


def concept_kind(cid: str) -> str:
    return "tool" if cid in TOOL_CONCEPTS else "topic"


def blank_mapping() -> pd.DataFrame:
    """The empty mapping, one row per lexicon concept, in lexicon order."""
    rows = [{"concept_id": cid, "label": c["label"], "concept_kind": concept_kind(cid),
             "search_terms": SEARCH_TERMS.get(cid, c["label"]), "event_period": EVENT_PERIOD}
            for cid, c in LEXICON.items()]
    return pd.DataFrame(rows, columns=MAPPING_COLUMNS).fillna("")


def prefilled_mapping(draft: pd.DataFrame) -> pd.DataFrame:
    """The mapping pre-filled from Claude's draft, ready to be checked.
    Statuses, units and evidence are filled; the check columns are left empty."""
    base = blank_mapping()
    d = draft.fillna("").set_index("concept_id")
    for col in ("cs2013_status", "cs2013_knowledge_area", "cs2013_evidence", "cs2013_quote",
                "cs2023_status", "cs2023_knowledge_area", "cs2023_evidence", "cs2023_quote",
                "check_first", "notes"):
        base[col] = base["concept_id"].map(d[col]) if col in d.columns else ""
    base["claude_draft_2013"] = base["cs2013_status"]
    base["claude_draft_2023"] = base["cs2023_status"]
    base["check_2013"] = ""
    base["check_2023"] = ""
    return base.fillna("")


def derive_change(s2013: str, s2023: str) -> str:
    """The only place the change category is decided."""
    if s2013 == s2023:
        return "none"
    if s2023 == "core":
        return "adoption"          # absent or minor -> core
    if s2023 == "minor":
        return "expansion" if s2013 == "absent" else "reduction"
    return "removal"               # minor or core -> absent


def read_mapping(path) -> pd.DataFrame:
    """Read the filled mapping from .xlsx (sheet 'Mapping') or .csv."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"mapping file not found: {path}")
    if path.suffix.lower() == ".xlsx":
        xl = pd.ExcelFile(path)
        sheet = "Mapping" if "Mapping" in xl.sheet_names else xl.sheet_names[0]
        df = xl.parse(sheet, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    if "concept_id" not in df.columns:
        raise ValueError("mapping has no 'concept_id' column; did you change the header row?")
    # Older template: one combined evidence column.
    if "evidence_page" in df.columns:
        for col in ("cs2013_evidence", "cs2023_evidence"):
            if col not in df.columns:
                df[col] = df["evidence_page"]
    for col in MAPPING_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    for col in ("cs2013_status", "cs2023_status", "change", "concept_kind"):
        df[col] = df[col].str.lower()
    for col in ("check_2013", "check_2023", "claude_draft_2013", "claude_draft_2023"):
        if col in df.columns:
            df[col] = df[col].str.lower()
    df = df[df["concept_id"] != ""]
    return df.reset_index(drop=True)


def check_mapping(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Add a 'derived_change' and 'problem' column. Returns (df, warnings)."""
    df = df.copy()
    warnings: List[str] = []
    unknown = sorted(set(df["concept_id"]) - set(LEXICON))
    if unknown:
        warnings.append(f"not in lexicon v1 (ignored): {unknown}")
    dup = sorted(df.loc[df["concept_id"].duplicated(), "concept_id"].unique())
    if dup:
        warnings.append(f"listed twice (first row used): {dup}")
    df = df[df["concept_id"].isin(LEXICON)].drop_duplicates("concept_id")
    checking = "claude_draft_2013" in df.columns and (df["claude_draft_2013"] != "").any()
    derived, problems = [], []
    for _, r in df.iterrows():
        s13, s23 = r["cs2013_status"], r["cs2023_status"]
        prob = []
        if checking:
            for yr, st in (("2013", s13), ("2023", s23)):
                chk, draft = r.get(f"check_{yr}", ""), r.get(f"claude_draft_{yr}", "")
                if chk not in CHECK_VALUES:
                    prob.append(f"CS{yr} not yet checked" if not chk else f"CS{yr} check '{chk}' not allowed")
                elif chk == "ok" and draft and st != draft:
                    warnings.append(f"{r['concept_id']}: CS{yr} marked OK but status changed from "
                                    f"'{draft}' to '{st}'; please set the check to 'changed'")
                elif chk == "changed" and st == draft:
                    warnings.append(f"{r['concept_id']}: CS{yr} marked changed but status is still '{st}'")
        if s13 not in STATUSES:
            prob.append("CS2013 status blank" if not s13 else f"CS2013 status '{s13}' not allowed")
        if s23 not in STATUSES:
            prob.append("CS2023 status blank" if not s23 else f"CS2023 status '{s23}' not allowed")
        ch = derive_change(s13, s23) if not prob else ""
        if ch and r["change"] and r["change"] != ch:
            warnings.append(f"{r['concept_id']}: typed change '{r['change']}' differs from the rule; "
                            f"using '{ch}'")
        derived.append(ch)
        problems.append("; ".join(prob))
    df["derived_change"] = derived
    df["problem"] = problems
    missing = sorted(set(LEXICON) - set(df["concept_id"]))
    if missing:
        warnings.append(f"concepts missing from the mapping: {missing}")
    return df.reset_index(drop=True), warnings


def _evidence_ok(r) -> bool:
    need13 = r["cs2013_status"] != "absent"
    need23 = r["cs2023_status"] != "absent"
    return (not need13 or bool(r["cs2013_evidence"])) and (not need23 or bool(r["cs2023_evidence"]))


def _citation(r) -> str:
    parts = []
    for yr, cit in (("2013", CITATION_2013), ("2023", CITATION_2023)):
        where = r[f"cs{yr}_evidence"] or ("searched; not found" if r[f"cs{yr}_status"] == "absent"
                                          else "evidence missing")
        parts.append(f"{cit} [{where}]")
    return " | ".join(parts)


def mapping_to_events(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Apply the fixed rules. Input must come from check_mapping()."""
    rows, excluded_tools, incomplete, unsourced = [], [], [], []
    for _, r in df.iterrows():
        cid = r["concept_id"]
        if r["problem"]:
            incomplete.append(cid)
            continue
        ch = r["derived_change"]
        period = r["event_period"] or EVENT_PERIOD
        note = f"CS2013 {r['cs2013_status']} -> CS2023 {r['cs2023_status']} ({ch})"
        if r["notes"]:
            note += f"; {r['notes']}"
        status = "sourced" if _evidence_ok(r) else "requires_citation"
        if status != "sourced":
            unsourced.append(cid)
        if ch in ("adoption", "expansion"):
            etype, layer = "adoption", "systematic"
        elif ch in ("reduction", "removal"):
            etype, layer = "decline", "systematic"
        elif r["cs2023_status"] == "absent":
            if concept_kind(cid) == "tool":
                excluded_tools.append(cid)
                continue
            etype, layer = "none", "negative_control"
        else:
            continue  # present in both at the same level: no event, not a control
        rows.append({"concept_id": cid, "event_period": period, "event_type": etype,
                     "layer": layer, "source_citation": _citation(r),
                     "citation_status": status, "notes": note})
    events = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    summary = {
        "concepts_in_mapping": int(len(df)),
        "complete": int(len(df) - len(incomplete) - len(unsourced)),
        "adoption_events": int((events["event_type"] == "adoption").sum()),
        "decline_events": int((events["event_type"] == "decline").sum()),
        "negative_controls": int((events["event_type"] == "none").sum()),
        "unchanged_present": int(len(df) - len(incomplete) - len(events) - len(excluded_tools)),
        "tools_excluded": excluded_tools,
        "incomplete": incomplete,
        "missing_evidence": unsourced,
    }
    return events, summary


def second_coder_agreement(first: pd.DataFrame, second: pd.DataFrame) -> pd.DataFrame:
    """Cohen's kappa between two coders on the concepts both have completed."""
    cols = ["concept_id", "cs2013_status", "cs2023_status"]
    m = first[cols].merge(second[cols], on="concept_id", suffixes=("_1", "_2"))
    out = []
    for yr in ("2013", "2023"):
        ok = m[f"cs{yr}_status_1"].isin(STATUSES) & m[f"cs{yr}_status_2"].isin(STATUSES)
        both = m[ok]
        a, b = both[f"cs{yr}_status_1"], both[f"cs{yr}_status_2"]
        n = len(both)
        out.append({"curriculum": f"CS{yr}", "concepts_compared": n,
                    "percent_agreement": float((a.to_numpy() == b.to_numpy()).mean()) if n else float("nan"),
                    "cohen_kappa": cohen_kappa(a, b) if n else float("nan"),
                    "disagreements": ", ".join(both.loc[a != b, "concept_id"])})
    return pd.DataFrame(out)


def draft_agreement(df: pd.DataFrame) -> pd.DataFrame:
    """Agreement between Claude's draft and the researcher's final decision,
    on the rows the researcher has finished checking."""
    if "claude_draft_2013" not in df.columns:
        return pd.DataFrame()
    done = df[df["problem"] == ""]
    draft = done[["concept_id"]].assign(cs2013_status=done["claude_draft_2013"],
                                        cs2023_status=done["claude_draft_2023"])
    return second_coder_agreement(draft, done)
