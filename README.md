This small set of scripts fetches BibTeX for a DOI (or resolves PMID/arXiv id to DOI) and can save or email the resulting .bib file.

Requirements
------------
Install the Python dependencies (recommended in a venv):

pip install -r requirements.txt

Usage
-----
Examples:

Fetch by DOI and print:

python cli.py fetch --doi 10.1038/nphys1170

Fetch by DOI and save to file:

python cli.py fetch --doi 10.1038/nphys1170 --out paper.bib

Resolve a PMID and save:

python cli.py pmid --pmid 12345678 --out paper.bib

Resolve an arXiv id and save:

python cli.py arxiv --id 1901.00001 --out paper.bib

Notes
-----
- The scripts use the same upstream services as the original project:
  - DOI -> BibTeX via https://doi.org/ (content negotiation)
  - PMID -> DOI via NCBI idconv service
  - arXiv -> DOI via the arXiv API

- The code normalizes a few BibTeX quirks (pages, url decoding, simple special character replacements).
