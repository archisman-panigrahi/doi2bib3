# doi2bib3

doi2bib3 is a small Python utility to fetch BibTeX metadata for a DOI or to
resolve arXiv identifiers to DOIs and fetch their BibTeX entries. It accepts
DOI inputs, DOI URLs, arXiv IDs/URLs (modern and legacy), publisher landing
pages, and uses a sequence of resolution strategies to return a BibTeX string.
This tool combines the features of [doi2bib](https://github.com/bibcure/doi2bib/) and [doi2bib2](https://github.com/davidagraf/doi2bib2).


Key behaviors
- Provides bibtex entry for DOI and arXiv links.
- Automatically detects arXiv inputs (e.g. `2411.08091`, `arXiv:2411.08091`, or `https://arxiv.org/abs/2411.08091`) and queries the arXiv API for a DOI.
- For non-arXiv inputs: attempts DOI normalization, content negotiation at doi.org, Crossref transform, and as a last resort a Crossref bibliographic search.

A cross-platform **GUI frontend** is available: Check out [QuickBib](https://archisman-panigrahi.github.io/QuickBib).

Installation
------------
### Install from pypi

[![PyPI version](https://badge.fury.io/py/doi2bib3.svg)](https://badge.fury.io/py/doi2bib3)
```
pip install --user doi2bib3
```

<a href="https://repology.org/project/doi2bib3/versions">
    <img src="https://repology.org/badge/vertical-allrepos/doi2bib3.svg" alt="Packaging status" align="right">
</a>

### Arch Linux
In Arch Linux you can install it from the [AUR](https://aur.archlinux.org/packages/doi2bib3) with the command `yay -S doi2bib3`. 

### Ubuntu
You can use our [official PPA](https://code.launchpad.net/~apandada1/+archive/ubuntu/quickbib)
```
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

CLI usage
---------

The CLI accepts a single positional identifier and an optional `-o/--out`
path to save the BibTeX output. When installed, the package installs a console
script named `doi2bib3` (configured in `pyproject.toml`). From the repository
root you can also run the provided `main.py` shim.

```bash
# using the local shim
python main.py <identifier> [-o OUT]

# or when installed as console script
doi2bib3 <identifier> -o references.bib
```

Examples
--------

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

Note: If the tool is not installed, you can run it with `python main.py https://doi.org/10.1038/nphys1170` and so on.

Programmatic usage
------------------

The package exposes a small programmatic API so you can use doi2bib3 from
Python code. The most convenient entry point is the package-level
`fetch_bibtex` function which mirrors the CLI behavior and returns normalized
BibTeX by default:

```python
from doi2bib3 import fetch_bibtex

# Get normalized BibTeX (default)
bib = fetch_bibtex('https://www.pnas.org/doi/10.1073/pnas.2305943120')
print(bib)

# Get the raw provider output without normalization
raw = fetch_bibtex('10.1073/pnas.2305943120', normalize=False)
```

You can also invoke the thin CLI wrapper from `utils` when writing tests or
automation:

```python
from doi2bib3.utils import cli_doi2bib3
cli_doi2bib3(['https://arxiv.org/abs/2411.08091', '--out', 'paper.bib'])
```

License
-------
This project is distributed under the GNU General Public License v3 (GPL-3.0-only).

Acknowledgements
---------------
Parts of the code and documentation were assisted by copilot.
