"""Helpers to format BibTeX into APS/RevTeX \bibitem entries.

Provides two public functions:
- `format_bibtex_to_aps_bibitem(bibtex_str, key=None)` - format a BibTeX string
  into an APS `\bibitem` block.
- `fetch_bibitem_aps(identifier, key=None, timeout=15)` - resolve an identifier
  to BibTeX (reusing `fetch_bibtex`) and return a `\bibitem` block.
"""
from typing import Optional
import re

import bibtexparser

from .backend import fetch_bibtex, DOIError


def _format_authors_initials(author_field: str) -> str:
    """Convert BibTeX author list into "F. M. Lastname" style.

    Handles both "First Middle Last" and "Last, First Middle" forms.
    """
    if not author_field:
        return ""
    authors = [a.strip() for a in author_field.split(" and ") if a.strip()]
    out = []
    # common lowercase name particles to treat as part of the surname
    particles = {
        "van",
        "von",
        "de",
        "del",
        "da",
        "di",
        "la",
        "le",
        "du",
        "dos",
        "das",
        "des",
        "der",
        "den",
        "st",
        "st.",
        "al",
        "bin",
        "ibn",
    }

    for a in authors:
        if "," in a:
            last, given = [p.strip() for p in a.split(",", 1)]
        else:
            parts = a.split()
            if len(parts) == 1:
                last = parts[0]
                given = ""
            else:
                # detect lowercase particles preceding the final token and
                # include them as part of the surname (e.g. "van Beethoven")
                i = len(parts) - 1
                surname_tokens = [parts[i]]
                i -= 1
                while i >= 0 and parts[i].lower().rstrip(".") in particles:
                    surname_tokens.insert(0, parts[i])
                    i -= 1
                last = " ".join(surname_tokens)
                given = " ".join(parts[: i + 1])

        initials = []
        for token in re.split(r"[\s-]+", given.strip()):
            if not token:
                continue
            ch = token[0]
            if ch.isalpha():
                initials.append(ch.upper() + ".")

        if initials:
            out.append(" ".join(initials) + " " + last)
        else:
            out.append(last)

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
    result = re.sub(r"\{([A-Za-z\s\-]+)\}", r"\1", text)
    return result


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

    journal = entry.get("journal") or entry.get("booktitle") or entry.get("publisher")
    volume = entry.get("volume", "")
    number = entry.get("number", "")
    pages = entry.get("pages", "")
    year = entry.get("year", "")
    doi = entry.get("doi")
    if not doi:
        url = entry.get("url", "")
        match = re.search(r"doi\.org/(10\.\d{4,9}/\S+)$", url)
        if match:
            doi = match.group(1).rstrip(".,;:)]}'\"")

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
            jp = f"\\href{{https://doi.org/{doi}}}{{{jp}}}"
        parts.append(jp)
    else:
        if pages:
            parts.append(pages)

    if year:
        parts.append(f"({year})")

    # Keep any non-DOI URL as a fallback only if present.
    url = entry.get("url")
    if url and not doi:
        parts.append(url)

    output = ", ".join(p for p in parts if p)

    return f"\\bibitem{{{bibkey}}}\n{output}\n"


def fetch_bibitem_aps(identifier: str, key: Optional[str] = None, timeout: int = 15) -> str:
    """Resolve identifier and return an APS/RevTeX \bibitem block.

    Reuses `fetch_bibtex` to avoid duplicating network/normalization logic.
    """
    bibtex = fetch_bibtex(identifier, timeout=timeout)
    try:
        return format_bibtex_to_aps_bibitem(bibtex, key=key)
    except Exception:
        fallback_key = key or "entry"
        return f"\\bibitem{{{fallback_key}}}\n{bibtex}\n"
