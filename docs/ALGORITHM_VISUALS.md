# doi2bib3 Algorithm Visuals

Simple visual diagrams for `docs/ALGORITHM.md`.

GitHub renders Mermaid blocks directly. If your editor does not, open this file on GitHub or paste blocks into https://mermaid.live.

## 1) End-to-End Flow

```mermaid
flowchart TD
    A[Input identifier] --> B{CLI or Python API?}
    B -->|CLI| C[scripts/doi2bib3::main]
    B -->|API| D[doi2bib3.fetch_bibtex]
    C --> D
    D --> E[_resolve_identifier_to_doi]
    E --> F[_fetch_bibtex_for_doi]
    F --> G[normalize_bibtex]
    G --> H{Caller}
    H -->|CLI stdout| I[Print BibTeX]
    H -->|CLI -o| J[save_bibtex_to_file append=True]
    H -->|Python| K[Return string]
```

## 2) Identifier Resolution Decision Tree

```mermaid
flowchart TD
    A[identifier] --> B{Looks like arXiv?}
    B -->|Yes| C[_parse_arxiv_id_string]
    C --> D[_resolve_doi_from_arxiv_id via export.arxiv.org]
    D --> E{DOI found in arXiv metadata?}
    E -->|Yes| F[_parse_doi_string]
    E -->|No| G[Try 10.48550/arXiv.<id_without_version>]
    G --> F

    B -->|No| H[_parse_doi_string]
    H --> I{Valid DOI?}
    I -->|Yes| Z[Resolved DOI]
    I -->|No| J[_search_doi_via_crossref]

    J --> K{Input is URL?}
    K -->|Yes| L[_extract_doi_from_publisher_url]
    L --> M{DOI found in path/html?}
    M -->|Yes| N[_first_valid_doi]
    M -->|No| O[Crossref works query rows=5]
    K -->|No| O
    O --> P[Pick best candidate URL netloc match or top score]
    P --> Q[_parse_doi_string]
    N --> Q
    F --> Z
    Q --> Z
```

## 3) DOI to BibTeX Fetch (with fallback)

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

## 4) Normalization Pipeline

```mermaid
flowchart TD
    A[Raw BibTeX] --> B[bibtexparser.loads]
    B --> C[Recompute citation key Lastname_firstword_year]
    C --> D[Normalize pages n/a removal and dash normalization]
    D --> E{APS publisher and pages missing?}
    E -->|Yes| F[fetch_article_number_from_crossref]
    E -->|No| G[Continue]
    F --> G
    G --> H[If url exists decode url and drop doi field]
    H --> I[Title transforms insert_dollars and protect capitals]
    I --> J[Journal abbreviation mapping]
    J --> K[Month brace cleanup]
    K --> L[Special char to LaTeX encoding]
    L --> M[bibtexparser.dumps]
    M --> N[Normalized BibTeX]
```

## 5) Function Map (Quick Reference)

- CLI entry: `scripts/doi2bib3` -> `build_parser()`, `main()`
- Public API: `doi2bib3/backend.py` -> `fetch_bibtex()`
- Resolve identifier: `doi2bib3/backend.py` -> `_resolve_identifier_to_doi()`
- arXiv parse/query: `doi2bib3/backend.py` -> `_parse_arxiv_id_string()`, `_resolve_doi_from_arxiv_id()`
- Crossref search: `doi2bib3/backend.py` -> `_search_doi_via_crossref()`
- URL DOI extraction: `doi2bib3/backend.py` -> `_extract_doi_from_publisher_url()`
- Fetch raw BibTeX: `doi2bib3/backend.py` -> `_fetch_bibtex_for_doi()`
- Normalize BibTeX: `doi2bib3/normalize.py` -> `normalize_bibtex()`
- Write output file: `doi2bib3/io.py` -> `save_bibtex_to_file()`
