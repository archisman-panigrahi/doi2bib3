# Copyright (c) 2025 Archisman Panigrahi <apandada1ATgmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Identifier resolution and network fetching for BibTeX retrieval."""

from typing import Optional
import re
from urllib.parse import quote, unquote, urlparse

import requests

from .normalize import normalize_bibtex

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
DOI_IN_TEXT_PATTERN = re.compile(r"10\.\d{4,9}/[^\s'\"<>]+")
ARXIV_ID_PATTERN = re.compile(r"^(?:\d{4}\.\d+(?:v\d+)?|[A-Za-z\-]+/\d{7}(?:v\d+)?)$")


class DOIError(Exception):
    pass


def _is_http_url(value: str) -> bool:
    lower = value.lower()
    return lower.startswith("http://") or lower.startswith("https://")


def _decode_response_text(resp: requests.Response) -> str:
    try:
        return resp.content.decode("utf-8")
    except Exception:
        enc = resp.apparent_encoding or resp.encoding or "utf-8"
        return resp.content.decode(enc, errors="replace")


def _parse_doi_string(doi_input: str) -> str:
    """Parse and validate a DOI-like string."""
    candidate = doi_input.strip()
    if candidate.lower().startswith("doi:"):
        candidate = candidate[4:].strip()
    if _is_http_url(candidate):
        parsed = urlparse(candidate)
        candidate = parsed.path.lstrip("/")
    candidate = unquote(candidate)
    if DOI_PATTERN.match(candidate):
        return candidate
    raise DOIError(f"Invalid DOI: {doi_input}")


def _parse_arxiv_id_string(value: str) -> Optional[str]:
    """Return a valid arXiv id from an input string, else None."""
    if not value:
        return None
    candidate = value.strip()
    if candidate.lower().startswith("arxiv:"):
        candidate = candidate.split(":", 1)[1].strip()
    elif _is_http_url(candidate):
        try:
            parsed = urlparse(candidate)
        except Exception:
            return None
        if "arxiv.org" not in parsed.netloc.lower():
            return None
        path = parsed.path.lstrip("/")
        m = re.match(r"^(?:abs|pdf|html)/(?P<id>.+)$", path)
        if not m:
            return None
        candidate = re.sub(r"\.pdf$", "", m.group("id"), flags=re.I)

    if ARXIV_ID_PATTERN.match(candidate):
        return candidate
    return None


def _resolve_doi_from_arxiv_id(arxiv_id: str, timeout: int = 15) -> Optional[str]:
    """Resolve DOI for a validated arXiv id via arXiv API."""
    parsed = _parse_arxiv_id_string(arxiv_id)
    if not parsed:
        raise ValueError("Invalid arXiv ID")

    url = f"https://export.arxiv.org/api/query?id_list={parsed}"
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise DOIError(f"arXiv query failed: HTTP {resp.status_code}")

    text = resp.text
    patterns = (
        r"<arxiv:doi\b[^>]*>([^<]+)</arxiv:doi>",
        r"<doi\b[^>]*>([^<]+)</doi>",
        r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']',
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return unquote(m.group(1).strip())
    return None


def _first_valid_doi(candidates: list[str]) -> Optional[str]:
    for candidate in candidates:
        try:
            return _parse_doi_string(candidate)
        except DOIError:
            continue
    return None


def _doi_candidates_from_url_path(url: str) -> list[str]:
    try:
        path = unquote(urlparse(url).path or "")
    except Exception:
        return []
    m = DOI_IN_TEXT_PATTERN.search(path)
    return [m.group(0)] if m else []


def _doi_candidates_from_html(html: str) -> list[str]:
    candidates: list[str] = []
    patterns = (
        r'<meta[^>]+name=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\'](?:dc\.|dcterms\.)?identifier["\'][^>]*content=["\']([^"\']+)["\']',
        r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']',
        r'(?:href|src)=["\'][^"\']*(10\.\d{4,9}/[^"\']+)["\']',
        r"(10\.\d{4,9}/[^\s\"'<>]+)",
    )
    for pattern in patterns:
        for m in re.finditer(pattern, html, flags=re.I):
            raw = m.group(1).strip()
            if raw.lower().startswith("doi:"):
                raw = raw[4:].strip()
            candidates.append(raw)
    return candidates


def _fetch_html_for_doi_extraction(url: str, timeout: int = 10) -> Optional[str]:
    ua_bot = "doi2bib3-python/1.0"
    ua_browser = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )

    try:
        resp = requests.get(url, headers={"User-Agent": ua_bot}, timeout=timeout)
    except Exception:
        return None

    if resp.status_code == 200 and resp.text:
        return resp.text

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": ua_browser, "Referer": url},
            timeout=timeout,
        )
    except Exception:
        return None

    if resp.status_code == 200 and resp.text:
        return resp.text
    return None


def _extract_doi_from_publisher_url(url: str, timeout: int = 10) -> Optional[str]:
    """Extract DOI from URL path and publisher page metadata/content."""
    doi = _first_valid_doi(_doi_candidates_from_url_path(url))
    if doi:
        return doi

    html = _fetch_html_for_doi_extraction(url, timeout=timeout)
    if not html:
        return None
    return _first_valid_doi(_doi_candidates_from_html(html))


def _search_doi_via_crossref(query: str, timeout: int = 15) -> Optional[str]:
    """Search DOI using URL extraction heuristics and Crossref API."""
    q = query.strip()
    if not q:
        return None

    headers = {"User-Agent": "doi2bib-python/1.0"}
    if _is_http_url(q):
        doi = _extract_doi_from_publisher_url(q, timeout=timeout)
        if doi:
            return doi

    try:
        url = f"https://api.crossref.org/works?query.bibliographic={quote(q)}&rows=5"
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        items = resp.json().get("message", {}).get("items", [])
        if not items:
            return None

        if _is_http_url(q):
            netloc = urlparse(q).netloc.lower()
            for item in items:
                item_url = (item.get("URL") or "").lower()
                if netloc and netloc in item_url and item.get("DOI"):
                    return item.get("DOI")

        top = sorted(items, key=lambda item: item.get("score", 0), reverse=True)[0]
        return top.get("DOI")
    except Exception:
        return None


def _resolve_identifier_to_doi(identifier: str, timeout: int = 15) -> str:
    """Resolve user identifier (DOI/arXiv/URL/title) to a DOI string."""
    arxiv_id = _parse_arxiv_id_string(identifier)
    if arxiv_id:
        found_doi = _resolve_doi_from_arxiv_id(arxiv_id, timeout=timeout)
        if found_doi:
            return _parse_doi_string(found_doi)
        arxiv_core = re.sub(r"v\d+$", "", arxiv_id)
        candidate = f"10.48550/arXiv.{arxiv_core}"
        try:
            return _parse_doi_string(candidate)
        except DOIError as exc:
            raise DOIError(f"No DOI found for arXiv id: {arxiv_id}") from exc

    try:
        return _parse_doi_string(identifier)
    except DOIError:
        found = _search_doi_via_crossref(identifier, timeout=timeout)
        if not found:
            raise DOIError(f"Crossref lookup failed for: {identifier}")
        return _parse_doi_string(found)


def _fetch_bibtex_for_doi(doi: str, timeout: int = 15) -> str:
    """Query doi.org for BibTeX and fallback to Crossref transform endpoint."""
    headers = {
        "Accept": "application/x-bibtex; charset=utf-8",
        "User-Agent": "doi2bib-python/1.0",
    }

    url = f"https://doi.org/{doi}"
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 200:
        return _decode_response_text(resp)

    doi_quoted = quote(doi, safe="")
    xurl = (
        "https://api.crossref.org/works/"
        f"{doi_quoted}/transform/application/x-bibtex"
    )
    resp2 = requests.get(xurl, headers=headers, timeout=timeout)
    if resp2.status_code == 200:
        return _decode_response_text(resp2)

    raise DOIError(
        f"Failed to fetch DOI {doi}: doi.org HTTP {resp.status_code}, "
        f"crossref HTTP {resp2.status_code}"
    )


def fetch_bibtex(identifier: str, timeout: int = 15) -> str:
    """Public API: resolve identifier and return normalized BibTeX."""
    doi = _resolve_identifier_to_doi(identifier, timeout=timeout)
    raw = _fetch_bibtex_for_doi(doi, timeout=timeout)
    try:
        return normalize_bibtex(raw)
    except Exception:
        return raw
