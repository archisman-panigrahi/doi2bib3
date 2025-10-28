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
    return VAR_RE.sub(r"\1$\2$\3", title)


def encode_special_chars(value: str) -> str:
    for k, v in SPECIAL_CHARS.items():
        value = value.replace(k, v)
    return value


def normalize_bibtex(bib_str: str) -> str:
    bib_db = bibtexparser.loads(bib_str)
    for entry in bib_db.entries:
        if 'ID' in entry:
            entry['ID'] = entry['ID'].replace('_', '')
        pages = entry.get('pages')
        if pages:
            if pages.lower() == 'n/a-n/a':
                entry.pop('pages', None)
            else:
                if '--' not in pages:
                    entry['pages'] = pages.replace('-', '--')
        if 'url' in entry:
            entry['url'] = urllib.parse.unquote(entry['url'])
        if 'title' in entry:
            entry['title'] = insert_dollars(entry['title'])
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


def cli_main(argv=None):
    """A thin CLI wrapper to mirror the old main.py behavior."""
    import argparse
    import sys
    from .backend import get_bibtex_from_doi, arxiv_to_doi

    p = argparse.ArgumentParser(description='Fetch BibTeX by DOI or arXiv id')
    sub = p.add_subparsers(dest='cmd')

    # simple explicit command: `doi <DOI>`
    doi_cmd = sub.add_parser('doi', help='Fetch BibTeX by DOI')
    doi_cmd.add_argument('doi', help='DOI string (e.g. 10.1038/nphys1170)')
    doi_cmd.add_argument('-o', '--out', help='Write .bib file to this path')

    # simple arXiv command: `arxiv <arXiv-id>`
    arxiv_cmd = sub.add_parser('arxiv', help='Resolve arXiv id to DOI and fetch BibTeX')
    arxiv_cmd.add_argument('id', help='arXiv id (e.g. 2411.08091)')
    arxiv_cmd.add_argument('-o', '--out', help='Write .bib file to this path')

    args = p.parse_args(argv)

    if args.cmd == 'doi':
        doi_value = args.doi
        out = args.out

        if not doi_value:
            print('Please provide a DOI (usage: doi <DOI>)', file=sys.stderr)
            sys.exit(2)
        bib = get_bibtex_from_doi(doi_value)
        bib = normalize_bibtex(bib)
        if out:
            save_bibtex_to_file(bib, out, append=True)
            print('Wrote', out)
        else:
            print(bib)

    # elif args.cmd == 'pmid':
    #     if not args.pmid:
    #         print('Please provide --pmid', file=sys.stderr)
    #         sys.exit(2)
    #     doi = pmid_to_doi(args.pmid)
    #     if not doi:
    #         print('No DOI found for PMID', args.pmid)
    #         sys.exit(3)
    #     bib = get_bibtex_from_doi(doi)
    #     bib = normalize_bibtex(bib)
    #     if args.out:
    #         save_bibtex_to_file(bib, args.out, append=True)
    #         print('Wrote', args.out)
    #     else:
    #         print(bib)

    elif args.cmd == 'arxiv':
        arxv = args.id
        out = args.out

        if not arxv:
            print('Please provide arXiv id (usage: arxiv <id>)', file=sys.stderr)
            sys.exit(2)
        doi = arxiv_to_doi(arxv)
        if not doi:
            print('No DOI found for arXiv id', arxv)
            sys.exit(3)
        bib = get_bibtex_from_doi(doi)
        bib = normalize_bibtex(bib)
        if out:
            save_bibtex_to_file(bib, out, append=True)
            print('Wrote', out)
        else:
            print(bib)

    else:
        p.print_help()


if __name__ == '__main__':
    cli_main()
