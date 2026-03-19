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
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(backend.requests, "get", fake_get)


@pytest.mark.imported
def test_fetch_bibtex_adds_arxiv_fields_for_unpublished_arxiv_url(monkeypatch):
    called_urls = []
    arxiv_id = "2501.12345"
    responses = {
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}": FakeResponse(
            status_code=503, text="temporary outage"
        ),
        f"https://export.arxiv.org/api/query?id_list={arxiv_id}": FakeResponse(
            text=f"""
            <feed xmlns:arxiv="http://arxiv.org/schemas/atom">
              <entry>
                <id>http://arxiv.org/abs/{arxiv_id}v1</id>
                <arxiv:primary_category term="cond-mat.str-el" />
              </entry>
            </feed>
            """
        ),
        f"https://doi.org/10.48550/arXiv.{arxiv_id}": FakeResponse(
            text="""
            @misc{sample,
             author = {Doe, Jane},
             title = {Example preprint},
             year = {2025},
             url = {https://doi.org/10.48550/arXiv.2501.12345}
            }
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(f"https://arxiv.org/abs/{arxiv_id}")

    assert "archivePrefix = {arXiv}" in bibtex
    assert f"eprint = {{{arxiv_id}}}" in bibtex
    assert "primaryClass = {cond-mat.str-el}" in bibtex
    assert called_urls[:2] == [
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
        f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
    ]


@pytest.mark.imported
def test_fetch_bibtex_adds_arxiv_fields_for_unpublished_arxiv_doi_url(monkeypatch):
    called_urls = []
    arxiv_id = "2501.54321"
    responses = {
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}": FakeResponse(
            text=f"""
            <feed xmlns:arxiv="http://arxiv.org/schemas/atom">
              <entry>
                <id>http://arxiv.org/abs/{arxiv_id}v1</id>
                <arxiv:primary_category term="hep-th" />
              </entry>
            </feed>
            """
        ),
        f"https://doi.org/10.48550/arXiv.{arxiv_id}": FakeResponse(
            text="""
            @misc{sample,
             author = {Doe, Jane},
             title = {Another preprint},
             year = {2025},
             url = {https://doi.org/10.48550/arXiv.2501.54321}
            }
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(f"https://doi.org/10.48550/arXiv.{arxiv_id}")

    assert "archivePrefix = {arXiv}" in bibtex
    assert f"eprint = {{{arxiv_id}}}" in bibtex
    assert "primaryClass = {hep-th}" in bibtex


@pytest.mark.imported
def test_fetch_bibtex_skips_arxiv_fields_when_journal_doi_exists(monkeypatch):
    called_urls = []
    arxiv_id = "2502.00001"
    journal_doi = "10.9999/example.1"
    responses = {
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}": FakeResponse(
            text=f"""
            <feed xmlns:arxiv="http://arxiv.org/schemas/atom">
              <entry>
                <id>http://arxiv.org/abs/{arxiv_id}v1</id>
                <arxiv:doi>{journal_doi}</arxiv:doi>
                <arxiv:primary_category term="quant-ph" />
              </entry>
            </feed>
            """
        ),
        f"https://doi.org/{journal_doi}": FakeResponse(
            text=f"""
            @article{{sample,
             author = {{Doe, Jane}},
             title = {{Published result}},
             year = {{2025}},
             journal = {{Journal of Tests}},
             url = {{https://doi.org/{journal_doi}}}
            }}
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(f"arXiv:{arxiv_id}")

    assert "archivePrefix" not in bibtex
    assert "eprint" not in bibtex
    assert "primaryClass" not in bibtex
    assert f"https://doi.org/{journal_doi}" in bibtex
