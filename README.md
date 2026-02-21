# doi2bib3

doi2bib3 is a small Python utility to fetch BibTeX metadata for a DOI or to
resolve arXiv identifiers to DOIs and fetch their BibTeX entries. It accepts
DOI inputs, DOI URLs, arXiv IDs/URLs (modern and legacy), publisher landing
pages, and uses a sequence of resolution strategies to return a BibTeX string.
This tool combines the features of [doi2bib](https://github.com/bibcure/doi2bib/) and [doi2bib2](https://github.com/davidagraf/doi2bib2).

Key behaviors

- Provides bibtex entry for DOI and arXiv links.
- Automatically detects arXiv inputs (e.g. `2411.08091`, `arXiv:2411.08091`,
  or `https://arxiv.org/abs/2411.08091`) and queries the arXiv API for a DOI.
- For non-arXiv inputs: attempts DOI normalization, content negotiation at
  doi.org, Crossref transform, and as a last resort a Crossref bibliographic
  search.
- Full pipeline documentation (input -> output): [`docs/ALGORITHM.md`](docs/ALGORITHM.md)
- Diagram version of the pipeline: [`docs/ALGORITHM_VISUALS.md`](docs/ALGORITHM_VISUALS.md)

A cross-platform **GUI frontend** is available: Check out [QuickBib](https://archisman-panigrahi.github.io/QuickBib) and its [webapp](https://quickbib.streamlit.app/).

## Installation

[![Packaging status](https://repology.org/badge/vertical-allrepos/python:doi2bib3.svg?columns=3)](https://repology.org/project/python:doi2bib3/versions)


### Install from pypi

```shell
pip install --user doi2bib3
```

### Arch Linux

In Arch Linux you can install it from the [AUR](https://aur.archlinux.org/packages/doi2bib3) with the command `yay -S python-doi2bib3`.

### Ubuntu

You can use our [official PPA](https://code.launchpad.net/~apandada1/+archive/ubuntu/quickbib)

```bash
sudo add-apt-repository ppa:apandada1/quickbib
sudo apt update
sudo apt install python3-doi2bib3
```

### Installing from source

Create a virtual environment and install runtime dependencies:

```bash
git clone https://github.com/archisman-panigrahi/doi2bib3.git
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install the package for local development:

```bash
pip install -e .
```

## CLI usage

The CLI accepts a single positional identifier and an optional `-o/--out`
path to save the BibTeX output. When installed, the package installs a console
script named `doi2bib3` (configured in `pyproject.toml`). From the repository
root you can run the local script wrapper at `scripts/doi2bib3`.

```bash
# using the local wrapper script from repo root
python scripts/doi2bib3 <identifier> [-o OUT]

# or when installed as console script
doi2bib3 <identifier> -o references.bib
```

## Examples

Fetch by DOI (bare DOI or DOI URL):

```bash
doi2bib3 10.1038/nphys1170
doi2bib3 https://doi.org/10.1038/nphys1170
```

ArXiv inputs (detected automatically):

```bash
doi2bib3 https://arxiv.org/abs/2411.08091
doi2bib3 arXiv:2411.08091
doi2bib3 2411.08091
doi2bib3 hep-th/9901001
```

Name of the paper (includes fuzzy search):

```bash
doi2bib3 "Projected Topological Branes"
```

Save to a file:

```bash
doi2bib3 https://doi.org/10.1038/nphys1170 -o paper.bib
```

Note: If the tool is not installed, you can run `python scripts/doi2bib3 https://doi.org/10.1038/nphys1170`.

## Programmatic usage

### Public API

The Python API intentionally exposes one primary function:

- `doi2bib3.fetch_bibtex(identifier: str, timeout: int = 15) -> str`

Behavior:

- Accepts DOI, DOI URL, arXiv ID/URL, publisher URL, or article-title text.
- Resolves input to a DOI using arXiv and/or Crossref when needed.
- Fetches BibTeX via DOI content negotiation (with Crossref fallback).
- Returns normalized BibTeX output (same formatting as CLI output).
- Full step-by-step algorithm: [`docs/ALGORITHM.md`](docs/ALGORITHM.md)

Example:

```python
from doi2bib3 import fetch_bibtex

bib = fetch_bibtex('https://www.pnas.org/doi/10.1073/pnas.2305943120')
print(bib)
```

### Programmatic CLI entry

Use `subprocess` with `scripts/doi2bib3` (or installed `doi2bib3` command)
for automated CLI tests.

## Internal module layout

- `doi2bib3/backend.py`: input resolution and network fetch logic
- `doi2bib3/normalize.py`: BibTeX normalization/transforms
- `doi2bib3/io.py`: file output helpers
- `scripts/doi2bib3`: command-line argument parsing and output handling

## License

This project is distributed under the GNU General Public License v3 (GPL-3.0-only).

## Acknowledgements

Parts of the code and documentation were assisted by copilot and codex.
