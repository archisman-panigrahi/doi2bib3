from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3._bibtex import dump_entries, parse_entries, split_name


def test_parse_entries_resolves_strings_and_normalizes_field_names():
    entries = parse_entries(
        '@string{jan = "January"}\n'
        "@article{Example, month=jan, archivePrefix={arXiv}}"
    )

    assert entries == [
        {
            "ENTRYTYPE": "article",
            "ID": "Example",
            "month": "January",
            "archiveprefix": "arXiv",
        }
    ]


def test_dump_entries_keeps_the_v1_output_layout():
    output = dump_entries(
        [
            {
                "ENTRYTYPE": "article",
                "ID": "Example",
                "year": "2026",
                "author": "Doe, Jane",
            }
        ]
    )

    assert output == (
        "@article{Example,\n"
        " author = {Doe, Jane},\n"
        " year = {2026}\n"
        "}\n"
    )


def test_split_name_returns_v1_style_parts():
    assert split_name("van Beethoven, Ludwig") == {
        "first": ["Ludwig"],
        "von": ["van"],
        "last": ["Beethoven"],
        "jr": [],
    }
