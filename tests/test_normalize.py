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


def test_normalize_bibtex_encodes_real_accented_article_metadata():
    raw = """@article{Florencio_2015,
 title={Enmeshed bodies, impossible touch: The object-oriented world of Pina Bausch's Café Müller},
 author={Florêncio, João},
 journal={Performance Research},
 year={2015},
 volume={20},
 number={2},
 pages={53--59},
 url={https://doi.org/10.1080/13528165.2015.1026719}
}
"""

    out = normalize_bibtex(raw)

    assert "@article{Florencio_enmeshed_2015," in out
    assert "author = {Flor\\^{e}ncio, Jo\\~{a}o}" in out
    assert "{Caf\\'{e}} {M\\\"{u}ller}" in out


def test_normalize_bibtex_encodes_real_accented_booktitle_metadata():
    raw = """@inproceedings{Dennert_2013,
 title={Advanced concepts for flexible data integration in heterogeneous production environments},
 author={Dennert, Alexander and Garcia Izaguirre Montemayor, Jorge and Krause, Jakob and Hesse, Stefan and Martinez Lastra, Jose L. and Wollschlaeger, Martin},
 booktitle={11th IFAC Workshop on intelligent manufacturing systems, The international federation of automatic control, May 22-24, 2013. São Paulo, Brazil},
 year={2013},
 pages={348--353},
 url={https://doi.org/10.3182/20130522-3-BR-4036.00047}
}
"""

    out = normalize_bibtex(raw)

    assert "@inproceedings{Dennert_advanced_2013," in out
    assert "S\\~{a}o Paulo" in out


@pytest.mark.imported
@pytest.mark.parametrize(
    "doi, raw, expected_id, expected_author_parts, expected_title_parts",
    [
        (
            "10.1103/RevModPhys.86.843",
            """@article{Englert_2014,
 title={Nobel Lecture: The BEH mechanism and its scalar boson},
 author={Englert, François},
 journal={Reviews of Modern Physics},
 publisher={American Physical Society (APS)},
 year={2014},
 month={July},
 volume={86},
 number={3},
 pages={843--850},
 url={https://doi.org/10.1103/RevModPhys.86.843}
}
""",
            "Englert_nobel_2014",
            ["Englert, Fran\\c{c}ois"],
            ["{Nobel}", "{BEH}"],
        ),
        (
            "10.1103/PhysRevE.78.031908",
            """@article{Englert_2008,
 title={Twenty-four near-instabilities of Caspar-Klug viruses},
 author={François Englert and Kasper Peeters and Anne Taormina},
 journal={Physical Review E},
 publisher={American Physical Society (APS)},
 year={2008},
 month={September},
 volume={78},
 number={3},
 pages={031908},
 url={https://doi.org/10.1103/PhysRevE.78.031908}
}
""",
            "Englert_twenty-four_2008",
            ["Fran\\c{c}ois Englert"],
            ["{Twenty-four}", "{Caspar-Klug}"],
        ),
        (
            "10.1038/s41567-022-01725-6",
            """@article{Taie_2022,
 title={Observation of antiferromagnetic correlations in an ultracold SU(N) Hubbard model},
 author={Taie, Shintaro and Ibarra-García-Padilla, Eduardo and Nishizawa, Naoki},
 journal={Nature Physics},
 publisher={Springer Science and Business Media LLC},
 year={2022},
 month={September},
 volume={18},
 number={11},
 pages={1356--1361},
 url={https://doi.org/10.1038/s41567-022-01725-6}
}
""",
            "Taie_observation_2022",
            ["Ibarra-Garc\\'{i}a-Padilla, Eduardo"],
            ["{SU}({N})", "{Hubbard}"],
        ),
        (
            "10.1126/science.aal1575",
            """@article{Sprau_2017,
 title={Discovery of orbital-selective Cooper pairing in FeSe},
 author={Sprau, P. O. and Böhmer, A. E. and Davis, J. C. Séamus},
 journal={Science},
 publisher={American Association for the Advancement of Science (AAAS)},
 year={2017},
 month={July},
 volume={357},
 number={6346},
 pages={75--80},
 url={https://doi.org/10.1126/science.aal1575}
}
""",
            "Sprau_discovery_2017",
            ["B\\\"{o}hmer, A. E.", "Davis, J. C. S\\'{e}amus"],
            ["{Discovery}", "{Cooper}", "{FeSe}"],
        ),
    ],
)
def test_physics_doi_fixtures_encode_title_and_author_diacritics(
    doi, raw, expected_id, expected_author_parts, expected_title_parts
):
    out = normalize_bibtex(raw)

    assert f"@article{{{expected_id}," in out
    assert doi in out
    for author_part in expected_author_parts:
        assert author_part in out
    for title_part in expected_title_parts:
        assert title_part in out
