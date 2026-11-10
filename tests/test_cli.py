"""CLI formatting checks with fixed metadata and no network requests."""
from pathlib import Path
import runpy
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doi2bib3 import backend


@pytest.mark.parametrize("flag", [None, "--mbox", "-m"])
@pytest.mark.parametrize("save_to_file", [False, True])
def test_mbox_is_opt_in_for_bibtex_and_bibitem(
    monkeypatch, capsys, tmp_path, flag, save_to_file
):
    monkeypatch.setattr(
        backend, "_resolve_identifier", lambda *args, **kwargs: ("10.1234/example", None)
    )
    monkeypatch.setattr(
        backend,
        "_fetch_bibtex_for_doi",
        lambda *args, **kwargs: """@article{example,
 author={de la Cruz, Jane and Smith, John},
 title={Example},
 year={2025}
}""",
    )
    cli = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/doi2bib3"))
    args = ["10.1234/example", "--bibitem"]
    if flag:
        args.append(flag)
    output_path = tmp_path / "paper.bib"
    if save_to_file:
        args.extend(["-o", str(output_path)])

    assert cli["main"](args) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    bibtex = output_path.read_text() if save_to_file else captured.out.split(r"\bibitem")[0]
    bibitem = captured.out.split(r"\bibitem", 1)[1]
    if flag:
        assert r"author = {\mbox{de la Cruz}, Jane and \mbox{Smith}, John}" in bibtex
        assert r"J. \mbox{de la Cruz}, and J. \mbox{Smith}" in bibitem
    else:
        assert r"\mbox" not in bibtex
        assert r"\mbox" not in bibitem
        assert "author = {de la Cruz, Jane and Smith, John}" in bibtex
        assert "J. de la Cruz, and J. Smith" in bibitem



def test_output_file_is_written_fresh_not_appended(monkeypatch, capsys, tmp_path):
    cli = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/doi2bib3"))

    def fake_fetch(identifier, mbox=False):
        return f"@article{{{identifier},\n title={{T}}\n}}"

    monkeypatch.setitem(cli["main"].__globals__, "fetch_bibtex", fake_fetch)
    input_path = tmp_path / "dois.txt"
    input_path.write_text("a\n")
    output_path = tmp_path / "refs.bib"
    output_path.write_text("STALE\n")

    assert cli["main"](["--input", str(input_path), "--output", str(output_path)]) == 0
    bib = output_path.read_text()
    assert "STALE" not in bib
    assert bib.count("@article") == 1


def test_batch_input_file(monkeypatch, capsys, tmp_path):
    cli = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/doi2bib3"))

    def fake_fetch(identifier, mbox=False):
        if identifier == "bad":
            raise ValueError("not found")
        return f"@article{{{identifier},\n title={{T}}\n}}"

    monkeypatch.setitem(cli["main"].__globals__, "fetch_bibtex", fake_fetch)
    input_path = tmp_path / "dois.txt"
    input_path.write_text("# refs\na\n\n bad \nb\n")
    output_path = tmp_path / "refs.bib"

    assert cli["main"](["--input", str(input_path), "--output", str(output_path)]) == 1
    bib = output_path.read_text()
    assert "@article{a," in bib and "@article{b," in bib and bib.count("@article") == 2
    assert "Error (bad): not found" in capsys.readouterr().err
