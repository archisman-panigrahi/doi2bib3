# SPDX-License-Identifier: GPL-3.0-only
"""Pure-logic tests for the cite-key cross-checker (no network)."""

import pytest

from doi2bib3.verify.citecheck import check_cite_keys, extract_cite_keys


@pytest.mark.imported
def test_extract_cite_keys_handles_cite_family() -> None:
    tex = r"""
    See \cite{a} and \citep{b, c}. Also \autocite[p.~5]{d}, and
    \citeauthor*{e}. Some prose, and finally \nocite{f}.
    % A commented \cite{ignored} key.
    """
    assert extract_cite_keys(tex) == {"a", "b", "c", "d", "e", "f"}


@pytest.mark.imported
def test_check_cite_keys_reports_undefined_and_unused() -> None:
    tex = [r"Body cites \cite{a, b} and \cite{ghost}."]
    defined = {"a", "b", "unused_key"}
    result = check_cite_keys(tex, defined)
    assert result.undefined == {"ghost"}
    assert result.unused == {"unused_key"}
    assert result.cited == {"a", "b", "ghost"}


@pytest.mark.imported
def test_check_cite_keys_with_no_inputs() -> None:
    result = check_cite_keys([], set())
    assert result.cited == set()
    assert result.defined == set()
    assert result.undefined == set()
    assert result.unused == set()


@pytest.mark.imported
def test_to_dict_returns_sorted_lists() -> None:
    result = check_cite_keys([r"\cite{c, a, b, missing}"], {"a", "b", "c"})
    payload = result.to_dict()
    assert payload["undefined"] == ["missing"]
    assert payload["unused"] == []
    assert payload["citedCount"] == 4
    assert payload["definedCount"] == 3
