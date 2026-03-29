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

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
import re
import time
from urllib.parse import quote, unquote, urlparse

import requests

from .normalize import normalize_bibtex

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
DOI_IN_TEXT_PATTERN = re.compile(r"10\.\d{4,9}/[^\s'\"<>]+")
ARXIV_ID_PATTERN = re.compile(r"^(?:\d{4}\.\d+(?:v\d+)?|[A-Za-z\-]+/\d{7}(?:v\d+)?)$")
ARXIV_DOI_PATTERN = re.compile(r"^10\.48550/arxiv\.(?P<id>.+)$", flags=re.I)
ARXIV_API_URLS = (
    "http://export.arxiv.org/api/query?id_list={id}",
    "https://export.arxiv.org/api/query?id_list={id}",
    "https://arxiv.org/api/query?id_list={id}",
    "http://arxiv.org/api/query?id_list={id}",
)
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_HTTP_ATTEMPTS = 3


class DOIError(Exception):
    pass


@dataclass
class ArxivMetadata:
    arxiv_id: str
    primary_class: Optional[str] = None
    published_doi: Optional[str] = None


def _retry_delay_seconds(
    resp: Optional[requests.Response], attempt: int, base_delay: float = 1.0
) -> float:
    """Return a retry delay honoring Retry-After when possible."""
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    return max(delay, 0.0)
                except Exception:
                    pass
    return base_delay * (2**attempt)


def _request_with_retries(
    url: str,
    headers: Optional[dict[str, str]] = None,
    timeout: int = 15,
    attempts: int = DEFAULT_HTTP_ATTEMPTS,
) -> requests.Response:
    """Perform GET with retries for transient failures like HTTP 429."""
    last_exception: Optional[Exception] = None

    for attempt in range(attempts):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except Exception as exc:
            last_exception = exc
            if attempt + 1 == attempts:
                raise
            time.sleep(_retry_delay_seconds(None, attempt))
            continue

        if resp.status_code not in RETRYABLE_HTTP_STATUS_CODES:
            return resp
        if attempt + 1 == attempts:
            return resp
        time.sleep(_retry_delay_seconds(resp, attempt))

    if last_exception is not None:
        raise last_exception
    raise DOIError("HTTP request failed without a response")


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


def _parse_arxiv_id_from_doi_string(value: str) -> Optional[str]:
    """Return an arXiv id if the DOI points to an arXiv preprint."""
    try:
        doi = _parse_doi_string(value)
    except DOIError:
        return None

    match = ARXIV_DOI_PATTERN.match(doi)
    if not match:
        return None

    candidate = match.group("id").strip()
    if ARXIV_ID_PATTERN.match(candidate):
        return candidate
    return None


def _canonical_arxiv_id(arxiv_id: str) -> str:
    """Drop the version suffix from a validated arXiv id."""
    return re.sub(r"v\d+$", "", arxiv_id)


def _is_empty_arxiv_feed(text: str) -> bool:
    """Return True if an Atom response does not contain an entry."""
    return "<entry" not in text and "<opensearch:totalResults>0</opensearch:totalResults>" in text


def _fetch_arxiv_entry(arxiv_id: str, timeout: int = 15) -> str:
    """Fetch the raw arXiv Atom entry for an arXiv id."""
    parsed = _parse_arxiv_id_string(arxiv_id)
    if not parsed:
        raise ValueError("Invalid arXiv ID")

    headers = {
        "User-Agent": (
            "doi2bib3-python/1.0 "
            "(https://github.com/archisman-panigrahi/doi2bib3)"
        )
    }
    last_response: Optional[requests.Response] = None
    last_exception: Optional[Exception] = None

    for template in ARXIV_API_URLS:
        url = template.format(id=quote(parsed))
        try:
            resp = _request_with_retries(url, headers=headers, timeout=timeout)
        except Exception as exc:
            last_exception = exc
            continue

        last_response = resp
        if resp.status_code != 200:
            continue
        if _is_empty_arxiv_feed(resp.text):
            continue
        return resp.text

    if last_response is not None:
        if last_response.status_code == 200:
            return last_response.text
        raise DOIError(f"arXiv query failed: HTTP {last_response.status_code}")
    if last_exception is not None:
        raise DOIError(f"arXiv query failed: {last_exception}") from last_exception
    raise DOIError("arXiv query failed: no API endpoint succeeded")


def _extract_published_doi_from_arxiv_entry(text: str) -> Optional[str]:
    """Extract the journal DOI recorded by arXiv, if present."""
    patterns = (
        r"<arxiv:doi\b[^>]*>([^<]+)</arxiv:doi>",
        r"<doi\b[^>]*>([^<]+)</doi>",
        r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return unquote(match.group(1).strip())
    return None


def _extract_primary_class_from_arxiv_entry(text: str) -> Optional[str]:
    """Extract the primary arXiv subject class from an Atom entry."""
    match = re.search(
        r"<arxiv:primary_category\b[^>]*term=[\"']([^\"']+)[\"']",
        text,
        flags=re.I,
    )
    if match:
        return match.group(1).strip()
    return None


def _fetch_arxiv_metadata(arxiv_id: str, timeout: int = 15) -> ArxivMetadata:
    """Fetch arXiv metadata used for DOI resolution and BibTeX enrichment."""
    entry = _fetch_arxiv_entry(arxiv_id, timeout=timeout)
    return ArxivMetadata(
        arxiv_id=_canonical_arxiv_id(arxiv_id),
        primary_class=_extract_primary_class_from_arxiv_entry(entry),
        published_doi=_extract_published_doi_from_arxiv_entry(entry),
    )


def _resolve_doi_from_arxiv_id(arxiv_id: str, timeout: int = 15) -> Optional[str]:
    """Resolve DOI for a validated arXiv id via arXiv API."""
    return _fetch_arxiv_metadata(arxiv_id, timeout=timeout).published_doi


def _resolve_arxiv_identifier(
    arxiv_id: str, timeout: int = 15
) -> tuple[str, ArxivMetadata]:
    """Resolve an arXiv id to its journal DOI or arXiv DOI plus metadata."""
    try:
        metadata = _fetch_arxiv_metadata(arxiv_id, timeout=timeout)
    except DOIError:
        metadata = ArxivMetadata(arxiv_id=_canonical_arxiv_id(arxiv_id))
    if metadata.published_doi:
        return _parse_doi_string(metadata.published_doi), metadata

    candidate = f"10.48550/arXiv.{metadata.arxiv_id}"
    try:
        return _parse_doi_string(candidate), metadata
    except DOIError as exc:
        raise DOIError(f"No DOI found for arXiv id: {arxiv_id}") from exc


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
        resp = _request_with_retries(
            url, headers={"User-Agent": ua_bot}, timeout=timeout
        )
    except Exception:
        return None

    if resp.status_code == 200 and resp.text:
        return resp.text

    try:
        resp = _request_with_retries(
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
        resp = _request_with_retries(url, headers=headers, timeout=timeout)
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
        doi, _ = _resolve_arxiv_identifier(arxiv_id, timeout=timeout)
        return doi

    arxiv_doi_id = _parse_arxiv_id_from_doi_string(identifier)
    if arxiv_doi_id:
        return _parse_doi_string(identifier)

    try:
        return _parse_doi_string(identifier)
    except DOIError:
        found = _search_doi_via_crossref(identifier, timeout=timeout)
        if not found:
            raise DOIError(f"Crossref lookup failed for: {identifier}")
        return _parse_doi_string(found)


def _resolve_identifier(
    identifier: str, timeout: int = 15
) -> tuple[str, Optional[ArxivMetadata]]:
    """Resolve an identifier to a DOI plus optional arXiv metadata."""
    arxiv_id = _parse_arxiv_id_string(identifier)
    if arxiv_id:
        doi, metadata = _resolve_arxiv_identifier(arxiv_id, timeout=timeout)
        return doi, metadata

    arxiv_doi_id = _parse_arxiv_id_from_doi_string(identifier)
    if arxiv_doi_id:
        metadata: Optional[ArxivMetadata]
        try:
            metadata = _fetch_arxiv_metadata(arxiv_doi_id, timeout=timeout)
        except DOIError:
            metadata = ArxivMetadata(arxiv_id=_canonical_arxiv_id(arxiv_doi_id))
        return _parse_doi_string(identifier), metadata

    return _resolve_identifier_to_doi(identifier, timeout=timeout), None


def _fetch_bibtex_for_doi(doi: str, timeout: int = 15) -> str:
    """Query doi.org for BibTeX and fallback to Crossref transform endpoint."""
    headers = {
        "Accept": "application/x-bibtex; charset=utf-8",
        "User-Agent": "doi2bib-python/1.0",
    }

    url = f"https://doi.org/{doi}"
    resp: Optional[requests.Response]
    resp2: Optional[requests.Response]

    doi_error: Optional[str] = None
    try:
        resp = _request_with_retries(url, headers=headers, timeout=timeout)
    except Exception as exc:
        resp = None
        doi_error = f"request failed: {exc}"
    if resp is not None and resp.status_code == 200:
        return _decode_response_text(resp)
    if doi_error is None and resp is not None:
        doi_error = f"HTTP {resp.status_code}"

    doi_quoted = quote(doi, safe="")
    xurl = (
        "https://api.crossref.org/works/"
        f"{doi_quoted}/transform/application/x-bibtex"
    )
    crossref_error: Optional[str] = None
    try:
        resp2 = _request_with_retries(xurl, headers=headers, timeout=timeout)
    except Exception as exc:
        resp2 = None
        crossref_error = f"request failed: {exc}"
    if resp2 is not None and resp2.status_code == 200:
        return _decode_response_text(resp2)
    if crossref_error is None and resp2 is not None:
        crossref_error = f"HTTP {resp2.status_code}"

    raise DOIError(
        f"Failed to fetch DOI {doi}: doi.org {doi_error}, "
        f"crossref {crossref_error}"
    )


def fetch_bibtex(identifier: str, timeout: int = 15) -> str:
    """Public API: resolve identifier and return normalized BibTeX."""
    doi, arxiv_metadata = _resolve_identifier(identifier, timeout=timeout)
    raw = _fetch_bibtex_for_doi(doi, timeout=timeout)
    try:
        include_arxiv_fields = bool(
            arxiv_metadata and not arxiv_metadata.published_doi
        )
        return normalize_bibtex(
            raw,
            arxiv_id=arxiv_metadata.arxiv_id if include_arxiv_fields else None,
            primary_class=(
                arxiv_metadata.primary_class if include_arxiv_fields else None
            ),
            include_arxiv_fields=include_arxiv_fields,
        )
    except Exception:
        return raw
