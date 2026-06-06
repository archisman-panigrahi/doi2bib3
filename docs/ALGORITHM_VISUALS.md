# doi2bib3 Algorithm Visuals

Simple visual diagrams for `docs/ALGORITHM.md`.

## 1) End-to-End Flow

```mermaid
flowchart TD
    A[Input identifier] --> B{CLI or Python API?}
    B -->|CLI| C[scripts/doi2bib3::main]
    B -->|API| D[doi2bib3.fetch_bibtex]
    C --> D
    D --> E{Valid ISBN?}
    E -->|Yes| IB[_fetch_bibtex_for_isbn via book metadata APIs]
    E -->|No| R[_resolve_identifier]
    R --> F[_fetch_bibtex_for_doi]
    IB --> G[normalize_bibtex]
    F --> G
    G --> H{Caller}
    H -->|CLI stdout| I[Print BibTeX]
    H -->|CLI -o| J[save_bibtex_to_file append=True]
    H -->|Python| K[Return string]
    I --> L{--bibitem?}
    J --> L
    L -->|Yes| M[format_bibtex_to_aps_bibitem]
    L -->|No| N[Done]
    M --> O[Print bibitem or warning]
```

## 2) Identifier Resolution Decision Tree

```mermaid
flowchart TD
    A[identifier] --> AA{Valid ISBN-10/13?}
    AA -->|Yes| AB[Open Library book query]
    AB --> AE{Found?}
    AE -->|No| AF[Google Books volume query]
    AE -->|Yes| AC[Construct @book]
    AF --> AC
    AC --> ZB[Raw BibTeX for normalization]

    AA -->|No| B{Looks like arXiv?}
    B -->|Yes| C[_parse_arxiv_id_string]
    C --> D[_fetch_arxiv_metadata via arXiv API fallback list]
    D --> E{Published DOI found in arXiv metadata?}
    E -->|Yes| F[_parse_doi_string]
    E -->|No| G[Try 10.48550/arXiv.<id_without_version>]
    G --> F

    B -->|No| H{Looks like arXiv DOI?}
    H -->|Yes| I[_parse_arxiv_id_from_doi_string]
    I --> J[_fetch_arxiv_metadata for enrichment]
    J --> Z[Resolved DOI plus optional arXiv metadata]

    H -->|No| K[_parse_doi_string]
    K --> L{Valid DOI?}
    L -->|Yes| Z
    L -->|No| M[_search_doi_via_crossref]

    M --> N{Input is URL?}
    N -->|Yes| O[_extract_doi_from_publisher_url]
    O --> W{IOP /pdf or SciPost article path?}
    W -->|Yes| X[Strip view suffix or map SciPost path to DOI]
    W -->|No| U{ScienceDirect PII URL?}
    X --> P
    U -->|Yes| V[Query Elsevier article metadata]
    U -->|No| P{DOI found in path/html?}
    V --> P
    P -->|Yes| Q[_first_valid_doi]
    P -->|No| R[Crossref works query rows=5]
    N -->|No| R
    R --> S[Pick best candidate URL netloc match or top score]
    S --> T[_parse_doi_string]
    Q --> T
    F --> Z
    T --> Z
```

## 3) ISBN to BibTeX Fetch

```mermaid
flowchart TD
    A[ISBN input] --> B[_parse_isbn_string]
    B --> C{Checksum valid?}
    C -->|No| D[Continue non-ISBN resolver]
    C -->|Yes| E[GET Open Library api/books]
    E --> F{Book with title?}
    F -->|No| O[GET Google Books volumes?q=isbn:<isbn>]
    O --> P{Volume with title?}
    P -->|No| G[Raise DOIError]
    F -->|Yes| H[Build @book fields]
    P -->|Yes| H
    H --> I[Raw BibTeX]
```

## 4) DOI to BibTeX Fetch (with fallback)

```mermaid
flowchart TD
    A[DOI] --> B[GET doi.org with Accept: application/x-bibtex]
    B --> C{HTTP 200?}
    C -->|Yes| D[_decode_response_text]
    C -->|No| E[GET Crossref transform endpoint]
    E --> F{HTTP 200?}
    F -->|Yes| D
    F -->|No| G[Raise DOIError with both status codes]
    D --> H[Raw BibTeX]
```

## 5) Normalization Pipeline

```mermaid
flowchart TD
    A[Raw BibTeX] --> B[bibtexparser.loads]
    B --> C[Recompute citation key Lastname_firstword_year]
    C --> D[Normalize pages n/a removal and dash normalization]
    D --> E{Pages missing and DOI present?}
    E -->|Yes| F[fetch_article_number_from_crossref]
    E -->|No| G[Continue]
    F --> G
    G --> H[If url exists decode url and drop doi field]
    H --> I{Unpublished arXiv enrichment enabled?}
    I -->|Yes| J[Add archivePrefix eprint and optional primaryClass]
    I -->|No| K[Continue]
    J --> K
    K --> L[Title NFC normalization]
    L --> M[Convert inline MathML to LaTeX math]
    M --> N[Convert HTML italics to LaTeX textit]
    N --> O[Insert dollar math and normalize plus/minus]
    O --> P[Convert plain chemical formulas to LaTeX math]
    P --> Q[Space inline math and escape title specials]
    Q --> R[Collapse title whitespace and protect capitals]
    R --> U[Journal abbreviation and ampersand escaping]
    U --> V[Month brace cleanup]
    V --> W[Special char to LaTeX encoding]
    W --> X[bibtexparser.dumps]
    X --> Y[Normalized BibTeX]
```

## 6) Function Map (Quick Reference)

- CLI entry: `scripts/doi2bib3` -> `build_parser()`, `main()`
- Public API: `doi2bib3/backend.py` -> `fetch_bibtex()`
- ISBN parse/query: `doi2bib3/backend.py` -> `_parse_isbn_string()`, `_fetch_bibtex_for_isbn()`
- Resolve identifier: `doi2bib3/backend.py` -> `_resolve_identifier()`, `_resolve_identifier_to_doi()`
- arXiv parse/query: `doi2bib3/backend.py` -> `_parse_arxiv_id_string()`, `_parse_arxiv_id_from_doi_string()`, `_fetch_arxiv_metadata()`, `_resolve_arxiv_identifier()`
- Crossref search: `doi2bib3/backend.py` -> `_search_doi_via_crossref()`
- URL DOI extraction: `doi2bib3/backend.py` -> `_extract_doi_from_publisher_url()`, `_extract_doi_from_sciencedirect_url()`
- Fetch raw BibTeX: `doi2bib3/backend.py` -> `_fetch_bibtex_for_doi()`
- Normalize BibTeX: `doi2bib3/normalize.py` -> `normalize_bibtex()`
- Format APS/RevTeX bibitem: `doi2bib3/bibitem.py` -> `format_bibtex_to_aps_bibitem()`
- Write output file: `doi2bib3/io.py` -> `save_bibtex_to_file()`
