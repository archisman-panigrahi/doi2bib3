"""doi2bib3 package shim."""

from .backend import fetch_bibtex
from .bibitem import fetch_bibitem_aps, format_bibtex_to_aps_bibitem
from .verify import (
    BibEntry,
    CiteCheckResult,
    ERROR,
    MISMATCH,
    NOT_FOUND,
    REVIEW,
    STATUS_ICON,
    UNVERIFIED,
    VERIFIED,
    VerificationResult,
    check_cite_keys,
    extract_cite_keys,
    normalize_doi,
    parse_bibtex,
    summary,
    verify_bibtex,
    verify_entries,
    verify_entry,
)

__all__ = [
    "fetch_bibtex",
    # APS bibitem
    "fetch_bibitem_aps",
    "format_bibtex_to_aps_bibitem",
    # Verify engine
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
