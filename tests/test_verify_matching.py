# SPDX-License-Identifier: GPL-3.0-only
"""Pure-logic tests for the verify matching helpers (no network)."""

import pytest

from doi2bib3.verify.matching import (
    author_overlap,
    clean,
    contained,
    normalize,
    similarity,
    strip_markup,
)


@pytest.mark.imported
def test_strip_markup_removes_xml_and_latex_and_entities() -> None:
    raw = r"<mml:math><mml:mi>A</mml:mi></mml:math>{\bf B} &amp; C"
    assert strip_markup(raw).replace(" ", "") == "AB&C"


@pytest.mark.imported
def test_normalize_lowercases_and_drops_punctuation() -> None:
    assert normalize("On the {Origin} of Species!") == "on the origin of species"


@pytest.mark.imported
def test_similarity_is_one_for_identical_titles() -> None:
    assert similarity("Foo Bar Baz", "Foo Bar Baz") == 1.0


@pytest.mark.imported
def test_similarity_is_high_for_subtitle_difference() -> None:
    # CrossRef stores the main title only; the BibTeX entry includes the
    # subtitle. The verifier should treat these as the same publication.
    a = "Topology and Geometry for Physicists"
    b = "Topology and Geometry for Physicists: a Modern Treatment"
    assert similarity(a, b) >= 0.9


@pytest.mark.imported
def test_similarity_is_low_for_unrelated_titles() -> None:
    assert similarity("Quantum entanglement primer", "Banana bread recipe") < 0.5


@pytest.mark.imported
def test_contained_requires_at_least_four_words() -> None:
    assert contained("alpha beta gamma delta", "alpha beta gamma delta epsilon")
    # Short fragments must not match -- they would cause spurious verdicts.
    assert not contained("alpha beta", "alpha beta gamma delta")


@pytest.mark.imported
def test_clean_collapses_whitespace_and_strips_markup() -> None:
    assert clean("  <jats:p>Hello,\nworld!</jats:p>  ") == "Hello, world!"


@pytest.mark.imported
def test_author_overlap_uses_surnames() -> None:
    bib = ["Aspelmeyer, Markus", "Doe, Jane"]
    record = ["Markus Aspelmeyer", "Other Person"]
    # 1/2 of the record's authors have surnames present in the bib entry.
    assert author_overlap(bib, record) == 0.5


@pytest.mark.imported
def test_author_overlap_handles_empty_inputs() -> None:
    assert author_overlap([], ["A B"]) == 0.0
    assert author_overlap(["A B"], []) == 0.0
