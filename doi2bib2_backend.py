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

"""Fetch BibTeX for DOI / resolve PMID / arXiv ID to DOI.

Functions:
- get_bibtex_from_doi(doi) -> str
- pmid_to_doi(pmid) -> str or None
- arxiv_to_doi(arxivid) -> str or None

Raises requests.HTTPError on non-200 responses.
"""
from typing import Optional
import re
import requests
from urllib.parse import urlparse, unquote

DOI_REGEX = re.compile(r"^10\..+/.+$")


def normalize_doi(doi_input: str) -> str:
    """Normalize a DOI input to the bare DOI string.

    Accepts inputs like:
    - "10.48550/arXiv.2411.08091"
    - "https://doi.org/10.48550/arXiv.2411.08091"
    - "http://dx.doi.org/10.48550/arXiv.2411.08091"
    - "doi:10.48550/arXiv.2411.08091"

    Returns the bare DOI (e.g. "10.48550/arXiv.2411.08091") or raises DOIError.
    """
    s = doi_input.strip()

    # handle doi: prefix
    if s.lower().startswith('doi:'):
        s = s[4:]

    # handle URL forms
    if s.lower().startswith('http://') or s.lower().startswith('https://'):
        parsed = urlparse(s)
        # take the path component (drop leading slash)
        s = parsed.path.lstrip('/')

    # decode percent-encoding
    s = unquote(s)

    if DOI_REGEX.match(s):
        return s
    raise DOIError(f"Invalid DOI: {doi_input}")


class DOIError(Exception):
    pass


def get_bibtex_from_doi(doi: str, timeout: int = 15) -> str:
    """Fetch BibTeX for a DOI using content negotiation.

    Raises:
        DOIError: if DOI is invalid or remote returns non-200.
    """
    doi = normalize_doi(doi)

    headers = {
        'Accept': 'application/x-bibtex; charset=utf-8',
        'User-Agent': 'doi2bib-python/1.0'
    }
    url = f'https://doi.org/{doi}'
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 200:
        return resp.text
    else:
        raise DOIError(f"Failed to fetch DOI {doi}: HTTP {resp.status_code}")


# def pmid_to_doi(pmid: str, timeout: int = 15) -> Optional[str]:
#     """Resolve a PubMed PMID (or PMC id) to DOI using NCBI idconv service.

#     Returns DOI string or None if not found.
#     """
#     pmid = pmid.strip()
#     if not re.match(r"^\d+$|^PMC\d+(\.\d+)?$", pmid):
#         raise ValueError("Invalid PMID")

#     url = f'http://www.pubmedcentral.nih.gov/utils/idconv/v1.0/?format=json&ids={pmid}'
#     resp = requests.get(url, timeout=timeout)
#     if resp.status_code != 200:
#         raise DOIError(f"PubMed ID conversion failed: HTTP {resp.status_code}")
#     data = resp.json()
#     records = data.get('records')
#     if not records or not records[0]:
#         return None
#     return records[0].get('doi')


def arxiv_to_doi(arxivid: str, timeout: int = 15) -> Optional[str]:
    """Resolve an arXiv id to DOI using the arXiv API.

    Returns DOI string or None if not found.
    """
    arxivid = arxivid.strip()
    # accept optional "arXiv:" prefix
    if arxivid.lower().startswith('arxiv:'):
        arxivid = arxivid.split(':', 1)[1].strip()

    if not re.match(r"^\d+\.\d+(v(\d+))?$", arxivid):
        raise ValueError("Invalid arXiv ID")

    url = f'https://export.arxiv.org/api/query?id_list={arxivid}'
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise DOIError(f"arXiv query failed: HTTP {resp.status_code}")
    # parse XML (naively) to look for DOI in several possible places:
    text = resp.text
    # 1) <arxiv:doi ...>value</arxiv:doi> (may include xmlns attributes)
    m = re.search(r"<arxiv:doi\b[^>]*>([^<]+)</arxiv:doi>", text)
    if m:
        return m.group(1).strip()
    # 2) <doi>value</doi>
    m = re.search(r"<doi\b[^>]*>([^<]+)</doi>", text)
    if m:
        return m.group(1).strip()
    # 3) links like href="https://doi.org/10.xxxx/..."
    m = re.search(r'href=["\']https?://(?:dx\.)?doi\.org/([^"\']+)["\']', text)
    if m:
        return unquote(m.group(1).strip())
    return None
