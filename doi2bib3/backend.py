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
import json
from typing import Optional
import re
import unicodedata
from urllib.parse import quote, unquote, urlparse
import xml.etree.ElementTree as ET

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
import requests

from .constants import USER_AGENT
from .normalize import normalize_bibtex

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
DOI_IN_TEXT_PATTERN = re.compile(r"10\.\d{4,9}/[^\s'\"<>]+")
ISBN_PREFIX_PATTERN = re.compile(
    r"^(?:urn:isbn:|isbn(?:-1[03])?:?)\s*", flags=re.I
)
ISBN_SEPARATOR_TRANSLATION = str.maketrans("", "", " \t\r\n\f\v-")
ARXIV_ID_PATTERN = re.compile(
    r"^(?:\d{4}\.\d+(?:v\d+)?|[A-Za-z\-]+/\d{7}(?:v\d+)?)$"
)
ARXIV_DOI_PATTERN = re.compile(r"^10\.48550/arxiv\.(?P<id>.+)$", flags=re.I)
ARXIV_HOSTS = ("arxiv.org", "www.arxiv.org", "xxx.lanl.gov")
SCHEMELESS_ARXIV_PREFIXES = tuple(f"{host}/" for host in ARXIV_HOSTS)
ARXIV_API_URLS = (
    "http://export.arxiv.org/api/query?id_list={id}",
    "https://export.arxiv.org/api/query?id_list={id}",
    "https://arxiv.org/api/query?id_list={id}",
    "http://arxiv.org/api/query?id_list={id}",
)


class DOIError(Exception):
    pass


@dataclass
class ArxivMetadata:
    arxiv_id: str
    primary_class: Optional[str] = None
    published_doi: Optional[str] = None


def _is_http_url(value: str) -> bool:
    lower = value.lower()
    return lower.startswith("http://") or lower.startswith("https://")


def _dspace_item_api_url(value: str) -> Optional[str]:
    """Map a DSpace 7 entity URL to its public item metadata endpoint."""
    if not _is_http_url(value):
        return None
    parsed = urlparse(value.strip().rstrip(".,;:)]}'\""))
    match = re.fullmatch(
        r"/entities/[^/]+/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})/?",
        parsed.path,
        flags=re.I,
    )
    if not match:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/server/api/core/items/{match.group(1)}"


def _is_handle_url(value: str) -> bool:
    """Return whether *value* is an HTTP Handle System resolver URL."""
    if not _is_http_url(value):
        return False
    return urlparse(value.rstrip(".,;:)]}'\"")).netloc.lower() == "hdl.handle.net"


def _resolve_dspace_api_url(url: str, timeout: int = 15) -> Optional[str]:
    """Resolve a DSpace entity or persistent Handle URL to its item API URL."""
    cleaned_url = url.strip().rstrip(".,;:)]}'\"")
    api_url = _dspace_item_api_url(cleaned_url)
    if api_url:
        return api_url
    if not _is_handle_url(cleaned_url):
        return None

    try:
        resp = requests.get(
            cleaned_url, headers={"User-Agent": USER_AGENT}, timeout=timeout
        )
    except Exception as exc:
        raise DOIError(f"Failed to resolve DSpace handle: {url}") from exc

    api_url = _dspace_item_api_url(resp.url)
    if api_url:
        return api_url

    resolved = urlparse(resp.url)
    legacy_match = re.fullmatch(r"/handle/(.+?)/?", resolved.path)
    if legacy_match:
        handle = unquote(legacy_match.group(1))
        return (
            f"{resolved.scheme}://{resolved.netloc}/server/api/pid/find"
            f"?id={quote(handle, safe='')}"
        )

    if resp.status_code != 200:
        raise DOIError(f"Failed to resolve DSpace handle: HTTP {resp.status_code}")
    raise DOIError(f"Handle did not resolve to a DSpace item: {url}")


def _fetch_dspace_metadata(
    url: str, timeout: int = 15, api_url: Optional[str] = None
) -> dict:
    """Fetch a DSpace item's Dublin Core metadata."""
    api_url = api_url or _resolve_dspace_api_url(url, timeout)
    if not api_url:
        raise DOIError(f"Invalid DSpace item URL: {url}")
    try:
        resp = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except Exception as exc:
        raise DOIError(f"Failed to fetch DSpace metadata: {url}") from exc
    if resp.status_code != 200:
        raise DOIError(f"Failed to fetch DSpace metadata: HTTP {resp.status_code}")

    try:
        metadata = json.loads(_decode_response_text(resp)).get("metadata", {})
    except (json.JSONDecodeError, AttributeError) as exc:
        raise DOIError(f"Invalid DSpace metadata response: {url}") from exc
    return metadata


def _dspace_values(metadata: dict, field: str) -> list[str]:
    return [item["value"] for item in metadata.get(field, []) if item.get("value")]


def _dspace_thesis_bibtex(metadata: dict, url: str) -> Optional[str]:
    """Build thesis BibTeX, or return None when the item is not a thesis."""

    def values(field: str) -> list[str]:
        return _dspace_values(metadata, field)

    degree = " ".join(
        values("dc.description.degree")
        + values("mit.thesis.degree")
        + values("thesis.degree.name")
    ).lower()
    if any(term in degree for term in ("ph.d", "phd", "doctoral", "doctor of philosophy")):
        entry_type = "phdthesis"
    elif "master" in degree:
        entry_type = "mastersthesis"
    else:
        return None

    issued = values("dc.date.issued")
    entry = {
        "ENTRYTYPE": entry_type,
        "ID": "dspace",
        "author": " and ".join(values("dc.contributor.author")),
        "title": next(iter(values("dc.title")), ""),
        "school": next(iter(values("dc.publisher")), ""),
        "year": issued[0][:4] if issued else "",
        "url": next(iter(values("dc.identifier.uri")), url),
    }
    if not all(entry[field] for field in ("author", "title", "school", "year")):
        raise DOIError(f"Incomplete DSpace thesis metadata: {url}")

    database = BibDatabase()
    database.entries = [entry]
    return bibtexparser.dumps(database)


def _dspace_item_doi(metadata: dict) -> Optional[str]:
    """Extract a DOI from common DSpace identifier and relation fields."""
    candidates: list[str] = []
    for field in (
        "dc.identifier.doi",
        "dc.relation.isversionof",
        "dc.relation.hasversion",
        "dc.identifier.uri",
    ):
        candidates.extend(_dspace_values(metadata, field))
    return _first_valid_doi(candidates)


def _fetch_dspace_thesis_bibtex(
    url: str, timeout: int = 15, api_url: Optional[str] = None
) -> str:
    """Build thesis BibTeX from a DSpace item's Dublin Core metadata."""
    metadata = _fetch_dspace_metadata(url, timeout, api_url)
    bibtex = _dspace_thesis_bibtex(metadata, url)
    if bibtex is None:
        raise DOIError(f"DSpace item is not an identified thesis: {url}")
    return bibtex


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


def _is_valid_isbn10(isbn: str) -> bool:
    total = 0
    for idx, char in enumerate(isbn):
        if char == "X":
            if idx != 9:
                return False
            value = 10
        else:
            value = int(char)
        total += (10 - idx) * value
    return total % 11 == 0


def _is_valid_isbn13(isbn: str) -> bool:
    total = sum(
        (1 if idx % 2 == 0 else 3) * int(char)
        for idx, char in enumerate(isbn[:12])
    )
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(isbn[-1])


def _parse_isbn_string(value: str) -> Optional[str]:
    """Return a canonical ISBN-10/ISBN-13 string from input, else None."""
    candidate = value.strip()
    if not candidate:
        return None

    candidate = ISBN_PREFIX_PATTERN.sub("", candidate, count=1).strip()
    if not re.fullmatch(r"[0-9Xx][0-9Xx\s-]*", candidate):
        return None

    isbn = candidate.translate(ISBN_SEPARATOR_TRANSLATION).upper()
    if re.fullmatch(r"\d{9}[\dX]", isbn) and _is_valid_isbn10(isbn):
        return isbn
    if re.fullmatch(r"\d{13}", isbn) and _is_valid_isbn13(isbn):
        return isbn
    return None


def _clean_doi_candidate(candidate: str) -> str:
    """Remove common delimiters accidentally captured around DOI text."""
    return unquote(candidate.strip().replace("\\/", "/")).rstrip(".,;:)]}'\"")


def _parse_arxiv_id_string(value: str) -> Optional[str]:
    """Return a valid arXiv id from an input string, else None."""
    if not value:
        return None
    candidate = value.strip()
    if candidate.lower().startswith("arxiv:"):
        candidate = candidate.split(":", 1)[1].strip()
    elif _is_http_url(candidate) or candidate.lower().startswith(
        SCHEMELESS_ARXIV_PREFIXES
    ):
        try:
            if candidate.lower().startswith(SCHEMELESS_ARXIV_PREFIXES):
                candidate = f"https://{candidate}"
            parsed = urlparse(candidate)
        except Exception:
            return None
        if parsed.netloc.lower() not in ARXIV_HOSTS:
            return None
        m = re.match(r"^(?:abs|pdf|html)/(?P<id>.+)$", parsed.path.lstrip("/"))
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

    headers = {"User-Agent": USER_AGENT}
    last_response: Optional[requests.Response] = None
    last_exception: Optional[Exception] = None

    for template in ARXIV_API_URLS:
        url = template.format(id=quote(parsed))
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
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
    metadata = _fetch_arxiv_metadata(arxiv_id, timeout=timeout)
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
            return _parse_doi_string(_clean_doi_candidate(candidate))
        except DOIError:
            continue
    return None


def _doi_candidates_from_url_path(url: str) -> list[str]:
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path or "")
    except Exception:
        return []

    netloc = parsed.netloc.lower()

    if netloc in ("nature.com", "www.nature.com"):
        match = re.match(r"^/articles/([^/?#]+)/?$", path, flags=re.I)
        if match:
            return [f"10.1038/{match.group(1)}"]

    if (
        netloc in ("iopscience.iop.org", "www.iopscience.iop.org")
        and path.lower().endswith("/pdf")
    ):
        path = path.rsplit("/", 1)[0]

    if netloc in ("scipost.org", "www.scipost.org"):
        scipost_path = path.strip("/")
        if scipost_path.lower().endswith("/pdf"):
            scipost_path = scipost_path.rsplit("/", 1)[0]
        if re.match(r"^SciPost[A-Za-z0-9.:-]+$", scipost_path):
            return [f"10.21468/{scipost_path}"]

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


def _extract_doi_from_sciencedirect_url(url: str, timeout: int = 10) -> Optional[str]:
    """Resolve a ScienceDirect article URL through its Elsevier PII."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if parsed.netloc.lower() not in ("sciencedirect.com", "www.sciencedirect.com"):
        return None

    match = re.search(r"(?:^|/)pii/([^/?#]+)", parsed.path)
    if not match:
        return None

    pii = unquote(match.group(1)).strip()
    if not pii:
        return None

    url = f"https://api.elsevier.com/content/article/pii/{quote(pii, safe='')}"
    headers = {
        "Accept": "application/xml, text/xml;q=0.9, application/json;q=0.8",
        "User-Agent": USER_AGENT,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    text = _decode_response_text(resp).replace("\\/", "/")
    return _first_valid_doi(_doi_candidates_from_html(text))


def _aip_minimal_article_url(url: str) -> Optional[str]:
    """Return AIP's metadata-friendly article URL for a pubs.aip.org URL."""
    parsed = urlparse(url)
    if parsed.netloc.lower() != "pubs.aip.org":
        return None
    match = re.search(r"/article/(?:[^/]+/){3}(\d+)(?:/|$)", parsed.path)
    if not match:
        return None
    return f"https://aipp.silverchair-cdn.com/article-minimal/{match.group(1)}"


def _fetch_html_for_doi_extraction(url: str, timeout: int = 10) -> Optional[str]:
    ua_browser = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
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

    aip_url = _aip_minimal_article_url(url)
    if aip_url:
        html = _fetch_html_for_doi_extraction(aip_url, timeout=timeout)
        return _first_valid_doi(_doi_candidates_from_html(html or ""))

    doi = _extract_doi_from_sciencedirect_url(url, timeout=timeout)
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

    headers = {"User-Agent": USER_AGENT}
    if _is_http_url(q):
        doi = _extract_doi_from_publisher_url(q, timeout=timeout)
        if doi:
            return doi
        if _aip_minimal_article_url(q):
            return None

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
        "User-Agent": USER_AGENT,
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


def _json_response(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        try:
            return json.loads(resp.text)
        except Exception as exc:
            raise DOIError("Invalid JSON response") from exc


def _published_year(published_date: str) -> str:
    match = re.search(r"\d{4}", published_date or "")
    return match.group(0) if match else ""


def _clean_string(value) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _clean_title(value: str) -> str:
    value = _clean_string(value)
    value = re.sub(r"\s+([:;,])", r"\1", value)
    return re.sub(r"([:;,])(?=\S)", r"\1 ", value)


def _join_names(value) -> str:
    if isinstance(value, list):
        names = []
        seen = set()
        for item in value:
            if isinstance(item, dict):
                name = _clean_string(item.get("name"))
            else:
                name = _clean_string(item)
            key = unicodedata.normalize("NFC", name).casefold()
            if name and key not in seen:
                names.append(name)
                seen.add(key)
        return " and ".join(names)
    return _clean_string(value)


def _first_name(value) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _clean_string(item.get("name"))
            else:
                name = _clean_string(item)
            if name:
                return name
        return ""
    return _clean_string(value)


def _book_bibtex(
    isbn: str,
    title: str,
    subtitle: str = "",
    authors: str = "",
    publisher: str = "",
    year: str = "",
    url: str = "",
) -> str:
    title = _clean_title(title)
    subtitle = _clean_string(subtitle)
    if subtitle and subtitle not in title:
        title = f"{title}: {subtitle}" if title else subtitle
    title = _clean_title(title)

    entry = {
        "ENTRYTYPE": "book",
        "ID": isbn,
        "title": title,
        "isbn": isbn,
    }

    optional_fields = {
        "author": _clean_string(authors),
        "publisher": _clean_string(publisher),
        "year": _published_year(year),
        "url": _clean_string(url),
    }
    entry.update({key: value for key, value in optional_fields.items() if value})

    db = BibDatabase()
    db.entries = [entry]
    return bibtexparser.dumps(db)


def _google_books_volume_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch the first Google Books volume result for an ISBN."""
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception as exc:
        raise DOIError(f"Google Books lookup failed for ISBN {isbn}: {exc}") from exc

    if resp.status_code != 200:
        raise DOIError(
            f"Google Books lookup failed for ISBN {isbn}: HTTP {resp.status_code}"
        )

    data = _json_response(resp)
    if not isinstance(data, dict):
        raise DOIError(f"Google Books lookup failed for ISBN {isbn}: invalid response")

    for item in data.get("items", []) or []:
        volume_info = item.get("volumeInfo", {}) if isinstance(item, dict) else {}
        if isinstance(volume_info, dict) and _clean_string(volume_info.get("title")):
            return volume_info

    raise DOIError(
        f"Google Books lookup failed for ISBN {isbn}: no book metadata found"
    )


def _bibtex_from_google_books_volume(isbn: str, volume_info: dict) -> str:
    return _book_bibtex(
        isbn,
        title=_clean_string(volume_info.get("title")),
        subtitle=_clean_string(volume_info.get("subtitle")),
        authors=_join_names(volume_info.get("authors")),
        publisher=_clean_string(volume_info.get("publisher")),
        year=_clean_string(volume_info.get("publishedDate")),
        url=_clean_string(
            volume_info.get("canonicalVolumeLink") or volume_info.get("infoLink")
        ),
    )


def _library_of_congress_book_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch book metadata from the Library of Congress SRU catalog."""
    url = (
        "http://lx2.loc.gov:210/LCDB?version=1.1&operation=searchRetrieve&"
        f"query=bath.isbn%3D{isbn}&maximumRecords=1&recordSchema=mods"
    )
    try:
        resp = requests.get(
            url, headers={"Accept": "application/xml", "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except Exception as exc:
        raise DOIError(f"Library of Congress lookup failed for ISBN {isbn}: {exc}") from exc
    if resp.status_code != 200:
        raise DOIError(
            f"Library of Congress lookup failed for ISBN {isbn}: HTTP {resp.status_code}"
        )

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        raise DOIError(
            f"Library of Congress lookup failed for ISBN {isbn}: invalid XML"
        ) from exc

    ns = {"mods": "http://www.loc.gov/mods/v3"}
    record = root.find(".//mods:mods", ns)
    if record is None:
        raise DOIError(
            f"Library of Congress lookup failed for ISBN {isbn}: no book metadata found"
        )

    title_info = record.find("mods:titleInfo", ns)
    title_parts = []
    subtitle = ""
    if title_info is not None:
        title_parts = [
            _clean_string(node.text)
            for node in title_info.findall("mods:nonSort", ns)
            + title_info.findall("mods:title", ns)
            if _clean_string(node.text)
        ]
        subtitle = _clean_string(title_info.findtext("mods:subTitle", default="", namespaces=ns))

    authors = []
    for name in record.findall("mods:name[@type='personal']", ns):
        for part in name.findall("mods:namePart", ns):
            if part.get("type") is None and _clean_string(part.text):
                authors.append(_clean_string(part.text).rstrip(" ,"))
                break

    publisher = ""
    year = ""
    origin = record.find("mods:originInfo", ns)
    if origin is not None:
        publisher = _clean_string(
            origin.findtext("mods:agent/mods:namePart", default="", namespaces=ns)
        ).rstrip(" ,")
        year = _clean_string(
            origin.findtext("mods:dateIssued", default="", namespaces=ns)
        )

    lccn = record.find("mods:identifier[@type='lccn']", ns)
    catalog_url = (
        f"https://lccn.loc.gov/{quote(_clean_string(lccn.text))}"
        if lccn is not None and _clean_string(lccn.text)
        else ""
    )
    return {
        "title": "".join(title_parts),
        "subtitle": subtitle,
        "authors": authors,
        "publisher": publisher,
        "year": year,
        "url": catalog_url,
    }


def _marc_subfields(field: ET.Element, code: str) -> list[str]:
    ns = {"marc": "http://www.loc.gov/MARC21/slim"}
    return [
        _clean_string(node.text)
        for node in field.findall(f"marc:subfield[@code='{code}']", ns)
        if _clean_string(node.text)
    ]


def _dnb_book_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch book metadata from the German National Library SRU catalog."""
    url = (
        "https://services.dnb.de/sru/dnb?version=1.1&operation=searchRetrieve&"
        f"query=num%3D{isbn}&maximumRecords=1&recordSchema=MARC21-xml"
    )
    try:
        resp = requests.get(
            url, headers={"Accept": "application/xml", "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except Exception as exc:
        raise DOIError(f"DNB lookup failed for ISBN {isbn}: {exc}") from exc
    if resp.status_code != 200:
        raise DOIError(f"DNB lookup failed for ISBN {isbn}: HTTP {resp.status_code}")

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        raise DOIError(f"DNB lookup failed for ISBN {isbn}: invalid XML") from exc

    ns = {"marc": "http://www.loc.gov/MARC21/slim"}
    record = root.find(".//marc:record", ns)
    if record is None:
        raise DOIError(f"DNB lookup failed for ISBN {isbn}: no book metadata found")

    title_field = record.find("marc:datafield[@tag='245']", ns)
    title = subtitle = ""
    if title_field is not None:
        title = " ".join(_marc_subfields(title_field, "a")).rstrip(" /:;,")
        subtitle = " ".join(_marc_subfields(title_field, "b")).rstrip(" /:;,")

    authors = []
    for tag in ("100", "700"):
        for field in record.findall(f"marc:datafield[@tag='{tag}']", ns):
            roles = [role.lower() for role in _marc_subfields(field, "4")]
            if roles and "aut" not in roles:
                continue
            authors.extend(name.rstrip(" /:;,") for name in _marc_subfields(field, "a"))

    publication = record.find("marc:datafield[@tag='264'][@ind2='1']", ns)
    if publication is None:
        publication = record.find("marc:datafield[@tag='260']", ns)
    publisher = year = ""
    if publication is not None:
        publisher = " ".join(_marc_subfields(publication, "b")).rstrip(" /:;,")
        year = " ".join(_marc_subfields(publication, "c"))

    identifier = _clean_string(
        record.findtext("marc:controlfield[@tag='001']", default="", namespaces=ns)
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "authors": authors,
        "publisher": publisher,
        "year": year,
        "url": f"https://d-nb.info/{identifier}" if identifier else "",
    }


def _crossref_book_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch book metadata from Crossref when a deposited work lists the ISBN."""
    url = f"https://api.crossref.org/works?filter=isbn%3A{isbn}&rows=1"
    try:
        resp = requests.get(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except Exception as exc:
        raise DOIError(f"Crossref lookup failed for ISBN {isbn}: {exc}") from exc
    if resp.status_code != 200:
        raise DOIError(f"Crossref lookup failed for ISBN {isbn}: HTTP {resp.status_code}")
    data = _json_response(resp)
    items = data.get("message", {}).get("items", []) if isinstance(data, dict) else []
    if not items:
        raise DOIError(f"Crossref lookup failed for ISBN {isbn}: no book metadata found")
    item = items[0]
    titles = item.get("title") or []
    subtitles = item.get("subtitle") or []
    authors = [
        " ".join(filter(None, (_clean_string(author.get("given")), _clean_string(author.get("family")))))
        for author in item.get("author", [])
        if isinstance(author, dict)
    ]
    date_parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [])
    year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
    return {
        "title": _clean_string(titles[0]) if titles else "",
        "subtitle": _clean_string(subtitles[0]) if subtitles else "",
        "authors": authors,
        "publisher": _clean_string(item.get("publisher")),
        "year": year,
        "url": _clean_string(item.get("URL")),
    }


def _internet_archive_book_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch book metadata from Internet Archive's public search index."""
    fields = "title,creator,publisher,date,identifier"
    url = (
        "https://archive.org/advancedsearch.php?"
        f"q=isbn%3A{isbn}&fl%5B%5D={quote(fields)}&rows=1&output=json"
    )
    try:
        resp = requests.get(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except Exception as exc:
        raise DOIError(f"Internet Archive lookup failed for ISBN {isbn}: {exc}") from exc
    if resp.status_code != 200:
        raise DOIError(
            f"Internet Archive lookup failed for ISBN {isbn}: HTTP {resp.status_code}"
        )
    data = _json_response(resp)
    docs = data.get("response", {}).get("docs", []) if isinstance(data, dict) else []
    if not docs:
        raise DOIError(
            f"Internet Archive lookup failed for ISBN {isbn}: no book metadata found"
        )
    book = docs[0]
    identifier = _clean_string(book.get("identifier"))
    return {
        "title": _clean_string(book.get("title")),
        "authors": book.get("creator") or [],
        "publisher": _first_name(book.get("publisher")),
        "year": _clean_string(book.get("date")),
        "url": f"https://archive.org/details/{quote(identifier)}" if identifier else "",
    }


def _bibtex_from_book_info(isbn: str, book: dict) -> str:
    return _book_bibtex(
        isbn,
        title=_clean_string(book.get("title")),
        subtitle=_clean_string(book.get("subtitle")),
        authors=_join_names(book.get("authors")),
        publisher=_clean_string(book.get("publisher")),
        year=_clean_string(book.get("year")),
        url=_clean_string(book.get("url")),
    )


def _openlibrary_book_info(isbn: str, timeout: int = 15) -> dict:
    """Fetch the Open Library book result for an ISBN."""
    url = (
        "https://openlibrary.org/api/books?"
        f"bibkeys=ISBN:{isbn}&jscmd=data&format=json"
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception as exc:
        raise DOIError(f"Open Library lookup failed for ISBN {isbn}: {exc}") from exc

    if resp.status_code != 200:
        raise DOIError(
            f"Open Library lookup failed for ISBN {isbn}: HTTP {resp.status_code}"
        )

    data = _json_response(resp)
    if not isinstance(data, dict):
        raise DOIError(f"Open Library lookup failed for ISBN {isbn}: invalid response")

    book = data.get(f"ISBN:{isbn}")
    if isinstance(book, dict) and _clean_string(book.get("title")):
        return book

    raise DOIError(
        f"Open Library lookup failed for ISBN {isbn}: no book metadata found"
    )


def _bibtex_from_openlibrary_book(isbn: str, book: dict) -> str:
    return _book_bibtex(
        isbn,
        title=_clean_string(book.get("title")),
        subtitle=_clean_string(book.get("subtitle")),
        authors=_join_names(book.get("authors")),
        publisher=_first_name(book.get("publishers")),
        year=_clean_string(book.get("publish_date")),
        url=_clean_string(book.get("url") or book.get("info_url")),
    )


def _fetch_bibtex_for_isbn(isbn: str, timeout: int = 15) -> str:
    """Query ISBN metadata providers and return a raw BibTeX entry."""
    errors = []
    try:
        book = _openlibrary_book_info(isbn, timeout=timeout)
        return _bibtex_from_openlibrary_book(isbn, book)
    except DOIError as exc:
        errors.append(str(exc))

    providers = (
        ("Library of Congress", _library_of_congress_book_info),
        ("DNB", _dnb_book_info),
        ("Crossref", _crossref_book_info),
        ("Internet Archive", _internet_archive_book_info),
    )
    for _name, provider in providers:
        try:
            book = provider(isbn, timeout=timeout)
            if _clean_string(book.get("title")):
                return _bibtex_from_book_info(isbn, book)
        except DOIError as exc:
            errors.append(str(exc))

    try:
        volume_info = _google_books_volume_info(isbn, timeout=timeout)
        return _bibtex_from_google_books_volume(isbn, volume_info)
    except DOIError as exc:
        errors.append(str(exc))

    raise DOIError(f"ISBN lookup failed for {isbn}: {'; '.join(errors)}")


def fetch_bibtex(identifier: str, timeout: int = 15) -> str:
    """Public API: resolve identifier and return normalized BibTeX."""
    isbn = _parse_isbn_string(identifier)
    if isbn:
        raw = _fetch_bibtex_for_isbn(isbn, timeout=timeout)
        try:
            return normalize_bibtex(raw)
        except Exception:
            return raw

    if _dspace_item_api_url(identifier) or _is_handle_url(identifier):
        dspace_api_url = _resolve_dspace_api_url(identifier, timeout)
        metadata = _fetch_dspace_metadata(identifier, timeout, dspace_api_url)
        thesis_bibtex = _dspace_thesis_bibtex(metadata, identifier)
        if thesis_bibtex is not None:
            return normalize_bibtex(thesis_bibtex)
        doi = _dspace_item_doi(metadata)
        if not doi:
            raise DOIError(f"No thesis degree or DOI found in DSpace item: {identifier}")
        return normalize_bibtex(_fetch_bibtex_for_doi(doi, timeout))

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
