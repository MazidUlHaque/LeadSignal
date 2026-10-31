"""Concept matching on titles and abstracts.

Rules (proposal Section 4.2):
  * whole-word matching, implemented with alphanumeric lookarounds so terms
    like "C++", "CI/CD" and "Next.js" still work;
  * aliases written entirely in capitals (LLM, RAG, NLP, BERT, ...) are
    case-sensitive, all others are case-insensitive;
  * spaces and hyphens are interchangeable ("chain-of-thought" matches
    "chain of thought"), and a plural "s"/"es" is allowed;
  * exclusion terms veto a match.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .lexicon import LEXICON

_L = r"(?<![A-Za-z0-9])"
_R = r"(?![A-Za-z0-9])"


def _alias_regex(alias: str) -> str:
    # Split on spaces and hyphens, escape each piece, and rejoin with a
    # separator that accepts either (so "chain-of-thought" == "chain of thought").
    pieces = [re.escape(p) for p in re.split(r"[ \-]+", alias.strip()) if p]
    body = r"[\s\-]*".join(pieces)
    plural = r"(?:s|es)?" if alias[-1].isalpha() else ""
    return body + plural


def _is_case_sensitive(alias: str) -> bool:
    letters = [ch for ch in alias if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters)


def compile_concept(concept: Dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    ci = [_alias_regex(a) for a in concept["aliases"] if not _is_case_sensitive(a)]
    cs = [_alias_regex(a) for a in concept["aliases"] if _is_case_sensitive(a)]
    ex = [_alias_regex(a) for a in concept.get("exclude", [])]
    wrap = lambda parts: f"{_L}(?:{'|'.join(parts)}){_R}" if parts else None
    return wrap(ci), wrap(cs), wrap(ex)


def match_text(text: str, concept: Dict) -> bool:
    ci, cs, ex = compile_concept(concept)
    hit = bool((ci and re.search(ci, text, re.IGNORECASE)) or (cs and re.search(cs, text)))
    if hit and ex and re.search(ex, text, re.IGNORECASE):
        return False
    return hit


def match_papers(papers: pd.DataFrame, lexicon: Dict[str, Dict] = None,
                 concepts: Optional[List[str]] = None) -> pd.DataFrame:
    """Return a long table (arxiv_id, concept_id), one row per match."""
    lexicon = lexicon or LEXICON
    text = (papers["title"].fillna("") + " . " + papers["abstract"].fillna("")).astype(str)
    out = []
    for cid in concepts or list(lexicon):
        ci, cs, ex = compile_concept(lexicon[cid])
        mask = pd.Series(False, index=papers.index)
        if ci:
            mask |= text.str.contains(ci, flags=re.IGNORECASE, regex=True)
        if cs:
            mask |= text.str.contains(cs, regex=True)
        if ex:
            mask &= ~text.str.contains(ex, flags=re.IGNORECASE, regex=True)
        ids = papers.loc[mask, "arxiv_id"]
        out.append(pd.DataFrame({"arxiv_id": ids.to_numpy(), "concept_id": cid}))
    if not out:
        return pd.DataFrame(columns=["arxiv_id", "concept_id"])
    return pd.concat(out, ignore_index=True).drop_duplicates()


def audit_sample(papers: pd.DataFrame, matches: pd.DataFrame, concept_id: str,
                 n: int = 30, seed: int = 0) -> pd.DataFrame:
    """Random sample of matched papers for the hand precision audit.

    Fill the 'relevant' column with 1 or 0 by hand; precision is its mean."""
    ids = matches.loc[matches["concept_id"] == concept_id, "arxiv_id"]
    sample = papers[papers["arxiv_id"].isin(ids)]
    sample = sample.sample(n=min(n, len(sample)), random_state=seed)
    out = sample[["arxiv_id", "v1_date", "title", "abstract"]].copy()
    out.insert(0, "concept_id", concept_id)
    out["relevant"] = ""
    return out
