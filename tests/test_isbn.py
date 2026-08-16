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


def isbn_provider_urls(isbn):
    return [
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json",
        (
            "http://lx2.loc.gov:210/LCDB?version=1.1&operation=searchRetrieve&"
            f"query=bath.isbn%3D{isbn}&maximumRecords=1&recordSchema=mods"
        ),
        (
            "https://services.dnb.de/sru/dnb?version=1.1&operation=searchRetrieve&"
            f"query=num%3D{isbn}&maximumRecords=1&recordSchema=MARC21-xml"
        ),
        f"https://api.crossref.org/works?filter=isbn%3A{isbn}&rows=1",
        (
            "https://archive.org/advancedsearch.php?"
            f"q=isbn%3A{isbn}&fl%5B%5D=title%2Ccreator%2Cpublisher%2Cdate%2Cidentifier"
            "&rows=1&output=json"
        ),
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}",
    ]


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

    assert called == isbn_provider_urls(isbn)
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

    assert called == isbn_provider_urls(isbn)


@pytest.mark.imported
def test_fetch_bibtex_stops_after_library_of_congress_match(monkeypatch):
    called = []
    isbn = "9780465024933"
    mods = b"""<?xml version="1.0"?>
    <zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/"
      xmlns:mods="http://www.loc.gov/mods/v3">
      <zs:records><zs:record><zs:recordData><mods:mods>
        <mods:titleInfo><mods:nonSort>The </mods:nonSort>
          <mods:title>Feynman Lectures on Physics</mods:title>
          <mods:subTitle>Mainly Mechanics</mods:subTitle></mods:titleInfo>
        <mods:name type="personal"><mods:namePart>Feynman, Richard P.</mods:namePart>
          <mods:namePart type="date">1918-1988</mods:namePart></mods:name>
        <mods:originInfo><mods:agent><mods:namePart>Basic Books</mods:namePart></mods:agent>
          <mods:dateIssued>2011</mods:dateIssued></mods:originInfo>
        <mods:identifier type="lccn">2010938208</mods:identifier>
      </mods:mods></zs:recordData></zs:record></zs:records>
    </zs:searchRetrieveResponse>"""

    def fake_get(url, headers=None, timeout=None):
        called.append(url)
        if "openlibrary.org" in url:
            return FakeResponse(payload={})
        response = FakeResponse()
        response.content = mods
        return response

    monkeypatch.setattr(backend.requests, "get", fake_get)
    bibtex = backend.fetch_bibtex(isbn)

    assert called == isbn_provider_urls(isbn)[:2]
    assert "author = {Feynman, Richard P.}" in bibtex
    assert "publisher = {Basic Books}" in bibtex
    assert "year = {2011}" in bibtex


@pytest.mark.imported
def test_dnb_marc_parser_and_author_deduplication(monkeypatch):
    isbn = "9783527408559"
    marc = b"""<?xml version="1.0"?>
    <searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
      <records><record><recordData>
        <record xmlns="http://www.loc.gov/MARC21/slim">
          <controlfield tag="001">988812509</controlfield>
          <datafield tag="100"><subfield code="a">Mihaly, Laszlo</subfield>
            <subfield code="4">aut</subfield></datafield>
          <datafield tag="700"><subfield code="a">Mihaly, Laszlo</subfield>
            <subfield code="4">aut</subfield></datafield>
          <datafield tag="700"><subfield code="a">Martin, Michael C.</subfield>
            <subfield code="4">aut</subfield></datafield>
          <datafield tag="245"><subfield code="a">Solid state physics :</subfield>
            <subfield code="b">problems and solutions /</subfield></datafield>
          <datafield tag="264" ind2="1"><subfield code="b">Wiley-VCH,</subfield>
            <subfield code="c">2009.</subfield></datafield>
        </record>
      </recordData></record></records>
    </searchRetrieveResponse>"""
    response = FakeResponse()
    response.content = marc
    monkeypatch.setattr(backend.requests, "get", lambda *args, **kwargs: response)

    book = backend._dnb_book_info(isbn)
    bibtex = backend._bibtex_from_book_info(isbn, book)

    assert book["title"] == "Solid state physics"
    assert book["subtitle"] == "problems and solutions"
    assert bibtex.count("Mihaly, Laszlo") == 1
    assert "Martin, Michael C." in bibtex


@pytest.mark.imported
def test_join_names_deduplicates_unicode_equivalent_authors():
    assert backend._join_names(["La\u0301szlo\u0301 Miha\u0301ly", "László Mihály"]) == (
        "La\u0301szlo\u0301 Miha\u0301ly"
    )


@pytest.mark.imported
def test_non_isbn_does_not_query_book_catalogs(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("a non-ISBN input queried a book catalog")

    monkeypatch.setattr(backend, "_fetch_bibtex_for_isbn", unexpected)
    monkeypatch.setattr(
        backend, "_resolve_identifier", lambda identifier, timeout=15: (identifier, None)
    )
    monkeypatch.setattr(
        backend,
        "_fetch_bibtex_for_doi",
        lambda doi, timeout=15: "@article{x, title={A paper}, year={2025}}",
    )

    bibtex = backend.fetch_bibtex("10.1234/example")

    assert "@article" in bibtex
