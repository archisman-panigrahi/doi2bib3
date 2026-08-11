import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.content = json.dumps(payload or {}).encode()
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"


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
