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

"""Backend functions for doi2bib2 package.

This file is a copy of the top-level `doi2bib2_backend.py` but placed inside the
package so packaging and imports are clean. Keep function names identical.
"""
from typing import Optional
import re
import requests
from urllib.parse import urlparse, unquote

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


def pmid_to_doi(pmid: str, timeout: int = 15) -> Optional[str]:
    pmid = pmid.strip()
    if not re.match(r"^\d+$|^PMC\d+(\.\d+)?$", pmid):
        raise ValueError("Invalid PMID")

    url = f'http://www.pubmedcentral.nih.gov/utils/idconv/v1.0/?format=json&ids={pmid}'
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise DOIError(f"PubMed ID conversion failed: HTTP {resp.status_code}")
    data = resp.json()
    records = data.get('records')
    if not records or not records[0]:
        return None
    return records[0].get('doi')


def arxiv_to_doi(arxivid: str, timeout: int = 15) -> Optional[str]:
    arxivid = arxivid.strip()
    if arxivid.lower().startswith('arxiv:'):
        arxivid = arxivid.split(':', 1)[1].strip()

    if not re.match(r"^\d+\.\d+(v(\d+))?$", arxivid):
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
