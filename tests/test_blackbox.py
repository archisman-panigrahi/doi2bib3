#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only

"""External pytest checks by pytest on datawarrior_clustersort.py.

Checks in this file probe the application as a whole from the outside
(blackbox tests) marked by `blackbox`.  It is complemented by checks
defined in file `test_with_imports.py` labelled by `imported`."""

import os
import subprocess
import sys

import pytest

PRG = "scripts/doi2bib3"


@pytest.mark.blackbox
def test_script_exists() -> None:
    """Check for the script's presence."""
    assert os.path.isfile(PRG), f"script {PRG} was not found"


import subprocess
import pytest


@pytest.mark.blackbox
@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (
            "10.1038/nphys1170",
            r"""@article{Aspelmeyer_measured_2009,
 author = {Aspelmeyer, Markus},
 issn = {1745-2481},
 journal = {Nat. Phys.},
 month = {January},
 number = {1},
 pages = {11--12},
 publisher = {Springer Science and Business Media LLC},
 title = {{Measured} measurement},
 url = {http://dx.doi.org/10.1038/nphys1170},
 volume = {5},
 year = {2009}
}

""",
        ),
        (
            "https://doi.org/10.1038/nphys1170",
            r"""@article{Aspelmeyer_measured_2009,
 author = {Aspelmeyer, Markus},
 issn = {1745-2481},
 journal = {Nat. Phys.},
 month = {January},
 number = {1},
 pages = {11--12},
 publisher = {Springer Science and Business Media LLC},
 title = {{Measured} measurement},
 url = {http://dx.doi.org/10.1038/nphys1170},
 volume = {5},
 year = {2009}
}

""",
        ),
        (
            "arXiv:2411.08091",
            r"""@article{Panigrahi_non-fermi_2025,
 author = {Panigrahi, Archisman and Kumar, Ajesh},
 issn = {1079-7114},
 journal = {Phys. Rev. Lett.},
 month = {June},
 number = {23},
 pages = {236502},
 publisher = {American Physical Society (APS)},
 title = {{Non-Fermi} {Liquids} from {Subsystem} {Symmetry} {Breaking} in van der {Waals} {Multilayers}},
 url = {http://dx.doi.org/10.1103/v6r7-4ph9},
 volume = {134},
 year = {2025}
}

""",
        ),
    ],
)
def test_article_output(capfd, input_value, expected_output) -> None:
    """Check .bib generation at level of the CLI."""
    subprocess.run(f"python {PRG} {input_value}", shell=True, check=True)
    out, err = capfd.readouterr()
    assert expected_output.splitlines() == out.splitlines()


@pytest.mark.blackbox
@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (
            '"Projected Topological Branes"',
            r"""@article{Panigrahi_projected_2022,
 author = {Panigrahi, Archisman and Juričić, Vladimir and Roy, Bitan},
 issn = {2399-3650},
 journal = {Commun. Phys.},
 month = {September},
 number = {1},
 publisher = {Springer Science and Business Media LLC},
 title = {{Projected} topological branes},
 url = {http://dx.doi.org/10.1038/s42005-022-01006-x},
 volume = {5},
 year = {2022}
}

""",
        ),
    ],
)
@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="This test is not supported on Windows."
)
def test_article_fuzzy_title(capfd, input_value, expected_output) -> None:
    """Check .bib generation at level of the CLI."""
    subprocess.run(f"python {PRG} {input_value}", shell=True, check=True)
    out, err = capfd.readouterr()
    assert expected_output == out
