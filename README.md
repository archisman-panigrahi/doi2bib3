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

## Using from Python

You can use this library directly from another Python package or script. Below are recommended ways to install and example code showing the public functions to call.

Installation options before importing:

- Install in editable mode while developing inside the repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

- Or install the built wheel:

```bash
python -m build
pip install dist/doi2bib2-0.1.0-py3-none-any.whl
```

Import paths and useful functions
- doi2bib2.backend.get_bibtex_from_doi(doi: str) -> str
	- Fetches BibTeX text for a DOI. Raises `doi2bib2.backend.DOIError` on non-200 responses or invalid DOIs.

- doi2bib2.backend.arxiv_to_doi(arxivid: str) -> Optional[str]
	- Resolves an arXiv id to a DOI string or returns None if not found.

- doi2bib2.utils.normalize_bibtex(bib_str: str) -> str
	- Normalizes a BibTeX string (ID cleanup, page formatting, URL decoding, small character fixes).

- doi2bib2.utils.save_bibtex_to_file(bib_str: str, path: str, append: bool=False) -> None
	- Writes or appends the BibTeX string to a file.

Example usage (save as `fetch_example.py`):

```python
from doi2bib2.backend import get_bibtex_from_doi, arxiv_to_doi, DOIError
from doi2bib2.utils import normalize_bibtex, save_bibtex_to_file

def fetch_by_doi(doi: str, out_path: str | None = None) -> str:
		try:
				raw = get_bibtex_from_doi(doi)
		except DOIError as exc:
				raise RuntimeError(f"Failed to fetch DOI {doi}: {exc}") from exc
		cleaned = normalize_bibtex(raw)
		if out_path:
				save_bibtex_to_file(cleaned, out_path, append=True)
				return f"Wrote {out_path}"
		return cleaned

def fetch_by_arxiv(arxivid: str, out_path: str | None = None) -> str:
		doi = arxiv_to_doi(arxivid)
		if not doi:
				raise RuntimeError(f"No DOI found for arXiv id {arxivid}")
		return fetch_by_doi(doi, out_path)

if __name__ == '__main__':
		print(fetch_by_doi('10.1038/nphys1170'))
		# Or:
		# print(fetch_by_arxiv('2411.08091', out_path='paper.bib'))
```

Programmatic CLI call
- You can also call the CLI function directly (it accepts argv list):

```python
from doi2bib2.utils import cli_doi2bib2
cli_doi2bib2(['doi', '10.1038/nphys1170', '--out', 'paper.bib'])
```

License
-------
This project is distributed under the GNU General Public License v3 (GPL-3.0-only).
