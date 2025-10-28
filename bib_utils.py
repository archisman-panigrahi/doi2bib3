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

"""Utilities to normalize and pretty-print BibTeX entries.

Relies on bibtexparser to parse and dump entries so we can safely edit fields.
"""
from typing import Optional
import re
import urllib.parse
import bibtexparser
import os

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


VAR_RE = re.compile(r"(\{)(\\var[A-Z]?[a-z]*)(\})")


def insert_dollars(title: str) -> str:
    """Wrap occurrences like {\varX} into {$\varX$} to help TeX math tokens.
    """
    return VAR_RE.sub(r"\1$\2$\3", title)


def encode_special_chars(value: str) -> str:
    # naive replacement of special characters
    for k, v in SPECIAL_CHARS.items():
        value = value.replace(k, v)
    return value


def normalize_bibtex(bib_str: str) -> str:
    """Parse a BibTeX string, normalize some fields and return cleaned BibTeX.

    Changes made:
    - removes pages if value == 'n/a-n/a'
    - converts single hyphen in pages to double hyphen
    - decodes percent-encoded URL
    - wraps \var... tokens in title with $...$
    - removes underscores from entry ID
    - encodes a small set of special characters
    """
    bib_db = bibtexparser.loads(bib_str)
    for entry in bib_db.entries:
        # ID cleanup
        if 'ID' in entry:
            entry['ID'] = entry['ID'].replace('_', '')
        # pages
        pages = entry.get('pages')
        if pages:
            if pages.lower() == 'n/a-n/a':
                entry.pop('pages', None)
            else:
                if '--' not in pages:
                    entry['pages'] = pages.replace('-', '--')
        # url decode
        if 'url' in entry:
            entry['url'] = urllib.parse.unquote(entry['url'])
        # title handling
        if 'title' in entry:
            entry['title'] = insert_dollars(entry['title'])
        # month remove surrounding braces
        if 'month' in entry:
            entry['month'] = entry['month'].strip()
            if entry['month'].startswith('{') and entry['month'].endswith('}'):
                entry['month'] = entry['month'][1:-1]
        # encode special chars
        for key in list(entry.keys()):
            if key in ['title', 'journal', 'booktitle']:
                entry[key] = encode_special_chars(entry[key])

    return bibtexparser.dumps(bib_db)


def save_bibtex_to_file(bib_str: str, path: str, append: bool = False) -> None:
    """Write or append a BibTeX string to `path`.

    If `append` is False (default) the file is overwritten (same as before).
    If `append` is True the bib string is appended. A separating newline is
    added when the file already exists and is non-empty.
    """
    if not append:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(bib_str)
        return

    # append mode: ensure a separating newline if file exists and non-empty
    prefix = ''
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            # check last byte to avoid doubling newlines
            with open(path, 'rb') as fh:
                fh.seek(-1, os.SEEK_END)
                last = fh.read(1)
            if last != b"\n":
                prefix = "\n"
    except OSError:
        # if any issue checking file, just proceed without prefix
        prefix = "\n"

    with open(path, 'a', encoding='utf-8') as f:
        if prefix:
            f.write(prefix)
        f.write(bib_str)