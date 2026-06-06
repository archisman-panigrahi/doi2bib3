import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.text = json.dumps(payload or {})
        self.content = self.text.encode("utf-8")
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"

    def json(self):
        return json.loads(self.text)


@pytest.mark.imported
@pytest.mark.parametrize(
    "identifier, expected",
    [
        ("9780465024933", "9780465024933"),
        ("ISBN 978-0-465-02493-3", "9780465024933"),
        ("ISBN-13: 978 0 465 02493 3", "9780465024933"),
        ("0-306-40615-2", "0306406152"),
        ("urn:isbn:0-306-40615-2", "0306406152"),
    ],
)
def test_parse_isbn_accepts_valid_isbn_forms(identifier, expected):
    assert backend._parse_isbn_string(identifier) == expected


@pytest.mark.imported
@pytest.mark.parametrize(
    "identifier",
    [
        "9780465024934",
        "0-306-40615-3",
        "978-0-465-02493-X",
        "Projected Topological Branes",
        "10.1038/nphys1170",
    ],
)
def test_parse_isbn_rejects_non_isbn_forms(identifier):
    assert backend._parse_isbn_string(identifier) is None


@pytest.mark.imported
def test_fetch_bibtex_resolves_isbn_with_openlibrary(monkeypatch):
    called = []
    isbn = "9780465024933"

    def fake_get(url, headers=None, timeout=None):
        called.append(url)
        return FakeResponse(
            payload={
                f"ISBN:{isbn}": {
                    "title": (
                        "The Feynman lectures on physics : "
                        "Mainly mechanics, radiation, and heat\t"
                    ),
                    "authors": [
                        {"name": "Richard Phillips Feynman"},
                        {"name": "Robert B. Leighton"},
                        {"name": "Matthew Sands"},
                    ],
                    "publishers": [{"name": "Basic Books\t"}],
                    "publish_date": "2011\t",
                    "url": (
                        "http://openlibrary.org/books/OL26366190M/"
                        "The_Feynman_lectures_on_physics"
                    ),
                }
            }
        )

    monkeypatch.setattr(backend.requests, "get", fake_get)

    bibtex = backend.fetch_bibtex("ISBN 978-0-465-02493-3")

    assert called == [
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json",
    ]
    assert "@book{Feynman_the_2011," in bibtex
    assert (
        "author = {Richard Phillips Feynman and Robert B. Leighton and Matthew Sands}"
        in bibtex
    )
    assert "isbn = {9780465024933}" in bibtex
    assert "publisher = {Basic Books}" in bibtex
    assert "year = {2011}" in bibtex
    assert (
        "title = {{The} {Feynman} lectures on physics: "
        "{Mainly} mechanics, radiation, and heat}" in bibtex
    )


@pytest.mark.imported
def test_fetch_bibtex_falls_back_to_google_books_when_openlibrary_fails(monkeypatch):
    called = []
    isbn = "9780465024933"

    def fake_get(url, headers=None, timeout=None):
        called.append(url)
        if "openlibrary.org" in url:
            return FakeResponse(status_code=503, payload={})
        return FakeResponse(
            payload={
                "totalItems": 1,
                "items": [
                    {
                        "volumeInfo": {
                            "title": "The Feynman Lectures on Physics",
                            "subtitle": "Mainly Mechanics, Radiation, and Heat",
                            "authors": [
                                "Richard P. Feynman",
                                "Robert B. Leighton",
                                "Matthew Sands",
                            ],
                            "publisher": "Basic Books",
                            "publishedDate": "2011-10-04",
                            "canonicalVolumeLink": (
                                "https://books.google.com/books?id=feynman"
                            ),
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(backend.requests, "get", fake_get)

    bibtex = backend.fetch_bibtex("ISBN 978-0-465-02493-3")

    assert called == [
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json",
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}",
    ]
    assert "@book{Feynman_the_2011," in bibtex
    assert (
        "author = {Richard P. Feynman and Robert B. Leighton and Matthew Sands}"
        in bibtex
    )
    assert "isbn = {9780465024933}" in bibtex
    assert "publisher = {Basic Books}" in bibtex
    assert "year = {2011}" in bibtex
    assert (
        "title = {{The} {Feynman} {Lectures} on {Physics}: "
        "{Mainly} {Mechanics}, {Radiation}, and {Heat}}" in bibtex
    )


@pytest.mark.imported
def test_fetch_bibtex_raises_when_isbn_providers_have_no_result(monkeypatch):
    called = []
    isbn = "9780465024933"

    def fake_get(url, headers=None, timeout=None):
        called.append(url)
        if "openlibrary.org" in url:
            return FakeResponse(payload={})
        return FakeResponse(payload={"totalItems": 0, "items": []})

    monkeypatch.setattr(backend.requests, "get", fake_get)

    with pytest.raises(backend.DOIError, match="ISBN lookup failed"):
        backend.fetch_bibtex("9780465024933")

    assert called == [
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json",
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}",
    ]
