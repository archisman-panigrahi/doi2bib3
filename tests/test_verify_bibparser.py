# SPDX-License-Identifier: GPL-3.0-only
"""Pure-logic tests for the verify BibTeX parser (no network)."""

import pytest

from doi2bib3.verify.bibparser import BibEntry, normalize_doi, parse_bibtex


SAMPLE = r"""
@string{nat = "Nature"}

@article{einstein1905,
  author = {Einstein, Albert and Other, Author},
  title  = {On the Electrodynamics of {Moving} Bodies},
  year   = {1905},
  doi    = {10.1002/andp.19053221004},
  journal= nat
}

@misc{arxiv_demo,
  title = {A preprint},
  eprint = {2411.08091},
  archiveprefix = {arXiv},
  year = 2024,
}

@comment{a stray comment block}
"""


@pytest.mark.imported
def test_parse_bibtex_returns_two_entries() -> None:
    entries = parse_bibtex(SAMPLE)
    assert [e.key for e in entries] == ["einstein1905", "arxiv_demo"]


@pytest.mark.imported
def test_string_substitution_works() -> None:
    entry = parse_bibtex(SAMPLE)[0]
    assert entry.get("journal") == "Nature"


@pytest.mark.imported
def test_authors_and_year_are_extracted() -> None:
    entry = parse_bibtex(SAMPLE)[0]
    assert entry.authors == ["Einstein, Albert", "Other, Author"]
    assert entry.year == "1905"


@pytest.mark.imported
def test_doi_is_normalised() -> None:
    entry = parse_bibtex(SAMPLE)[0]
    assert entry.doi == "10.1002/andp.19053221004"


@pytest.mark.imported
def test_arxiv_id_detection_from_eprint() -> None:
    entry = parse_bibtex(SAMPLE)[1]
    assert entry.arxiv_id == "2411.08091"


@pytest.mark.imported
def test_normalize_doi_strips_prefixes_and_punctuation() -> None:
    assert normalize_doi("https://doi.org/10.1038/nphys1170.") == "10.1038/nphys1170"
    assert normalize_doi("DOI: 10.1038/Nphys1170") == "10.1038/nphys1170"
    assert normalize_doi("") == ""


@pytest.mark.imported
def test_unknown_block_is_skipped_not_fatal() -> None:
    text = "@string{not closed"  # malformed -- parser must not crash
    assert parse_bibtex(text) == []
