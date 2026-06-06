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
- optional `-b/--bibitem`
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

6. If `-b/--bibitem` is set:
- format the fetched BibTeX as an APS/RevTeX-style `\bibitem`
- print it to stdout after the BibTeX output or after the `Wrote <path>` message
- if formatting fails, print a warning to stderr but keep exit code 0
- the `\bibitem` is not written to `-o/--out`
- Implemented by `format_bibtex_to_aps_bibitem()` in `doi2bib3/bibitem.py`, called from `main()`

If `fetch_bibtex()` raises, CLI prints `Error: <message>` to stderr and exits code 1.
- Implemented by the fetch `try/except` in `main()` (`scripts/doi2bib3`)

## 3. Core API flow (`fetch_bibtex`)

`fetch_bibtex(identifier, timeout)` does:

1. Try ISBN parsing first.
- If the input is a valid ISBN-10 or ISBN-13, fetch public book metadata,
  construct a raw `@book` BibTeX entry, normalize it, and return it.
- Open Library is tried first; Google Books is used as a fallback if Open
  Library fails or has no matching result.
- Implemented by `_parse_isbn_string()`, `_fetch_bibtex_for_isbn()`, and
  `normalize_bibtex()` in `doi2bib3/backend.py`.

2. Resolve non-ISBN input to a DOI string plus optional arXiv metadata.
- `_resolve_identifier()` in `doi2bib3/backend.py`

3. Fetch BibTeX for that DOI (`doi.org` first, Crossref transform fallback).
- `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`

4. Normalize BibTeX fields and formatting.
- `normalize_bibtex()` in `doi2bib3/normalize.py`
- Unpublished arXiv metadata is passed through only when the arXiv entry has no
  published journal DOI, so published arXiv inputs resolve to the journal DOI
  without adding `archivePrefix`, `eprint`, or `primaryClass`.

5. Return normalized BibTeX text.
- `fetch_bibtex()` in `doi2bib3/backend.py`
- If normalization fails, `fetch_bibtex()` returns raw BibTeX as fallback.

## 4. ISBN resolution

ISBN handling is a direct BibTeX fetch path and does not go through DOI
resolution.

Accepted forms:

- ISBN-13, e.g. `9780465024933`
- ISBN-10, e.g. `0306406152`
- formatted variants with spaces or hyphens, e.g. `ISBN 978-0-465-02493-3`
- `ISBN-10:`, `ISBN-13:`, and `urn:isbn:` prefixes

Implementation:

1. Strip the optional ISBN prefix, spaces, and hyphens.
- `_parse_isbn_string()` in `doi2bib3/backend.py`

2. Validate the canonical string.
- ISBN-10 accepts nine digits plus a digit or `X` check character.
- ISBN-13 accepts thirteen digits.
- Checksum validation is performed by `_is_valid_isbn10()` and
  `_is_valid_isbn13()`.

3. Query Open Library first:
- `https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&jscmd=data&format=json`
- sends `Accept: application/json` and the shared doi2bib3 `User-Agent`
- implemented by `_openlibrary_book_info()`

4. If Open Library fails or has no result, query Google Books:
- `https://www.googleapis.com/books/v1/volumes?q=isbn:<isbn>`
- sends `Accept: application/json` and the shared doi2bib3 `User-Agent`
- implemented by `_google_books_volume_info()`

5. Use the first returned book/volume with a title and construct `@book` BibTeX:
- `title` plus `subtitle` when present
- `author` joined with BibTeX `and`
- `publisher`
- four-digit `year` from `publishedDate` / `publish_date`
- `isbn`
- `url` from `canonicalVolumeLink`, `infoLink`, or the Open Library book URL
- implemented by `_bibtex_from_google_books_volume()` and
  `_bibtex_from_openlibrary_book()`

6. Normalize and return the resulting `@book`.
- Implemented by `fetch_bibtex()` calling `normalize_bibtex()`.

If both providers fail or return no matching volume, ISBN resolution raises
`DOIError("ISBN lookup failed for ...")`.

## 5. Identifier -> DOI resolution

Resolution order is deterministic and is implemented in `_resolve_identifier()` (`doi2bib3/backend.py`).

### 5.1 Try arXiv parsing first

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
  - old LANL aliases like `http://xxx.lanl.gov/abs/...` and `http://xxx.lanl.gov/pdf/...pdf`
  - scheme-less forms like `arxiv.org/abs/...`, `arxiv.org/pdf/...pdf`, or `xxx.lanl.gov/abs/...`

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
- sends the shared doi2bib3 `User-Agent` header for the arXiv request
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

### 5.2 If not arXiv, try DOI parsing

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

### 5.3 If not DOI, search via URL heuristics + Crossref

Used for publisher URLs and free-text (including paper titles).

#### URL heuristic phase (if input looks like URL)

1. Try DOI pattern from URL path directly.
- For IOP Science URL paths ending in `/pdf`, strip that view suffix before
  DOI matching so the article DOI is used.
- For SciPost article paths like `/SciPostPhys.20.3.082` or
  `/SciPostPhys.20.3.082/pdf`, convert the path to its DOI form
  `10.21468/SciPostPhys.20.3.082`.
- `_doi_candidates_from_url_path()` + `_first_valid_doi()` in `doi2bib3/backend.py`

2. If the URL is a ScienceDirect `/science/article/pii/...` link:
- extract the Elsevier PII from the URL path
- query `https://api.elsevier.com/content/article/pii/<pii>`
- scan the returned metadata with the same DOI candidate extractor used for
  publisher HTML
- implemented by `_extract_doi_from_sciencedirect_url()` in `doi2bib3/backend.py`

3. If none, fetch page HTML.
- first request with bot user-agent
- retry once with browser user-agent + `Referer` when needed
- `_fetch_html_for_doi_extraction()` in `doi2bib3/backend.py`

4. Scan HTML for DOI candidates in this order:
- `meta[name=citation_doi]`
- `meta[name=dc.identifier|dcterms.identifier]`
- links to `doi.org` / `dx.doi.org`
- DOI-like patterns in `href/src`
- generic DOI-like text pattern
- `_doi_candidates_from_html()` in `doi2bib3/backend.py`

5. First valid parsed DOI wins.
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

## 6. DOI -> raw BibTeX retrieval

Given resolved DOI:

1. Request `https://doi.org/<doi>` with headers:
- `Accept: application/x-bibtex; charset=utf-8`
- `User-Agent: doi2bib3-python/1.0 (https://github.com/archisman-panigrahi/doi2bib3)`
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

## 7. BibTeX normalization

Raw provider BibTeX is normalized before returning.
- Main function: `normalize_bibtex(bib_str, arxiv_id=None, primary_class=None, include_arxiv_fields=False)` in `doi2bib3/normalize.py`
- The parser is seeded with common month string definitions before parsing, so
  provider output such as `month=july` can be resolved even when the provider
  omitted `@string` definitions. These helper string definitions are removed
  before serialization.

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

3. Article-number enrichment:
- if pages are missing and the entry has a DOI:
  - query Crossref work metadata
  - copy `article-number` into pages when available
- Implemented by `fetch_article_number_from_crossref()` and the missing-pages block in `normalize_bibtex()`

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
- Unicode-normalize the title to NFC.
- Convert embedded inline MathML blocks to LaTeX math with `mathml_to_latex()`.
- Convert simple HTML italic tags such as `<i>v</i>` to `\textit{v}` with
  `html_italics_to_latex()`.
- Convert `\{\var...\}` placeholders to math form with dollars.
- Normalize plus/minus notation:
  - outside math: `+-` or `±` -> `$\pm$`
  - inside existing `$...$` math: `+-` or `±` -> `\pm`
- Convert compact plain-text chemical formulas to LaTeX math with
  `chemical_formulas_to_latex()`.
- Insert spaces around inline `$...$` math spans when provider titles attach
  math directly to neighboring words.
- Escape title LaTeX-special characters `&`, `%`, and `#`, without
  double-escaping already escaped forms; HTML entities such as `&amp;` are
  decoded first.
- Collapse ASCII whitespace runs in titles to a single space.
- Protect capitalized words by wrapping with `{...}`.
- Implemented by `mathml_to_latex()`, `html_italics_to_latex()`,
  `insert_dollars()`, `plus_minus_to_latex()`,
  `chemical_formulas_to_latex()`, `ensure_space_around_math()`,
  `escape_latex_chars()`, `normalize_title_whitespace()`, and
  `protect_capitalized_words()` called in `normalize_bibtex()`.

### 7.1 Inline MathML title conversion

Some publishers return formulas in titles as inline MathML instead of LaTeX,
for example APS titles containing `<mml:math>...</mml:math>`.

The conversion pass works as follows:

1. Find complete inline MathML blocks using `MATHML_RE`.
   - Both unprefixed `<math>` and namespaced `<mml:math>` tags are accepted.
   - Matching is limited to the full math block, so surrounding title text is
     left untouched.
2. Normalize smart quotes in XML attributes before parsing, because some DOI
   content-negotiation responses contain typographic quotes around namespace
   attributes.
3. Parse the block with `xml.etree.ElementTree`.
4. Convert supported MathML nodes recursively:
   - `math` becomes a `$...$` LaTeX math span.
   - `mrow` concatenates converted child nodes.
   - `mi` becomes a Greek LaTeX command when it is a recognized Greek symbol,
     roman text with `\mathrm{...}` when it is a multi-character identifier
     such as `RuCl`, or escaped text otherwise.
   - `mn` and `mo` become escaped math text, with Unicode minus normalized to
     `-`.
   - `mtext` becomes `\text{...}`; minus-like text becomes `\text{-}`.
   - `msub`, `msup`, and `msubsup` become grouped `_`, `^`, or combined
     subscript/superscript LaTeX.
5. If XML parsing fails, strip tags as a fallback and convert recognized Greek
   symbols and minus signs while still wrapping the result in `$...$`.

Example:

```text
<mml:mi>α</mml:mi><mml:mtext>−</mml:mtext>
<mml:msub><mml:mi>RuCl</mml:mi><mml:mn>3</mml:mn></mml:msub>
```

becomes:

```latex
$\alpha\text{-}{\mathrm{RuCl}}_{3}$
```

### 7.2 Plain-text chemical formula conversion

Some publishers return chemical formulas as ordinary title text, for example
`(Pb,Bi)2Sr2CuO6+δ`. Without a formula-aware pass, the later capitalization
protection treats element symbols as ordinary title words and produces invalid
chemistry such as `({Pb},{Bi})2{Sr2CuO6}+δ`.

The plain-text formula parser is deliberately conservative:

1. Split the title on existing `$...$` math spans.
   - Only non-math segments are scanned.
   - This prevents already-correct LaTeX math from being converted twice.
2. Find compact formula-like chunks using `CHEMICAL_FORMULA_RE`.
   - A candidate must start at a non-letter/non-backslash boundary.
   - It must begin with either an element-like token matching `[A-Z][a-z]?`,
     such as `Pb`, `O`, or `Cu`, or a comma-separated mixed site group such
     as `(Pb,Bi)`.
   - It may then contain element-like tokens, mixed site groups,
     stoichiometric numbers, `+`/`-`/Unicode minus, and selected Greek
     composition variables such as `δ`.
   - It must not be immediately followed by a lowercase letter. This helps
     avoid catching prefixes inside normal words.
3. Reject weak candidates unless they contain:
   - at least one element-like token, and
   - either a digit or a recognized Greek composition variable.
4. Tokenize accepted formulas with `FORMULA_TOKEN_RE`.
   - Mixed site group: `(Pb,Bi)`
   - Element-like token: `Sr`, `Cu`, `O`
   - Stoichiometric number, optionally with signed Greek suffix: `2`, `6+δ`
   - Standalone recognized Greek variable or sign
5. Convert tokens:
   - element-like tokens -> `\mathrm{Element}`
   - mixed site groups -> `(\mathrm{Pb},\mathrm{Bi})`
   - numeric tokens -> `_{...}` subscripts
   - Greek variables -> LaTeX commands such as `\delta`
   - Unicode minus -> `-`
6. Wrap the converted formula in `$...$`.

Example:

```text
(Pb,Bi)2Sr2CuO6+δ
```

is tokenized as:

```text
(Pb,Bi), 2, Sr, 2, Cu, O, 6+δ
```

and becomes:

```latex
$(\mathrm{Pb},\mathrm{Bi})_{2}\mathrm{Sr}_{2}\mathrm{Cu}\mathrm{O}_{6+\delta}$
```

Known intentional limits:

- The parser handles compact formula notation found in titles; it is not a
  complete chemistry grammar.
- It does not validate element symbols against a periodic-table list. The
  code uses the syntactic pattern `[A-Z][a-z]?`, plus surrounding formula
  structure, to keep the implementation small and avoid a bundled element
  table.
- Parenthesized groups are currently intended for comma-separated mixed sites
  such as `(Pb,Bi)`, not every possible inorganic formula convention.
- It avoids scanning existing LaTeX math spans, so provider-supplied correct
  math is preserved as-is.

### 7.3 HTML, spacing, and LaTeX-special title cleanup

Some provider BibTeX contains lightweight HTML and raw LaTeX-special
characters in titles. The title cleanup passes are generic and not
publisher-specific:

- `<i>...</i>` spans become `\textit{...}`.
- `+-` and `±` become `\pm` inside existing math and `$\pm$` outside math.
- Inline math spans are separated from adjacent text, for example
  `in${...}$` -> `in ${...}$` and `${s}_{\pm}$Pairing` ->
  `${s}_{\pm}$ Pairing`.
- Raw `&`, `%`, and `#` in titles are escaped as `\&`, `\%`, and `\#`.
  Already escaped versions are left unchanged.
- HTML entities are decoded before escaping, so `&amp;` becomes `\&`.
- Provider newlines and repeated ASCII spaces in titles are collapsed to a
  single space.

7. Journal formatting:
- apply abbreviation mapping from bundled JSON dictionaries:
  - `APS_replacement.json`
  - `Nature_replacement.json`
  - `IOP_replacement.json`
- Mapping load: `_load_journal_replacements()` at import time
- Abbreviation lookup: `abbreviate_journal_name()`
- HTML entities are decoded and raw `&` is escaped as `\&`.
- Applied inside `normalize_bibtex()`

Publisher-specific note:
- ScienceDirect/Elsevier handling is part of identifier resolution, before raw
  BibTeX fetch, because ScienceDirect URLs often expose a PII instead of a DOI.
- Crossref article-number enrichment and APS/Nature/IOP journal abbreviations are part of
  BibTeX normalization, after raw BibTeX has already been fetched.

8. Month cleanup:
- strip outer braces `{January}` -> `January`
- Implemented in month block inside `normalize_bibtex()`

9. Special character encoding:
- apply selected unicode -> LaTeX substitutions in
  - `title`
  - `author`
  - `booktitle`
- Implemented by `encode_special_chars()` called from `normalize_bibtex()`

Finally, serialize with `bibtexparser.dumps`.
- Implemented as return statement in `normalize_bibtex()`

## 8. Output guarantees

- Public Python API always attempts to return normalized BibTeX.
  - Function: `fetch_bibtex()` in `doi2bib3/backend.py`
- If normalization raises, raw BibTeX is returned instead.
  - Function: `fetch_bibtex()` fallback `except`
- CLI prints exactly what `fetch_bibtex()` returns unless `-o` is used.
  - Function: `main()` in `scripts/doi2bib3`
- With `-o`, the same content is appended to the target file.
  - Functions: `main()` + `save_bibtex_to_file(..., append=True)`

## 9. Network dependencies

Resolution/fetch may contact:

- `www.googleapis.com/books/v1/volumes` (Google Books ISBN metadata)
  - `_google_books_volume_info()` in `doi2bib3/backend.py`
- `openlibrary.org/api/books` (Open Library ISBN metadata fallback)
  - `_openlibrary_book_info()` in `doi2bib3/backend.py`
- `export.arxiv.org` / `arxiv.org` API endpoints (arXiv metadata)
  - `_fetch_arxiv_entry()` / `_fetch_arxiv_metadata()` in `doi2bib3/backend.py`
- `doi.org` (content negotiation for BibTeX)
  - `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`
- `api.crossref.org` (search, transform, article-number)
  - `_search_doi_via_crossref()` in `doi2bib3/backend.py`
  - `_fetch_bibtex_for_doi()` in `doi2bib3/backend.py`
  - `fetch_article_number_from_crossref()` in `doi2bib3/normalize.py`

If network access is blocked/unavailable, DOI/ISBN/arXiv/title lookups will fail with an error.
