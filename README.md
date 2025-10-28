# doi2bib3

Small utility to fetch BibTeX metadata for a DOI or resolve an arXiv id to a DOI
and fetch the BibTeX entry. This script combines the features of [doi2bib](https://github.com/bibcure/doi2bib/) and [doi2bib2](https://github.com/davidagraf/doi2bib2).

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
pip install dist/doi2bib3-0.1.0-py3-none-any.whl
```

## Usage

The CLI accepts a single positional identifier: a DOI, a DOI URL, an arXiv
identifier or arXiv URL, or a publisher landing page URL. The resolver will
automatically detect arXiv inputs and use the arXiv API, or fall back to DOI
normalization and Crossref lookups when needed.

Examples:

Fetch by DOI (bare DOI or DOI URL accepted):

```bash
python main.py 10.1038/nphys1170
python main.py https://doi.org/10.1038/nphys1170
```

Save to a file with `-o` / `--out`:

```bash
python main.py https://doi.org/10.1038/nphys1170 -o paper.bib
```

ArXiv inputs (URL or id) are detected automatically and resolved via the
arXiv API to a DOI (when available):

```bash
python main.py https://arxiv.org/abs/2411.08091
python main.py arXiv:2411.08091
python main.py 2411.08091
python main.py hep-th/9901001
python main.py https://arxiv.org/abs/hep-th/9901001
```

Publisher landing pages or other free-form queries are handled by a Crossref
search fallback which attempts to find the most likely DOI and then fetch
BibTeX. This reduces failures when users paste a journal article page instead
of the DOI itself.

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
pip install dist/doi2bib3-0.1.0-py3-none-any.whl
```

Import paths and useful functions
-- doi2bib3.backend.get_bibtex_from_doi(doi: str) -> str
	- Fetches BibTeX text for a DOI. Raises `doi2bib3.backend.DOIError` on non-200 responses or invalid DOIs.

-- doi2bib3.backend.arxiv_to_doi(arxivid: str) -> Optional[str]
	- Resolves an arXiv id to a DOI string or returns None if not found.

-- doi2bib3.utils.normalize_bibtex(bib_str: str) -> str
	- Normalizes a BibTeX string (ID cleanup, page formatting, URL decoding, small character fixes).

-- doi2bib3.utils.save_bibtex_to_file(bib_str: str, path: str, append: bool=False) -> None
	- Writes or appends the BibTeX string to a file.

Example usage (save as `fetch_example.py`):

```python
from doi2bib3.backend import get_bibtex_from_doi, arxiv_to_doi, DOIError
from doi2bib3.utils import normalize_bibtex, save_bibtex_to_file

def fetch_by_doi_or_arxiv(identifier: str, out_path: str | None = None) -> str:
	"""Accepts DOI, DOI URL, arXiv id/URL, or publisher URL and returns BibTeX.

	This function delegates to `get_bibtex_from_doi`, which handles arXiv
	detection and Crossref fallback automatically.
	"""
	try:
		raw = get_bibtex_from_doi(identifier)
	except DOIError as exc:
		raise RuntimeError(f"Failed to resolve {identifier}: {exc}") from exc
	cleaned = normalize_bibtex(raw)
	if out_path:
		save_bibtex_to_file(cleaned, out_path, append=True)
		return f"Wrote {out_path}"
	return cleaned

if __name__ == '__main__':
		print(fetch_by_doi('10.1038/nphys1170'))
		# Or:
		# print(fetch_by_arxiv('2411.08091', out_path='paper.bib'))
```

Programmatic CLI call

You can also call the CLI function directly (it accepts an argv list):

```python
from doi2bib3.utils import cli_doi2bib3
cli_doi2bib3(['https://arxiv.org/abs/2411.08091', '--out', 'paper.bib'])
```

License
-------
This project is distributed under the GNU General Public License v3 (GPL-3.0-only).
