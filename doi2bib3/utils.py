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

"""Utilities for bib normalization and IO inside the package."""
from typing import Optional
import re
import urllib.parse
import bibtexparser
import os
import requests
import json

SPECIAL_CHARS = {
    'a\u0300': "\\`a",
    '\u00f4': "\\^o",
    '\u00ea': "\\^e",
    '\u00e2': "\\^a",
    '\u00ae': '{\\textregistered}',
    '\u00e7': "\\c{c}",
    '\u00f6': "\\\"{o}",
    '\u00e4': "\\\"{a}",
    '\u00fc': "\\\"{u}",
    '\u00d6': "\\\"{O}",
    '\u00c4': "\\\"{A}",
    '\u00dc': "\\\"{U}"
}


VAR_RE = re.compile(r"(\\{)(\\var[A-Z]?[a-z]*)(\\})")


def _load_journal_replacements():
    """Load journal name replacement dictionaries from JSON files."""
    replacements = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    for json_file in ['APS_replacement.json', 'Nature_replacement.json']:
        file_path = os.path.join(current_dir, json_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                replacements.update(data)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is invalid JSON, skip silently
            pass
    
    return replacements


# Load journal replacements once at module initialization
_JOURNAL_REPLACEMENTS = _load_journal_replacements()


def abbreviate_journal_name(journal: str) -> str:
    """Replace journal name with its abbreviation if found in replacement dicts.
    
    Checks exact matches first, then case-insensitive matches.
    """
    if not journal:
        return journal
    
    # Try exact match first
    if journal in _JOURNAL_REPLACEMENTS:
        return _JOURNAL_REPLACEMENTS[journal]
    
    # Try case-insensitive match
    for full_name, abbrev in _JOURNAL_REPLACEMENTS.items():
        if full_name.lower() == journal.lower():
            return abbrev
    
    # No match found, return original
    return journal


def insert_dollars(title: str) -> str:
    return VAR_RE.sub(r"\\1$\\2$\\3", title)


def protect_capitalized_words(title: str) -> str:
    """Wrap capitalized words in curly braces for BibTeX title protection.
    
    This protects words that start with a capital letter from being
    lowercased by BibTeX bibliography styles. Handles words after hyphens too.
    
    Examples:
    - "Non-Fermi Liquids" -> "{Non}-{Fermi} {Liquids}"
    - "van der Waals" -> "van der {Waals}"
    """
    # Pattern to match:
    # 1. A word that starts with a capital letter (including after hyphen)
    # 2. The word can contain letters, numbers, and hyphens
    # We need to be careful not to wrap words that are already in braces
    
    result = []
    i = 0
    while i < len(title):
        # Check if we're at the start of an already-braced section
        if title[i] == '{':
            # Find the matching closing brace
            brace_count = 1
            j = i + 1
            while j < len(title) and brace_count > 0:
                if title[j] == '{':
                    brace_count += 1
                elif title[j] == '}':
                    brace_count -= 1
                j += 1
            # Keep the braced content as-is
            result.append(title[i:j])
            i = j
        # Check if we're at the start of a word with a capital letter
        elif title[i].isupper():
            # Collect the word (letters, numbers, and hyphens)
            j = i
            while j < len(title) and (title[j].isalnum() or title[j] == '-'):
                j += 1
            word = title[i:j]
            result.append('{' + word + '}')
            i = j
        else:
            result.append(title[i])
            i += 1
    
    return ''.join(result)


def encode_special_chars(value: str) -> str:
    for k, v in SPECIAL_CHARS.items():
        value = value.replace(k, v)
    return value


def fetch_article_number_from_crossref(doi: str, timeout: int = 10) -> Optional[str]:
    """Fetch article-number from Crossref API for a given DOI.
    
    Returns the article-number if found, None otherwise.
    """
    try:
        # Remove any prefix from DOI
        doi_clean = doi.strip()
        if doi_clean.lower().startswith('doi:'):
            doi_clean = doi_clean[4:].strip()
        
        url = f'https://api.crossref.org/works/{urllib.parse.quote(doi_clean, safe="")}'
        resp = requests.get(url, timeout=timeout)
        
        if resp.status_code == 200:
            data = resp.json()
            message = data.get('message', {})
            article_number = message.get('article-number')
            return article_number
    except Exception:
        pass
    
    return None


def normalize_bibtex(bib_str: str) -> str:
    bib_db = bibtexparser.loads(bib_str)
    for entry in bib_db.entries:
        if 'ID' in entry:
            entry['ID'] = entry['ID'].replace('_', '')

    def _make_bibtex_key(entry):
        """Generate a key of the form `Lastname_firstword_year`.

        - `lastname`: last name of the first author (comma or space name formats supported)
        - `firstword`: first word of the title (braces/quotes removed)
        - `year`: value of the `year` field if present

        The result is lowercased and non-alphanumeric characters (except hyphen)
        are removed from each component. If the generated key already exists
        in `seen`, a, b, c... suffixes are appended to disambiguate.
        """
        def _clean(s, lower=True):
            if not s:
                return ''
            s = s.strip()
            # remove surrounding braces/quotes
            s = re.sub(r'^[{\"\']+|[}\"\']+$', '', s)
            if lower:
                s = s.lower()
                # keep letters, digits and hyphens
                s = re.sub(r'[^a-z0-9\-]+', '', s)
            else:
                # preserve case for parts like last name; allow letters (both cases), digits and hyphens
                s = re.sub(r'[^A-Za-z0-9\-]+', '', s)
            return s

        # first author
        auth = entry.get('author', '')
        firstname_lastname = ''
        if auth:
            # bibtexparser leaves authors as single string with ' and ' separators
            first_author = auth.split(' and ')[0].strip()
            if ',' in first_author:
                # format: Last, First
                lastname = first_author.split(',', 1)[0].strip()
            else:
                # format: First Last
                parts = first_author.split()
                lastname = parts[-1] if parts else ''
            firstname_lastname = _clean(lastname, lower=False)

        # first word of title
        title = entry.get('title', '')
        firstword = ''
        if title:
            # remove surrounding braces and LaTeX macros roughly
            t = re.sub(r'[{}]', '', title)
            # split on whitespace and punctuation
            tw = re.split(r'\s+', t.strip())
            if tw:
                firstword = _clean(tw[0])

        year = _clean(entry.get('year', ''))

        base = '_'.join(p for p in (firstname_lastname, firstword, year) if p)
        if not base:
            # fallback to original ID or a short randomish fallback
            base = _clean(entry.get('ID', 'entry')) or 'entry'

        # Return the base key directly (no collision tracking / suffixing).
        return base

    # regenerate keys (no collision tracking)
    for entry in bib_db.entries:
        new_id = _make_bibtex_key(entry)
        entry['ID'] = new_id
        pages = entry.get('pages')
        if pages:
            # Normalize common N/A variants to remove the field entirely
            norm = pages.strip().lower()
            if norm in ('n/a-n/a', 'na-na', 'n/a', 'na'):
                entry.pop('pages', None)
            else:
                p = pages
                # Convert unicode en-dash/em-dash to ASCII double-hyphen
                p = p.replace('\u2013', '--').replace('\u2014', '--')
                # Replace en/em characters themselves if present
                p = p.replace('\u2013', '--').replace('\u2014', '--')
                # Replace any literal en-dash/em-dash characters too
                p = p.replace('\u2013', '--').replace('\u2014', '--')
                p = p.replace('–', '--').replace('—', '--')
                # Replace single hyphen between digits (with optional spaces)
                # e.g. '1932-1938', '1932 - 1938', '1932-1938.e3' -> '1932--1938' or '1932--1938.e3'
                p = re.sub(r'(?<=\d)\s*-[\u2013\u2014-]?\s*(?=\d)', '--', p)
                # If no double-dash already, ensure we don't inadvertently
                # convert word hyphens — only numeric ranges should be changed
                entry['pages'] = p
        # For American Physical Society journals, fetch article-number from Crossref if no pages
        # Do this BEFORE removing DOI (which happens if URL is present)
        publisher = entry.get('publisher', '').strip()
        if 'American Physical Society' in publisher and not pages:
            doi = entry.get('doi', '').strip()
            if doi:
                article_num = fetch_article_number_from_crossref(doi)
                if article_num:
                    entry['pages'] = article_num
        if 'url' in entry:
            entry['url'] = urllib.parse.unquote(entry['url'])
            # Remove DOI field if URL is present
            entry.pop('doi', None)
        if 'title' in entry:
            entry['title'] = insert_dollars(entry['title'])
            entry['title'] = protect_capitalized_words(entry['title'])
        if 'journal' in entry:
            entry['journal'] = abbreviate_journal_name(entry['journal'])
        if 'month' in entry:
            entry['month'] = entry['month'].strip()
            if entry['month'].startswith('{') and entry['month'].endswith('}'):
                entry['month'] = entry['month'][1:-1]
        for key in list(entry.keys()):
            if key in ['title', 'journal', 'booktitle']:
                entry[key] = encode_special_chars(entry[key])

    return bibtexparser.dumps(bib_db)


def save_bibtex_to_file(bib_str: str, path: str, append: bool = False) -> None:
    if not append:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(bib_str)
        return

    prefix = ''
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, 'rb') as fh:
                fh.seek(-1, os.SEEK_END)
                last = fh.read(1)
            if last != b"\n":
                prefix = "\n"
    except OSError:
        prefix = "\n"

    with open(path, 'a', encoding='utf-8') as f:
        if prefix:
            f.write(prefix)
        f.write(bib_str)


def cli_doi2bib3(argv=None):
    """A thin CLI wrapper to mirror the main.py behavior (entry point).

    This function is intended to be callable programmatically with an argv
    list (like sys.argv[1:]) and also used as the console script entry point.
    """
    import argparse
    import sys
    from .backend import get_bibtex_from_doi

    p = argparse.ArgumentParser(
        description='Fetch BibTeX by DOI, DOI URL, arXiv id or arXiv URL'
    )
    p.add_argument('identifier', nargs='?', help='DOI, DOI URL, arXiv id/URL, or publisher URL')
    p.add_argument('-o', '--out', help='Write .bib file to this path')

    args = p.parse_args(argv)

    if not args.identifier:
        p.print_help()
        sys.exit(2)

    ident = args.identifier
    out = args.out

    try:
        bib = get_bibtex_from_doi(ident)
    except Exception as e:
        print('Error:', e, file=sys.stderr)
        sys.exit(1)

    bib = normalize_bibtex(bib)
    if out:
        save_bibtex_to_file(bib, out, append=True)
        print('Wrote', out)
    else:
        print(bib)


if __name__ == '__main__':
    cli_doi2bib3()
