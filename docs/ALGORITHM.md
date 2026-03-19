# doi2bib3 Algorithm (Input -> Output)

This document describes exactly what doi2bib3 does for each input string, and where each step is implemented.
For visualization see [ALGORITHM_VISUALS.md](./ALGORITHM_VISUALS.md).

## 1. Entry points

- CLI shell script: `scripts/doi2bib3`
  - Parser creation: `build_parser()` in `scripts/doi2bib3`
  - CLI orchestration: `main(argv=None)` in `scripts/doi2bib3`
- Programmatic API: `doi2bib3.fetch_bibtex(identifier, timeout=15)`
  - Re-exported from `doi2bib3/__init__.py`
  - Implemented in `fetch_bibtex()` in `doi2bib3/backend.py`

The same backend pipeline is used by both CLI and API.

## 2. CLI flow

Given user input:

1. Parse args:
- positional `identifier`
- optional `-o/--out`
- Implemented by `build_parser()` and `argparse` wiring in `main()` (`scripts/doi2bib3`)

2. If `identifier` is missing:
- print help
- exit code 2
- Implemented by `main()` (`scripts/doi2bib3`)

3. Call `fetch_bibtex(identifier)`.
- Implemented by `main()` calling `fetch_bibtex()` (`scripts/doi2bib3` -> `doi2bib3/backend.py`)

4. If `-o/--out` is set:
- append output to file (insert a newline first when file is non-empty and does not end with `\n`)
- print `Wrote <path>`
- Implemented by `save_bibtex_to_file(..., append=True)` in `doi2bib3/io.py`, called from `main()`

5. Otherwise:
- print BibTeX to stdout
- Implemented by `main()` (`scripts/doi2bib3`)

On any exception, CLI prints `Error: <message>` to stderr and exits code 1.
- Implemented by `try/except` in `main()` (`scripts/doi2bib3`)

## 3. Core API flow (`fetch_bibtex`)

`fetch_bibtex(identifier, timeout)` does:

1. Resolve input identifier to a DOI string.
- `_resolve_identifier()` in `doi2bib3/backend.py`

2. Fetch BibTeX for that DOI (`doi.org` first, Crossref transform fallback).
- `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`

3. Normalize BibTeX fields and formatting.
- `normalize_bibtex()` in `doi2bib3/normalize.py`

4. Return normalized BibTeX text.
- `fetch_bibtex()` in `doi2bib3/backend.py`
- If normalization fails, `fetch_bibtex()` returns raw BibTeX as fallback.

## 4. Identifier -> DOI resolution

Resolution order is deterministic and is implemented in `_resolve_identifier()` (`doi2bib3/backend.py`).

### 4.1 Try arXiv parsing first

Input is considered arXiv if it matches one of these forms:

- `arXiv:2411.08091`
- `2411.08091` (with optional `vN`)
- legacy IDs like `hep-th/9901001` (with optional `vN`)
- arXiv DOI forms such as:
  - `10.48550/arXiv.2411.08091`
  - `https://doi.org/10.48550/arXiv.2411.08091`
- arXiv URLs such as:
  - `https://arxiv.org/abs/...`
  - `https://arxiv.org/pdf/...pdf`
  - `https://arxiv.org/html/...`

Implementation:

1. Parse and validate arXiv form.
- `_parse_arxiv_id_string()` using `ARXIV_ID_PATTERN` in `doi2bib3/backend.py`
- arXiv DOI inputs are recognized by `_parse_arxiv_id_from_doi_string()` in `doi2bib3/backend.py`

2. Query arXiv API for metadata:
- tries these endpoints in order until one succeeds with a non-empty feed:
  - `http://export.arxiv.org/api/query?id_list=<id>`
  - `https://export.arxiv.org/api/query?id_list=<id>`
  - `https://arxiv.org/api/query?id_list=<id>`
  - `http://arxiv.org/api/query?id_list=<id>`
- sends a `User-Agent` header for the arXiv request
- implemented by `_fetch_arxiv_entry()` / `_fetch_arxiv_metadata()` in `doi2bib3/backend.py`

3. Extract metadata from the arXiv Atom entry:
- published DOI from the first matching pattern:
- `<arxiv:doi>...</arxiv:doi>`
- `<doi>...</doi>`
- DOI links like `https://doi.org/...` or `https://dx.doi.org/...`
- primary category from `<arxiv:primary_category term="...">`
- implemented by `_extract_published_doi_from_arxiv_entry()` and `_extract_primary_class_from_arxiv_entry()` in `doi2bib3/backend.py`

4. If a published DOI is present:
- use that DOI
- implemented by `_resolve_arxiv_identifier()` in `doi2bib3/backend.py`

5. If no published DOI is found from arXiv metadata:
- try DataCite-style fallback DOI: `10.48550/arXiv.<id-without-version>`
- version suffix is removed before constructing the DOI
- implemented by `_resolve_arxiv_identifier()` in `doi2bib3/backend.py`

6. If still invalid:
- raise `DOIError("No DOI found for arXiv id: ...")`
- implemented by `_resolve_arxiv_identifier()` in `doi2bib3/backend.py`

### 4.2 If not arXiv, try DOI parsing

Accept DOI-like input:

- bare DOI, e.g. `10.1038/nphys1170`
- `doi:10.1038/nphys1170`
- DOI URL, e.g. `https://doi.org/10.1038/nphys1170`

Special case:

- if the DOI parses as `10.48550/arXiv.<id>`, it is treated as an arXiv preprint DOI and arXiv metadata is still queried for enrichment
- BibTeX is still fetched from the DOI itself

Normalization rules:

- trim whitespace
- remove `doi:` prefix
- if URL, keep path without leading `/`
- URL-decode (%xx)
- validate against DOI regex: `^10\.\d{4,9}/\S+$`

Implemented by `_parse_doi_string()` in `doi2bib3/backend.py`.

### 4.3 If not DOI, search via URL heuristics + Crossref

Used for publisher URLs and free-text (including paper titles).

#### URL heuristic phase (if input looks like URL)

1. Try DOI pattern from URL path directly.
- `_doi_candidates_from_url_path()` + `_first_valid_doi()` in `doi2bib3/backend.py`

2. If none, fetch page HTML.
- first request with bot user-agent
- retry once with browser user-agent + `Referer` when needed
- `_fetch_html_for_doi_extraction()` in `doi2bib3/backend.py`

3. Scan HTML for DOI candidates in this order:
- `meta[name=citation_doi]`
- `meta[name=dc.identifier|dcterms.identifier]`
- links to `doi.org` / `dx.doi.org`
- DOI-like patterns in `href/src`
- generic DOI-like text pattern
- `_doi_candidates_from_html()` in `doi2bib3/backend.py`

4. First valid parsed DOI wins.
- `_first_valid_doi()` in `doi2bib3/backend.py`
- orchestrated by `_extract_doi_from_publisher_url()`

#### Crossref phase

If still unresolved:

1. Query:
- `https://api.crossref.org/works?query.bibliographic=<query>&rows=5`
- `_search_doi_via_crossref()` in `doi2bib3/backend.py`

2. If URL query, prefer candidate whose returned `URL` contains the same netloc.
- Implemented in `_search_doi_via_crossref()`

3. Otherwise choose highest Crossref `score`.
- Implemented in `_search_doi_via_crossref()`

4. Parse/validate selected DOI.
- `_parse_doi_string()` called by `_resolve_identifier()` / `_resolve_identifier_to_doi()`

If none found: raise `DOIError("Crossref lookup failed for: ...")`.
- Implemented in `_resolve_identifier_to_doi()`

## 5. DOI -> raw BibTeX retrieval

Given resolved DOI:

1. Request `https://doi.org/<doi>` with headers:
- `Accept: application/x-bibtex; charset=utf-8`
- `User-Agent: doi2bib-python/1.0`
- Implemented in `_fetch_bibtex_for_doi()` (`doi2bib3/backend.py`)

2. If HTTP 200:
- decode bytes as UTF-8 first
- fallback to apparent/declared encoding with replacement on errors
- Implemented by `_decode_response_text()` called from `_fetch_bibtex_for_doi()`

3. If not 200:
- request Crossref transform endpoint:
  - `https://api.crossref.org/works/<url-quoted-doi>/transform/application/x-bibtex`
- Implemented in `_fetch_bibtex_for_doi()`

4. If both fail:
- raise `DOIError` with both HTTP status codes.
- Implemented in `_fetch_bibtex_for_doi()`

## 6. BibTeX normalization

Raw provider BibTeX is normalized before returning.
- Main function: `normalize_bibtex(bib_str, arxiv_id=None, primary_class=None, include_arxiv_fields=False)` in `doi2bib3/normalize.py`

For each entry:

1. Recompute citation key as:
- `Lastname_firstword_year`
- `Lastname`: last name of first author
- `firstword`: first token of title
- `year`: year field
- sanitize non-alphanumeric (hyphen preserved)
- fallback to existing ID or `entry`
- Implemented by nested `_make_bibtex_key()` called inside `normalize_bibtex()`

2. Normalize pages:
- remove pages when value is one of: `n/a-n/a`, `na-na`, `n/a`, `na`
- normalize en/em dashes and numeric ranges to `--`
- Implemented in pages block inside `normalize_bibtex()`

3. APS-specific enrichment:
- if publisher contains `American Physical Society` and pages missing:
  - query Crossref work metadata
  - copy `article-number` into pages when available
- Implemented by `fetch_article_number_from_crossref()` + APS check in `normalize_bibtex()`

4. If `url` exists:
- URL-decode it
- drop `doi` field (avoid duplication)
- Implemented in URL block inside `normalize_bibtex()`

5. Unpublished arXiv enrichment:
- when `include_arxiv_fields=True` and an arXiv id is available:
  - add `archivePrefix = {arXiv}`
  - add `eprint = {<arxiv-id-without-version>}`
  - add `primaryClass = {<primary-category>}` when available
- used only for arXiv inputs that do not have a published journal DOI
- implemented in `normalize_bibtex()`

6. Title formatting:
- convert `\{\var...\}` placeholders to math form with dollars
- protect capitalized words by wrapping with `{...}`
- Implemented by `insert_dollars()` and `protect_capitalized_words()` called in `normalize_bibtex()`

7. Journal formatting:
- apply abbreviation mapping from bundled JSON dictionaries:
  - `APS_replacement.json`
  - `Nature_replacement.json`
- Mapping load: `_load_journal_replacements()` at import time
- Abbreviation lookup: `abbreviate_journal_name()`
- Applied inside `normalize_bibtex()`

8. Month cleanup:
- strip outer braces `{January}` -> `January`
- Implemented in month block inside `normalize_bibtex()`

9. Special character encoding:
- apply selected unicode -> LaTeX substitutions in
  - `title`
  - `journal`
  - `booktitle`
- Implemented by `encode_special_chars()` called from `normalize_bibtex()`

Finally, serialize with `bibtexparser.dumps`.
- Implemented as return statement in `normalize_bibtex()`

## 7. Output guarantees

- Public Python API always attempts to return normalized BibTeX.
  - Function: `fetch_bibtex()` in `doi2bib3/backend.py`
- If normalization raises, raw BibTeX is returned instead.
  - Function: `fetch_bibtex()` fallback `except`
- CLI prints exactly what `fetch_bibtex()` returns unless `-o` is used.
  - Function: `main()` in `scripts/doi2bib3`
- With `-o`, the same content is appended to the target file.
  - Functions: `main()` + `save_bibtex_to_file(..., append=True)`

## 8. Network dependencies

Resolution/fetch may contact:

- `export.arxiv.org` / `arxiv.org` API endpoints (arXiv metadata)
  - `_fetch_arxiv_entry()` / `_fetch_arxiv_metadata()` in `doi2bib3/backend.py`
- `doi.org` (content negotiation for BibTeX)
  - `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`
- `api.crossref.org` (search, transform, APS article-number)
  - `_search_doi_via_crossref()` in `doi2bib3/backend.py`
  - `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`
  - `fetch_article_number_from_crossref()` in `doi2bib3/normalize.py`

If network access is blocked/unavailable, DOI/arXiv/title lookups will fail with an error.
