from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"


def _install_fake_get(monkeypatch, responses, called_urls):
    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        response = responses.get(url)
        if response is None:
            raise AssertionError(f"Unexpected URL: {url}")
        return response

    monkeypatch.setattr(backend.requests, "get", fake_get)


@pytest.mark.imported
def test_sciencedirect_url_resolves_doi_from_elsevier_pii(monkeypatch):
    called_urls = []
    pii = "S0003491605000096"
    doi = "10.1016/j.aop.2005.01.006"
    article_url = (
        f"https://www.sciencedirect.com/science/article/pii/{pii}?via%3Dihub"
    )
    responses = {
        f"https://api.elsevier.com/content/article/pii/{pii}": FakeResponse(
            text=f"<coredata><prism:doi>{doi}</prism:doi></coredata>"
        )
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    assert backend._resolve_identifier_to_doi(article_url) == doi
    assert called_urls == [f"https://api.elsevier.com/content/article/pii/{pii}"]


@pytest.mark.imported
def test_sciencedirect_url_fetches_bibtex_for_resolved_doi(monkeypatch):
    called_urls = []
    pii = "S0003491605000096"
    doi = "10.1016/j.aop.2005.01.006"
    article_url = (
        f"https://www.sciencedirect.com/science/article/pii/{pii}?via%3Dihub"
    )
    responses = {
        f"https://api.elsevier.com/content/article/pii/{pii}": FakeResponse(
            text='{"prism:doi":"10.1016\\/j.aop.2005.01.006"}'
        ),
        f"https://doi.org/{doi}": FakeResponse(
            text=f"""
            @article{{Zhang_infinite_2005,
             author = {{Zhang, F. C.}},
             title = {{Infinite U Hubbard problem}},
             year = {{2005}},
             url = {{https://doi.org/{doi}}}
            }}
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(article_url)

    assert f"https://doi.org/{doi}" in bibtex
    assert f"https://doi.org/{doi}" in called_urls


@pytest.mark.imported
def test_iopscience_pdf_url_resolves_doi_without_pdf_suffix():
    doi = "10.1088/1402-4896/ad995f"
    article_url = f"https://iopscience.iop.org/article/{doi}/pdf"

    assert backend._resolve_identifier_to_doi(article_url) == doi


@pytest.mark.imported
def test_iopscience_pdf_url_fetches_bibtex_for_resolved_doi(monkeypatch):
    called_urls = []
    doi = "10.1088/1402-4896/ad995f"
    article_url = f"https://iopscience.iop.org/article/{doi}/pdf"
    responses = {
        f"https://doi.org/{doi}": FakeResponse(
            text=f"""
            @article{{Singh_analysis_2024,
             author = {{Singh, Anmol and Anand, R K}},
             title = {{Analysis on the internal structure of shock wave-front}},
             year = {{2024}},
             url = {{https://doi.org/{doi}}}
            }}
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(article_url)

    assert f"https://doi.org/{doi}" in bibtex
    assert f"https://doi.org/{doi}" in called_urls
    assert f"https://doi.org/{doi}/pdf" not in called_urls


@pytest.mark.imported
def test_scipost_article_url_resolves_doi_from_path():
    doi = "10.21468/SciPostPhys.20.3.082"
    article_url = "https://www.scipost.org/SciPostPhys.20.3.082/"

    assert backend._resolve_identifier_to_doi(article_url) == doi


@pytest.mark.imported
def test_scipost_pdf_url_resolves_doi_without_pdf_suffix():
    doi = "10.21468/SciPostPhys.20.3.082"
    article_url = "https://www.scipost.org/SciPostPhys.20.3.082/pdf"

    assert backend._resolve_identifier_to_doi(article_url) == doi


@pytest.mark.imported
def test_scipost_pdf_url_fetches_bibtex_for_resolved_doi(monkeypatch):
    called_urls = []
    doi = "10.21468/SciPostPhys.20.3.082"
    article_url = "https://www.scipost.org/SciPostPhys.20.3.082/pdf"
    responses = {
        f"https://doi.org/{doi}": FakeResponse(
            text=f"""
            @article{{Example_2026,
             author = {{Example, A.}},
             title = {{SciPost example}},
             year = {{2026}},
             url = {{https://doi.org/{doi}}}
            }}
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(article_url)

    assert f"https://doi.org/{doi}" in bibtex
    assert f"https://doi.org/{doi}" in called_urls
    assert f"https://doi.org/{doi}/pdf" not in called_urls
