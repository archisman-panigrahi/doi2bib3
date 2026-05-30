"""Helpers to format BibTeX into APS/RevTeX \bibitem entries.

Provides two public functions:
- `format_bibtex_to_aps_bibitem(bibtex_str, key=None)` - format a BibTeX string
  into an APS `\bibitem` block.
- `fetch_bibitem_aps(identifier, key=None, timeout=15)` - resolve an identifier
  to BibTeX (reusing `fetch_bibtex`) and return a `\bibitem` block.
"""
import re
from typing import Optional

import bibtexparser
from bibtexparser.customization import splitname

from .backend import fetch_bibtex, DOIError


def _initials(tokens: list[str]) -> str:
    parts = re.split(r"[\s-]+", " ".join(tokens))
    return " ".join(f"{part[0].upper()}." for part in parts if part[:1].isalpha())


def _format_author(author: str) -> str:
    name = splitname(author, strict_mode=False)
    surname = " ".join(name["von"] + name["last"])
    if name["jr"]:
        surname = f"{surname}, {' '.join(name['jr'])}"
    initials = _initials(name["first"])
    return " ".join(part for part in (initials, surname) if part)


def _format_authors_initials(author_field: str) -> str:
    """Convert BibTeX author list into "F. M. Lastname" style.

    Handles both "First Middle Last" and "Last, First Middle" forms.
    """
    if not author_field:
        return ""
    out = [_format_author(author) for author in author_field.split(" and ")]
    out = [author for author in out if author]

    if len(out) <= 1:
        return out[0] if out else ""
    if len(out) == 2:
        return f"{out[0]}, and {out[1]}"
    return ", ".join(out[:-1]) + ", and " + out[-1]


def _remove_protective_braces(text: str) -> str:
    """Remove protective braces added by BibTeX normalization.
    
    Converts patterns like {Feshbach} to Feshbach while preserving
    other brace usage (nested structures, math, etc.).
    """
    if not text:
        return text
    return re.sub(r"\{([A-Za-z\s\-]+)\}", r"\1", text)


def _doi_from_entry(entry: dict[str, str]) -> Optional[str]:
    doi = entry.get("doi")
    if doi:
        return doi
    match = re.search(r"doi\.org/(10\.\d{4,9}/\S+)$", entry.get("url", ""))
    if match:
        return match.group(1).rstrip(".,;:)]}'\"")
    return None


def format_bibtex_to_aps_bibitem(bibtex_str: str, key: Optional[str] = None) -> str:
    """Format a normalized/formatted BibTeX string into an APS \bibitem.

    Accepts a BibTeX string (ideally normalized by `fetch_bibtex`/`normalize_bibtex`)
    and returns a string like:

    \bibitem{Key}
    F. M. Lastname, S. T. Other, Journal volume, pages (year)
    """
    parser = bibtexparser.bparser.BibTexParser(common_strings=False)
    db = bibtexparser.loads(bibtex_str, parser=parser)
    if not db.entries:
        raise DOIError("No BibTeX entries found to format as bibitem")

    entry = db.entries[0]
    bibkey = key or entry.get("ID") or entry.get("id") or "entry"

    authors = _format_authors_initials(entry.get("author", ""))
    title = _remove_protective_braces(entry.get("title", ""))

    eprint = entry.get("eprint", "")
    archive_prefix = entry.get("archiveprefix", "") or entry.get("archivePrefix", "")
    is_arxiv = archive_prefix.lower() == "arxiv" and eprint

    journal = entry.get("journal") or entry.get("booktitle")
    if not journal and not is_arxiv:
        journal = entry.get("publisher")
    volume = entry.get("volume", "")
    pages = entry.get("pages", "")
    year = entry.get("year", "")
    doi = _doi_from_entry(entry)

    parts = []
    if authors:
        parts.append(authors)
    if title:
        parts.append(title)
    if journal:
        # make the journal volume bold in LaTeX
        vol_part = f"\\textbf{{{volume}}}" if volume else ""
        jp = " ".join(p for p in (journal, vol_part) if p)
        if pages:
            jp = f"{jp}, {pages}"
        if doi:
            if year:
                jp = f"{jp} ({year})"
                year = ""
            jp = f"\\href{{https://doi.org/{doi}}}{{{jp}}}"
        parts.append(jp)
    elif is_arxiv:
        arxiv_ref = f"\\href{{https://arxiv.org/abs/{eprint}}}{{arXiv:{eprint}}}"
        parts.append(arxiv_ref)
    elif pages:
        parts.append(pages)

    # Keep any non-DOI URL as a fallback only if present.
    url = entry.get("url")
    if url and not doi and not is_arxiv:
        parts.append(url)

    output = ", ".join(p for p in parts if p)
    if year:
        output = f"{output} ({year})" if output else f"({year})"
    if output:
        output += "."

    return f"\\bibitem{{{bibkey}}}\n{output}\n"


def fetch_bibitem_aps(identifier: str, key: Optional[str] = None, timeout: int = 15) -> str:
    """Resolve identifier and return an APS/RevTeX \bibitem block.

    Reuses `fetch_bibtex` to avoid duplicating network/normalization logic.
    """
    bibtex = fetch_bibtex(identifier, timeout=timeout)
    return format_bibtex_to_aps_bibitem(bibtex, key=key)
