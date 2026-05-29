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
        "{Phys. Rev. E \\textbf{78}, 031908} (2008)\n"
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
        "M. Aspelmeyer, Measured measurement (2009)\n"
    )


def test_format_bibtex_to_aps_bibitem_rejects_empty_bibtex():
    with pytest.raises(DOIError):
        format_bibtex_to_aps_bibitem("")
