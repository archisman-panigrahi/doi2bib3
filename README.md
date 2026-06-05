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
- **Verifies** existing BibTeX references against CrossRef, arXiv, and the DOI
  Handle System to catch hallucinated or mistyped citations -- see
  [Verifying references](#verifying-references).
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

The CLI has two subcommands -- `fetch` (the historical behaviour) and
`verify` (described below). When installed, the package installs a console
script named `doi2bib3`. From the repository root you can also run the
local wrapper at `scripts/doi2bib3`.

```bash
# Fetch BibTeX for a single identifier (optionally an APS/RevTeX \bibitem)
doi2bib3 fetch <identifier> [-o OUT] [-b/--bibitem]

# Verify the references in a .bib file or project folder
doi2bib3 verify <path> [--json]
```

For backward compatibility, `doi2bib3 <identifier>` with no subcommand is
treated as `doi2bib3 fetch <identifier>`, so every example below continues
to work unchanged.

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

## Verifying references

Large language models often invent realistic-looking citations -- DOIs that
do not resolve, papers that were never written, or DOIs that point to a
completely different article. `doi2bib3 verify` checks every BibTeX entry
against authoritative databases (CrossRef, arXiv, the DOI registry) and
tells you which ones hold up.

Verification is **deterministic**: the real record for each entry is fetched
and the title, authors and year are corroborated in code -- no AI service,
API key, or subscription is involved. Each reference is reported as one of:

- **verified** -- an identifier resolves and the metadata is corroborated, or
  the title and authors were matched in CrossRef.
- **review** -- the work exists, but its registered metadata could not be
  matched to the entry with confidence; worth a quick look.
- **mismatch** -- the DOI/arXiv ID resolves, but to a record with a different
  title *and* different authors.
- **unresolved** -- the DOI/arXiv ID does not resolve in CrossRef or the DOI
  registry.
- **unverified** -- the entry had no identifier and no confident match, or a
  database was unreachable.

```bash
doi2bib3 verify references.bib
doi2bib3 verify ./paper-folder            # walks .bib + .tex files
doi2bib3 verify references.bib --json     # machine-readable output
```

When `.tex` files are present alongside `.bib` files, the tool also reports
`\cite` keys that are not defined in any `.bib` file (a common sign of an
invented citation key).

### Programmatic verification

```python
from doi2bib3 import verify_bibtex, summary

results = verify_bibtex(open("references.bib").read())
print(summary(results))           # counts by status

for r in results:
    if r.needs_attention:
        print(r.key, r.status, r.reason)
```

Lower-level entry points are available too: `parse_bibtex` to split parsing
from verification, `verify_entry` / `verify_entries` for finer control, and
`check_cite_keys` / `extract_cite_keys` for the LaTeX-side cite-key check.

## Supported journal groups

`doi2bib3` directly supports many APS, AMS, ACS, Nature, PNAS, SciPost, ScienceDirect and IOP groups of journals.
For other journals, the DOI link works, but the paper's URL would not work..

## Programmatic usage

### Public API

The Python API exposes:

- `doi2bib3.fetch_bibtex(identifier: str, timeout: int = 15) -> str`
- `doi2bib3.verify_bibtex(text: str, *, timeout: int = 20) -> list[VerificationResult]`
- `doi2bib3.parse_bibtex(text: str) -> list[BibEntry]`
- `doi2bib3.verify_entry(entry, *, timeout: int = 20) -> VerificationResult`
- `doi2bib3.verify_entries(entries, *, timeout: int = 20, max_workers: int = 4, progress=None) -> list[VerificationResult]`
- `doi2bib3.summary(results) -> dict[str, int]`
- `doi2bib3.check_cite_keys(tex_sources, defined_keys) -> CiteCheckResult`

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
- `doi2bib3/cli.py`: argparse-based CLI with `fetch` and `verify` subcommands
- `doi2bib3/verify/`: deterministic reference verification engine
  (parser, matching, CrossRef/arXiv/DOI-handle lookups, verdict logic)
- `scripts/doi2bib3`: legacy script wrapper that forwards to `doi2bib3.cli`

## License

This project is distributed under the GNU General Public License v3 (GPL-3.0-only).

## Acknowledgements

Parts of the code and documentation were assisted by copilot and codex.
