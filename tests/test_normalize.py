from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3.normalize import normalize_bibtex


@pytest.mark.imported
def test_normalize_bibtex_handles_unbraced_month_macro():
    raw = """@article{Nazaryan_2024,
 title={Nonlocal conductivity, continued fractions, and current vortices in electron fluids},
 volume={110},
 ISSN={2469-9969},
 url={http://dx.doi.org/10.1103/physrevb.110.045147},
 DOI={10.1103/physrevb.110.045147},
 number={4},
 pages={045147},
 journal={Physical Review B},
 publisher={American Physical Society (APS)},
 author={Nazaryan, Khachatur G. and Levitov, Leonid},
 year={2024},
 month=july
}
"""

    out = normalize_bibtex(raw)

    assert "@article{" in out
    assert "month = {July}" in out
    assert "journal = {Phys. Rev. B}" in out
