# doi2bib2

Small utility to fetch BibTeX metadata for a DOI or resolve an arXiv id to a DOI
and fetch the BibTeX entry.

## Installation

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You can also build and install the wheel locally:

```bash
python -m build
pip install dist/doi2bib2-0.1.0-py3-none-any.whl
```

## Usage

Two simple commands are provided. The CLI executable is the `main.py` shim in the
repository root; if you install the package the console script `doi2bib2` will be
available and behaves the same.

- Fetch by DOI:

```bash
python main.py doi 10.1038/nphys1170
```

Save to a file with `-o` / `--out`:

```bash
python main.py doi 10.1038/nphys1170 -o paper.bib
```

- Resolve an arXiv id and fetch the DOI's BibTeX:

```bash
python main.py arxiv 2411.08091
```

Save to a file:

```bash
python main.py arxiv 2411.08091 -o paper.bib
```

License
-------
This project is distributed under the GNU General Public License v3 (GPL-3.0-only).
