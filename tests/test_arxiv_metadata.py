from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"
        self.headers = headers or {}
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise AssertionError("json() was not expected for this response")
        return self._json_data


def _install_fake_get(monkeypatch, responses, called_urls):
    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        response = responses.get(url)
        if response is None:
            raise AssertionError(f"Unexpected URL: {url}")
        if isinstance(response, list):
            if not response:
                raise AssertionError(f"No responses left for URL: {url}")
            response = response.pop(0)
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
    assert called_urls[:4] == [
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
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


@pytest.mark.imported
def test_fetch_bibtex_retries_arxiv_api_on_rate_limit(monkeypatch):
    called_urls = []
    sleep_calls = []
    arxiv_id = "2512.03137"
    responses = {
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}": [
            FakeResponse(status_code=429, text="too many requests", headers={"Retry-After": "0"}),
            FakeResponse(
                text=f"""
                <feed xmlns:arxiv="http://arxiv.org/schemas/atom">
                  <entry>
                    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
                    <arxiv:primary_category term="cs.LG" />
                  </entry>
                </feed>
                """
            ),
        ],
        f"https://doi.org/10.48550/arXiv.{arxiv_id}": FakeResponse(
            text=f"""
            @misc{{sample,
             author = {{Doe, Jane}},
             title = {{Rate limited preprint}},
             year = {{2025}},
             url = {{https://doi.org/10.48550/arXiv.{arxiv_id}}}
            }}
            """
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)
    monkeypatch.setattr(backend.time, "sleep", lambda delay: sleep_calls.append(delay))

    bibtex = backend.fetch_bibtex(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

    assert called_urls[:2] == [
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
    ]
    assert sleep_calls == [0.0]
    assert "archivePrefix = {arXiv}" in bibtex
    assert f"eprint = {{{arxiv_id}}}" in bibtex
    assert "primaryClass = {cs.LG}" in bibtex


@pytest.mark.imported
def test_fetch_bibtex_falls_back_to_arxiv_doi_when_metadata_fetch_fails(monkeypatch):
    arxiv_id = "2512.03137"

    def fake_fetch_arxiv_metadata(value, timeout=15):
        raise backend.DOIError("arXiv query failed: HTTP 429")

    monkeypatch.setattr(backend, "_fetch_arxiv_metadata", fake_fetch_arxiv_metadata)

    called_urls = []
    responses = {
        f"https://doi.org/10.48550/arXiv.{arxiv_id}": FakeResponse(
            text=f"""
            @misc{{sample,
             author = {{Doe, Jane}},
             title = {{Fallback preprint}},
             year = {{2025}},
             url = {{https://doi.org/10.48550/arXiv.{arxiv_id}}}
            }}
            """
        ),
        f"https://api.crossref.org/works/10.48550%2FarXiv.{arxiv_id}/transform/application/x-bibtex": FakeResponse(
            status_code=404, text="not used"
        ),
    }
    _install_fake_get(monkeypatch, responses, called_urls)

    bibtex = backend.fetch_bibtex(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

    assert called_urls == [f"https://doi.org/10.48550/arXiv.{arxiv_id}"]
    assert "archivePrefix = {arXiv}" in bibtex
    assert f"eprint = {{{arxiv_id}}}" in bibtex
    assert "primaryClass" not in bibtex


@pytest.mark.imported
def test_fetch_bibtex_retries_doi_lookup_on_rate_limit(monkeypatch):
    called_urls = []
    sleep_calls = []
    arxiv_id = "2501.99999"
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
        f"https://doi.org/10.48550/arXiv.{arxiv_id}": [
            FakeResponse(status_code=429, text="too many requests", headers={"Retry-After": "0"}),
            FakeResponse(
                text=f"""
                @misc{{sample,
                 author = {{Doe, Jane}},
                 title = {{Retry DOI}},
                 year = {{2025}},
                 url = {{https://doi.org/10.48550/arXiv.{arxiv_id}}}
                }}
                """
            ),
        ],
    }
    _install_fake_get(monkeypatch, responses, called_urls)
    monkeypatch.setattr(backend.time, "sleep", lambda delay: sleep_calls.append(delay))

    bibtex = backend.fetch_bibtex(f"arXiv:{arxiv_id}")

    assert called_urls == [
        f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
        f"https://doi.org/10.48550/arXiv.{arxiv_id}",
        f"https://doi.org/10.48550/arXiv.{arxiv_id}",
    ]
    assert sleep_calls == [0.0]
    assert "archivePrefix = {arXiv}" in bibtex
    assert f"eprint = {{{arxiv_id}}}" in bibtex
