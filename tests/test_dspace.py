import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


class FakeResponse:
    def __init__(self, status_code=200, payload=None, url=""):
        self.status_code = status_code
        self.content = json.dumps(payload or {}).encode()
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"
        self.url = url


@pytest.mark.imported
def test_dspace_phd_thesis_url_uses_item_metadata(monkeypatch):
    uuid = "0e717874-1cc5-4fa0-ace3-9c08ff9396cf"
    url = f"https://dspace.mit.edu/entities/publication/{uuid}"
    api_url = f"https://dspace.mit.edu/server/api/core/items/{uuid}"
    payload = {
        "metadata": {
            "dc.contributor.author": [{"value": "Dong, Zhiyu"}],
            "dc.date.issued": [{"value": "2023-06"}],
            "dc.description.degree": [{"value": "Ph.D."}],
            "dc.identifier.uri": [
                {"value": "https://hdl.handle.net/1721.1/152555"}
            ],
            "dc.publisher": [
                {"value": "Massachusetts Institute of Technology"}
            ],
            "dc.title": [
                {"value": "Stoner magnetism and Berry phase in quantum materials"}
            ],
        }
    }
    called_urls = []

    def fake_get(request_url, headers=None, timeout=None):
        called_urls.append(request_url)
        assert request_url == api_url
        return FakeResponse(payload=payload)

    monkeypatch.setattr(backend.requests, "get", fake_get)

    bibtex = backend.fetch_bibtex(url)

    assert bibtex.startswith("@phdthesis{Dong_stoner_2023,")
    assert "author = {Dong, Zhiyu}" in bibtex
    assert "school = {Massachusetts Institute of Technology}" in bibtex
    assert "url = {https://hdl.handle.net/1721.1/152555}" in bibtex
    assert called_urls == [api_url]


@pytest.mark.imported
def test_dspace_metadata_failure_does_not_search_crossref(monkeypatch):
    uuid = "0e717874-1cc5-4fa0-ace3-9c08ff9396cf"
    url = f"https://dspace.mit.edu/entities/publication/{uuid}"
    monkeypatch.setattr(
        backend.requests, "get", lambda *args, **kwargs: FakeResponse(status_code=503)
    )

    with pytest.raises(backend.DOIError, match="DSpace metadata"):
        backend.fetch_bibtex(url)


@pytest.mark.imported
def test_dspace_handle_resolves_to_item_metadata(monkeypatch):
    uuid = "0e717874-1cc5-4fa0-ace3-9c08ff9396cf"
    handle_url = "https://hdl.handle.net/1721.1/152555"
    legacy_url = "https://dspace.mit.edu/handle/1721.1/152555"
    pid_url = "https://dspace.mit.edu/server/api/pid/find?id=1721.1%2F152555"
    payload = {
        "metadata": {
            "dc.contributor.author": [{"value": "Dong, Zhiyu"}],
            "dc.date.issued": [{"value": "2023-06"}],
            "dc.description.degree": [{"value": "Ph.D."}],
            "dc.identifier.uri": [{"value": handle_url}],
            "dc.publisher": [{"value": "Massachusetts Institute of Technology"}],
            "dc.title": [{"value": "Stoner magnetism and Berry phase in quantum materials"}],
        }
    }
    called_urls = []

    def fake_get(request_url, headers=None, timeout=None):
        called_urls.append(request_url)
        if request_url == handle_url:
            return FakeResponse(status_code=202, url=legacy_url)
        assert request_url == pid_url
        return FakeResponse(payload=payload, url=f"/server/api/core/items/{uuid}")

    monkeypatch.setattr(backend.requests, "get", fake_get)

    bibtex = backend.fetch_bibtex(f"{handle_url},")

    assert bibtex.startswith("@phdthesis{Dong_stoner_2023,")
    assert f"url = {{{handle_url}}}" in bibtex
    assert called_urls == [handle_url, pid_url]


@pytest.mark.imported
def test_dspace_non_thesis_uses_item_doi(monkeypatch):
    handle_url = "https://hdl.handle.net/1721.1/164424"
    legacy_url = "https://dspace.mit.edu/handle/1721.1/164424"
    pid_url = "https://dspace.mit.edu/server/api/pid/find?id=1721.1%2F164424"
    doi = "10.1073/pnas.2520608122"
    payload = {
        "metadata": {
            "dc.relation.isversionof": [{"value": f"https://doi.org/{doi}"}],
            "dc.title": [{"value": "Anyon delocalization transitions"}],
            "dc.type": [{"value": "Article"}],
        }
    }

    def fake_get(request_url, headers=None, timeout=None):
        if request_url == handle_url:
            return FakeResponse(status_code=202, url=legacy_url)
        assert request_url == pid_url
        return FakeResponse(payload=payload, url=pid_url)

    fetched_dois = []

    def fake_fetch_bibtex(item_doi, timeout=15):
        fetched_dois.append(item_doi)
        return "@article{item, author={Shi, Zhengyan}, title={Anyon delocalization transitions}, year={2025}}"

    monkeypatch.setattr(backend.requests, "get", fake_get)
    monkeypatch.setattr(backend, "_fetch_bibtex_for_doi", fake_fetch_bibtex)

    bibtex = backend.fetch_bibtex(handle_url)

    assert bibtex.startswith("@article{Shi_anyon_2025,")
    assert fetched_dois == [doi]
