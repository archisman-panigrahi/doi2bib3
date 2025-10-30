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

from typing import Optional
import re
import requests
from urllib.parse import urlparse, unquote, quote
from .utils import normalize_bibtex

DOI_REGEX = re.compile(r"^10\..+/.+$")


def normalize_doi(doi_input: str) -> str:
    s = doi_input.strip()
    if s.lower().startswith('doi:'):
        s = s[4:]
    if s.lower().startswith('http://') or s.lower().startswith('https://'):
        parsed = urlparse(s)
        s = parsed.path.lstrip('/')
    s = unquote(s)
    if DOI_REGEX.match(s):
        return s
    raise DOIError(f"Invalid DOI: {doi_input}")


class DOIError(Exception):
    pass


def get_bibtex_from_doi(doi: str, timeout: int = 15) -> str:
    # First, detect if the input is an arXiv id or arXiv URL. If so,
    # resolve it using the arXiv API (arxiv_to_doi) and continue with the
    # DOI fetch flow. This ensures arXiv links (abs/pdf/html) don't get
    # mis-resolved by Crossref.
    arxiv_id = _extract_arxiv_id(doi)
    if arxiv_id:
        found_doi = arxiv_to_doi(arxiv_id, timeout=timeout)
        if not found_doi:
            # Many arXiv entries (especially unpublished ones) are indexed in
            # Crossref/DataCite with a DOI of the form 10.48550/arXiv.<id>
            # (without version). Try that pattern before giving up.
            arxiv_core = re.sub(r'v\d+$', '', arxiv_id)
            candidate = f'10.48550/arXiv.{arxiv_core}'
            try:
                # normalize to ensure it's a valid DOI string
                candidate = normalize_doi(candidate)
                doi = candidate
            except DOIError:
                raise DOIError(f"No DOI found for arXiv id: {arxiv_id}")
        else:
            doi = found_doi
    else:
        # Try to normalize input to a DOI; if that fails, fall back to
        # Crossref search which can accept publisher URLs or free-form queries.
        try:
            doi = normalize_doi(doi)
        except DOIError:
            found = crossref_search_for_doi(doi, timeout=timeout)
            if not found:
                raise DOIError(f"Invalid DOI and Crossref lookup failed for: {doi}")
            doi = found

    headers = {
        'Accept': 'application/x-bibtex; charset=utf-8',
        'User-Agent': 'doi2bib-python/1.0'
    }
    # try doi.org first
    url = f'https://doi.org/{doi}'
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 200:
        # Some providers mislabel encodings; prefer UTF-8 and fall back to
        # the apparent encoding, replacing invalid bytes. This avoids
        # mojibake like â€“ for en-dash when requests guesses the wrong codec.
        try:
            return resp.content.decode('utf-8')
        except Exception:
            enc = resp.apparent_encoding or resp.encoding or 'utf-8'
            return resp.content.decode(enc, errors='replace')

    # fallback to Crossref transform endpoint
    doi_quoted = quote(doi, safe='')
    xurl = f'https://api.crossref.org/works/{doi_quoted}/transform/application/x-bibtex'
    resp2 = requests.get(xurl, headers=headers, timeout=timeout)
    if resp2.status_code == 200:
        try:
            return resp2.content.decode('utf-8')
        except Exception:
            enc2 = resp2.apparent_encoding or resp2.encoding or 'utf-8'
            return resp2.content.decode(enc2, errors='replace')

    raise DOIError(f"Failed to fetch DOI {doi}: doi.org HTTP {resp.status_code}, crossref HTTP {resp2.status_code}")


def _extract_arxiv_id(s: str) -> Optional[str]:
    """Return an arXiv id if `s` is an arXiv URL or id, else None.

    Accepts forms like:
    - https://arxiv.org/abs/2411.08091
    - https://arxiv.org/pdf/2411.08091.pdf
    - https://arxiv.org/html/2411.08091
    - arXiv:2411.08091
    - 2411.08091
    Also handles older IDs like hep-th/9901001.
    """
    if not s:
        return None
    t = s.strip()
    # arXiv: prefix
    if t.lower().startswith('arxiv:'):
        return t.split(':', 1)[1].strip()

    # URL forms
    if t.lower().startswith('http://') or t.lower().startswith('https://'):
        try:
            parsed = urlparse(t)
            net = parsed.netloc.lower()
            if 'arxiv.org' in net:
                path = parsed.path.lstrip('/')
                # match abs/, pdf/, html/ etc.
                m = re.match(r'^(?:abs|pdf|html)/(?P<id>.+)$', path)
                if m:
                    aid = m.group('id')
                    # strip .pdf extension when present
                    aid = re.sub(r'\.pdf$', '', aid, flags=re.I)
                    return aid
        except Exception:
            return None

    # bare modern arXiv id: YYYY.NNNNN or with vN
    if re.match(r'^\d{4}\.\d+(v\d+)?$', t):
        return t

    # legacy arXiv id like hep-th/9901001
    if re.match(r'^[a-z\-]+/\d{7}$', t, flags=re.I):
        return t

    return None


# pmid_to_doi is disabled — PubMed/PMID support commented out per project config
## def pmid_to_doi(pmid: str, timeout: int = 15) -> Optional[str]:
##     pmid = pmid.strip()
##     if not re.match(r"^\d+$|^PMC\d+(\.\d+)?$", pmid):
##         raise ValueError("Invalid PMID")
##
##     url = f'http://www.pubmedcentral.nih.gov/utils/idconv/v1.0/?format=json&ids={pmid}'
##     resp = requests.get(url, timeout=timeout)
##     if resp.status_code != 200:
##         raise DOIError(f"PubMed ID conversion failed: HTTP {resp.status_code}")
##     data = resp.json()
##     records = data.get('records')
##     if not records or not records[0]:
##         return None
##     return records[0].get('doi')


def arxiv_to_doi(arxivid: str, timeout: int = 15) -> Optional[str]:
    arxivid = arxivid.strip()
    if arxivid.lower().startswith('arxiv:'):
        arxivid = arxivid.split(':', 1)[1].strip()

    # Accept modern arXiv IDs (YYYY.NNNNN with optional vN) and legacy
    # subject-class IDs like hep-th/9901001 (optionally with vN).
    if not re.match(r"^(?:\d{4}\.\d+(v\d+)?|[A-Za-z\-]+/\d{7}(v\d+)?)$", arxivid):
        raise ValueError("Invalid arXiv ID")

    url = f'https://export.arxiv.org/api/query?id_list={arxivid}'
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise DOIError(f"arXiv query failed: HTTP {resp.status_code}")
    text = resp.text
    m = re.search(r"<arxiv:doi\b[^>]*>([^<]+)</arxiv:doi>", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"<doi\b[^>]*>([^<]+)</doi>", text)
    if m:
        return m.group(1).strip()
    m = re.search(r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']', text)
    if m:
        return unquote(m.group(1).strip())
    return None


def crossref_search_for_doi(query: str, timeout: int = 15) -> Optional[str]:
    q = query.strip()
    if not q:
        return None

    headers = {
        'User-Agent': 'doi2bib-python/1.0'
    }

    # If the query is a URL, try to extract a DOI-like substring from the path
    # or from the publisher page HTML (meta tags, canonical/doi links). This
    # avoids sending the full publisher URL as a free-form Crossref query
    # which can produce unrelated matches.
    if q.lower().startswith('http://') or q.lower().startswith('https://'):
        try:
            parsed = urlparse(q)
            path = unquote(parsed.path or '')
            m = re.search(r"10\.\d{4,9}/[^\s'\"<>]+", path)
            if m:
                candidate = m.group(0)
                try:
                    return normalize_doi(candidate)
                except DOIError:
                    pass
        except Exception:
            pass

        # Try to fetch the publisher page and look for common DOI metadata
        try:
            doi_from_page = _extract_doi_from_url(q, timeout=timeout)
            if doi_from_page:
                return doi_from_page
        except Exception:
            # Don't fail hard on page parsing — fall back to Crossref search
            pass

    # Ask Crossref for a handful of candidates and pick the best match.
    try:
        url = f'https://api.crossref.org/works?query.bibliographic={quote(q)}&rows=5'
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get('message', {}).get('items', [])
        if not items:
            return None

        # If query was a URL, prefer items whose URL contains the same netloc
        if q.lower().startswith('http://') or q.lower().startswith('https://'):
            try:
                parsed_q = urlparse(q)
                q_netloc = parsed_q.netloc.lower()
                for it in items:
                    it_url = (it.get('URL') or '')
                    if it_url and q_netloc in it_url.lower():
                        if it.get('DOI'):
                            return it.get('DOI')
            except Exception:
                pass

        # Fallback: choose highest score returned by Crossref
        items_sorted = sorted(items, key=lambda x: x.get('score', 0), reverse=True)
        top = items_sorted[0]
        return top.get('DOI')
    except Exception:
        return None


def _extract_doi_from_url(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch a publisher URL and try to extract a DOI from common meta tags
    and links.

    Heuristics checked (in order):
    - meta[name=citation_doi]
    - meta[name=dc.Identifier] / meta[name=DC.identifier]
    - meta[name=DC.identifier] with scheme DOI
    - link[href] pointing to dx.doi.org or doi.org
    - any href/src containing /10.xxxx/ pattern
    Returns a normalized DOI string or None.
    """
    # Try a polite bot UA first; some sites block unknown agents. If we get a
    # non-200 (commonly 403), retry once with a common browser User-Agent and
    # a Referer header to improve chances of acceptance.
    ua_bot = 'doi2bib3-python/1.0'
    ua_browser = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
    headers = {'User-Agent': ua_bot}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200 or not resp.text:
            # retry with browser UA and Referer
            try:
                headers = {'User-Agent': ua_browser, 'Referer': url}
                resp = requests.get(url, headers=headers, timeout=timeout)
            except Exception:
                return None
        if resp.status_code != 200 or not resp.text:
            return None
        html = resp.text
    except Exception:
        return None

    # meta tags: citation_doi is common (used by many publishers)
    m = re.search(r'<meta[^>]+name=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']', html, flags=re.I)
    if m:
        try:
            return normalize_doi(m.group(1).strip())
        except DOIError:
            pass

    # dc.identifier or DCTERMS.identifier
    m = re.search(r'<meta[^>]+name=["\'](?:dc\.|DCTERMS\.)?identifier["\'][^>]*content=["\']([^"\']+)["\']', html, flags=re.I)
    if m:
        val = m.group(1).strip()
        # sometimes comes as 'doi:10.xxx' or full URL
        if val.lower().startswith('doi:'):
            val = val.split(':', 1)[1]
        if val.lower().startswith('http://') or val.lower().startswith('https://'):
            try:
                parsed = urlparse(val)
                v = unquote(parsed.path.lstrip('/'))
                return normalize_doi(v)
            except Exception:
                pass
        try:
            return normalize_doi(val)
        except DOIError:
            pass

    # link tags and explicit DOI hrefs
    m = re.search(r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']', html, flags=re.I)
    if m:
        try:
            return normalize_doi(unquote(m.group(1).strip()))
        except DOIError:
            pass

    # Any /10.xxx/ pattern in href/src attributes
    m = re.search(r'(?:href|src)=["\'][^"\']*(10\.\d{4,9}/[^"\']+)["\']', html, flags=re.I)
    if m:
        try:
            return normalize_doi(m.group(1).strip())
        except DOIError:
            pass

    # last resort: any DOI-like substring in the page
    m = re.search(r'10\.\d{4,9}/[^\s"\'"<>]+', html)
    if m:
        try:
            return normalize_doi(m.group(0))
        except DOIError:
            pass

    return None


def fetch_bibtex(identifier: str, timeout: int = 15, normalize: bool = True) -> str:
    """Convenience wrapper for programmatic use.

    - identifier: DOI, DOI URL, arXiv id/URL, or publisher URL (same as CLI)
    - timeout: network timeout in seconds
    - normalize: if True (default), pass the fetched BibTeX through
      `doi2bib3.utils.normalize_bibtex` before returning. If False, the
      raw text from doi.org / Crossref is returned.

    This keeps `get_bibtex_from_doi` behaviour intact for callers that
    expect the raw provider output, while giving a convenient API for
    library users who want the nicely formatted BibTeX the CLI prints.
    """
    raw = get_bibtex_from_doi(identifier, timeout=timeout)
    if normalize:
        try:
            return normalize_bibtex(raw)
        except Exception:
            # If normalization fails for any reason, fall back to raw text
            return raw
    return raw
