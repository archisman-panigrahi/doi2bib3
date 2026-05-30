from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3.bibitem import format_bibtex_to_aps_bibitem
from doi2bib3.backend import DOIError


def test_format_bibtex_to_aps_bibitem_uses_normalized_fields():
    bib = r"""@article{Englert_twenty-four_2008,
 author = {Fran\c{c}ois Englert and Kasper Peeters and Anne Taormina},
 journal = {Phys. Rev. E},
 pages = {031908},
 title = {{Twenty-four} near-instabilities of {Caspar-Klug} viruses},
 url = {http://dx.doi.org/10.1103/PhysRevE.78.031908},
 volume = {78},
 year = {2008}
}
"""

    assert format_bibtex_to_aps_bibitem(bib) == (
        "\\bibitem{Englert_twenty-four_2008}\n"
        "F. Englert, K. Peeters, and A. Taormina, "
        "Twenty-four near-instabilities of Caspar-Klug viruses, "
        "\\href{https://doi.org/10.1103/PhysRevE.78.031908}"
        "{Phys. Rev. E \\textbf{78}, 031908 (2008)}.\n"
    )


def test_format_bibtex_to_aps_bibitem_allows_custom_key():
    bib = r"""@article{original_key,
 author = {Aspelmeyer, Markus},
 title = {{Measured} measurement},
 year = {2009}
}
"""

    assert format_bibtex_to_aps_bibitem(bib, key="custom") == (
        "\\bibitem{custom}\n"
        "M. Aspelmeyer, Measured measurement (2009).\n"
    )


def test_format_bibtex_to_aps_bibitem_shows_arxiv_eprint_for_unpublished():
    bib = r"""@misc{Doe_2025,
 author = {Doe, Jane and Smith, John},
 archivePrefix = {arXiv},
 eprint = {2501.12345},
 primaryClass = {cond-mat.str-el},
 title = {A preprint about something},
 year = {2025}
}
"""

    assert format_bibtex_to_aps_bibitem(bib) == (
        "\\bibitem{Doe_2025}\n"
        "J. Doe, and J. Smith, "
        "A preprint about something, "
        "\\href{https://arxiv.org/abs/2501.12345}{arXiv:2501.12345} (2025).\n"
    )


def test_format_bibtex_to_aps_bibitem_shows_first_page_for_aps_page_ranges():
    bib = r"""@article{Englert_2014,
 author = {Englert, Berthold-Georg},
 journal = {Phys. Rev. A},
 pages = {843--850},
 publisher = {American Physical Society (APS)},
 title = {An APS paper with a page range},
 volume = {89},
 year = {2014}
}
"""

    assert format_bibtex_to_aps_bibitem(bib) == (
        "\\bibitem{Englert_2014}\n"
        "B. G. Englert, An APS paper with a page range, "
        "Phys. Rev. A \\textbf{89}, 843 (2014).\n"
    )


def test_format_bibtex_to_aps_bibitem_keeps_non_aps_page_ranges():
    bib = r"""@article{Florencio_2015,
 author = {Florencio, Joao},
 journal = {Example Journal},
 pages = {53--59},
 publisher = {Example Publisher},
 title = {A non APS paper with a page range},
 volume = {10},
 year = {2015}
}
"""

    assert format_bibtex_to_aps_bibitem(bib) == (
        "\\bibitem{Florencio_2015}\n"
        "J. Florencio, A non APS paper with a page range, "
        "Example Journal \\textbf{10}, 53--59 (2015).\n"
    )


def test_format_bibtex_to_aps_bibitem_rejects_empty_bibtex():
    with pytest.raises(DOIError):
        format_bibtex_to_aps_bibitem("")
