"""Reference-verification engine for doi2bib3.

A deterministic toolkit that decides whether the BibTeX references in a
paper are *authentic* or likely *hallucinated*. Each entry is checked
against authoritative databases (CrossRef, arXiv, the DOI Handle System)
and the verdict is produced purely by code -- no AI service is involved.

The most common entry points are :func:`verify_bibtex`, :func:`verify_entries`
and :func:`verify_entry`. ``BibEntry`` / :func:`parse_bibtex` let callers
split parsing from verification when they need fine-grained control.
"""

from .bibparser import BibEntry, normalize_doi, parse_bibtex
from .citecheck import CiteCheckResult, check_cite_keys, extract_cite_keys
from .verifier import (
    ERROR,
    MISMATCH,
    NOT_FOUND,
    REVIEW,
    STATUS_ICON,
    UNVERIFIED,
    VERIFIED,
    VerificationResult,
    summary,
    verify_bibtex,
    verify_entries,
    verify_entry,
)

__all__ = [
    "BibEntry",
    "parse_bibtex",
    "normalize_doi",
    "CiteCheckResult",
    "check_cite_keys",
    "extract_cite_keys",
    "VerificationResult",
    "verify_entry",
    "verify_entries",
    "verify_bibtex",
    "summary",
    "VERIFIED",
    "REVIEW",
    "MISMATCH",
    "NOT_FOUND",
    "UNVERIFIED",
    "ERROR",
    "STATUS_ICON",
]
