# doi2bib3

doi2bib3 is a small Python utility to fetch BibTeX metadata for a DOI or to
resolve arXiv identifiers to DOIs and fetch their BibTeX entries. It accepts
DOI inputs, DOI URLs, arXiv IDs/URLs (modern and legacy), publisher landing
pages, and uses a sequence of resolution strategies to return a BibTeX string.
This tool combines the features of [doi2bib](https://github.com/bibcure/doi2bib/) and [doi2bib2](https://github.com/davidagraf/doi2bib2).

## Key behaviors

- Accepts DOI, DOI URL, arXiv ID/URL, publisher URL, or article-title text.
- Resolves inputs to a DOI using URL metadata, arXiv metadata, Crossref lookup,
  and DOI content negotiation with Crossref fallback.
- Normalizes BibTeX output, including journal abbreviation mappings and
  selected publisher-specific cleanup.
- Full pipeline documentation (input -> output): [`docs/ALGORITHM.md`](docs/ALGORITHM.md)
- Diagram version of the pipeline: [`docs/ALGORITHM_VISUALS.md`](docs/ALGORITHM_VISUALS.md)

A cross-platform **GUI frontend** is available: Check out [QuickBib](https://archisman-panigrahi.github.io/QuickBib) and its [webapp](https://quickbib.streamlit.app/).

## Installation

[![Packaging status](https://repology.org/badge/vertical-allrepos/python:doi2bib3.svg?columns=3)](https://repology.org/project/python:doi2bib3/versions)

[![PyPI - Version](https://img.shields.io/pypi/v/doi2bib3?color=67bed9)](https://pypi.org/project/doi2bib3/)

### Install from pypi

```shell
pip install --user doi2bib3
```

### Arch Linux

In Arch Linux you can install it from the [AUR](https://aur.archlinux.org/packages/python-doi2bib3) with the command `yay -S python-doi2bib3`.

### Ubuntu

You can use our [official PPA](https://code.launchpad.net/~apandada1/+archive/ubuntu/quickbib)

```bash
sudo add-apt-repository ppa:apandada1/quickbib
sudo apt update
sudo apt install python3-doi2bib3
```

### Debian

You can grab the prebuild .deb package from [GitHub releases](https://github.com/archisman-panigrahi/doi2bib3/releases/latest).

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

The CLI accepts a single positional identifier, an optional `-o/--out`
path to save the BibTeX output, and `-b/--bibitem` to also print an
APS/RevTeX-style `\bibitem`. When installed, the package installs a console
script named `doi2bib3` (configured in `pyproject.toml`). From the repository
root you can run the local script wrapper at `scripts/doi2bib3`.

```bash
# using the local wrapper script from repo root
python scripts/doi2bib3 <identifier> [-o OUT] [--bibitem]

# or when installed as console script
doi2bib3 <identifier> [-o OUT] [--bibitem]
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
doi2bib3 arxiv.org/abs/2411.08091
doi2bib3 www.arxiv.org/abs/2411.08091
doi2bib3 http://xxx.lanl.gov/abs/cond-mat/9903064
doi2bib3 arXiv:2411.08091
doi2bib3 2411.08091
doi2bib3 hep-th/9901001
```

Name of the paper (includes fuzzy search):

```bash
doi2bib3 "Projected Topological Branes"
```

Publisher/article pages (Supports APS, AMS, ACS, Science, IOP Science, Nature, PNAS, SciPost, and ScienceDirect journals):

```bash
doi2bib3 https://www.pnas.org/doi/10.1073/pnas.2305943120
doi2bib3 https://iopscience.iop.org/article/10.1088/1402-4896/ad995f/pdf
doi2bib3 https://www.scipost.org/SciPostPhys.20.3.082/
doi2bib3 https://www.scipost.org/SciPostPhys.20.3.082/pdf
doi2bib3 https://www.sciencedirect.com/science/article/pii/S0003491605000096?via%3Dihub
```

Save to a file:

```bash
doi2bib3 https://doi.org/10.1038/nphys1170 -o paper.bib
```

This appends the BibTeX entry to `paper.bib` and prints `Wrote paper.bib`.

Print BibTeX and an APS/RevTeX-style `\bibitem` without saving to a file:

```bash
doi2bib3 https://doi.org/10.1038/nphys1170 --bibitem
```

Save BibTeX to a file and print the `\bibitem`:

```bash
doi2bib3 https://doi.org/10.1038/nphys1170 -o paper.bib --bibitem
```

When `-o/--out` and `--bibitem` are used together, the BibTeX entry is
appended to the file, `Wrote paper.bib` is printed, and the `\bibitem` is
printed to the terminal. The `\bibitem` is not written to the `.bib` file.

Note: If the tool is not installed, you can run `python scripts/doi2bib3 https://doi.org/10.1038/nphys1170`.

## Supported journal groups

`doi2bib3` directly supports many APS, AMS, ACS, Nature, PNAS, SciPost, ScienceDirect and IOP groups of journals.
For other journals, the DOI link works, but the paper's URL would not work..

## Programmatic usage

### Public API

The Python API exposes one primary function:

- `doi2bib3.fetch_bibtex(identifier: str, timeout: int = 15) -> str`

Example:

```python
from doi2bib3 import fetch_bibtex

bib = fetch_bibtex('https://www.pnas.org/doi/10.1073/pnas.2305943120')
print(bib)
```

Additionally two convenience helpers are provided for APS/RevTeX-style
`\bibitem` output:

- `doi2bib3.format_bibtex_to_aps_bibitem(bibtex_str: str, key: Optional[str] = None) -> str`
- `doi2bib3.fetch_bibitem_aps(identifier: str, key: Optional[str] = None, timeout: int = 15) -> str`

Examples:

Format an already-obtained BibTeX string into an APS `\bibitem`:

```python
from doi2bib3 import format_bibtex_to_aps_bibitem

normalized_bibtex = "@article{smith_foobar_2020, title={Foo Bar}, author={Smith, A.}, year={2020}}"
bibitem = format_bibtex_to_aps_bibitem(normalized_bibtex, key="Smith2020")
print(bibitem)
```

Fetch an identifier (DOI/arXiv/etc.), get its normalized BibTeX, and return
an APS `\bibitem` in one call:

```python
from doi2bib3 import fetch_bibitem_aps

bibitem = fetch_bibitem_aps('10.1038/nphys1170', key='PhysRevSmith2008')
print(bibitem)
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

## Future plans

Fix common pitfals listed in https://tex.stackexchange.com/q/386053/78560. This is tracked in [todo.md](./todo.md).