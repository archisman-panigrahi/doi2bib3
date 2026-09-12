"""Efficient compatibility helpers for bibtexparser 1.x and 2.x.

bibtexparser 2 replaced the dict-based ``BibDatabase`` API with ``Library``
and ``Entry`` objects.  The rest of doi2bib3 deliberately continues to work
with plain dictionaries so its normalization code is independent of the
installed bibtexparser major version.
"""

from typing import Dict, List

import bibtexparser


BibtexEntry = Dict[str, str]
_ENTRY_METADATA_KEYS = frozenset(("ENTRYTYPE", "ID"))


if hasattr(bibtexparser, "parse_string"):
    from bibtexparser.library import Library
    from bibtexparser.middlewares import (
        AddEnclosingMiddleware,
        RemoveEnclosingMiddleware,
        ResolveStringReferencesMiddleware,
    )
    from bibtexparser.middlewares.names import parse_single_name_into_parts
    from bibtexparser.model import Entry, Field
    from bibtexparser.writer import BibtexFormat

    # These middleware instances are stateless. Reusing them avoids rebuilding
    # the default stacks for every entry fetched by the CLI.
    _PARSE_STACK = (
        ResolveStringReferencesMiddleware(allow_inplace_modification=True),
        RemoveEnclosingMiddleware(allow_inplace_modification=True),
    )
    _UNPARSE_STACK = (
        AddEnclosingMiddleware(
            allow_inplace_modification=True,
            default_enclosing="{",
            reuse_previous_enclosing=False,
            enclose_integers=True,
        ),
    )

    _BIBTEX_FORMAT = BibtexFormat()
    # Match bibtexparser 1.x's default layout to keep CLI output stable.
    _BIBTEX_FORMAT.indent = " "
    _BIBTEX_FORMAT.block_separator = "\n"

    def parse_entries(bibtex: str) -> List[BibtexEntry]:
        """Parse *bibtex* and return v1-style entry dictionaries."""
        library = bibtexparser.parse_string(bibtex, parse_stack=_PARSE_STACK)
        entries = []
        for parsed_entry in library.entries:
            entry = {
                "ENTRYTYPE": parsed_entry.entry_type,
                "ID": parsed_entry.key,
            }
            # v1 lowercases field names. Do that while converting instead of
            # running v2's separate NormalizeFieldKeys middleware traversal.
            entry.update(
                (field.key.lower(), field.value) for field in parsed_entry.fields
            )
            entries.append(entry)
        return entries

    def dump_entries(entries: List[BibtexEntry]) -> str:
        """Serialize v1-style entry dictionaries as BibTeX."""
        blocks = [
            Entry(
                source["ENTRYTYPE"],
                source["ID"],
                [
                    Field(key, source[key])
                    for key in sorted(source)
                    if key not in _ENTRY_METADATA_KEYS
                ],
            )
            for source in entries
        ]
        # The library is temporary, so in-place enclosing avoids a deep copy.
        return bibtexparser.write_string(
            Library(blocks),
            unparse_stack=_UNPARSE_STACK,
            bibtex_format=_BIBTEX_FORMAT,
        )

    def split_name(name: str) -> Dict[str, List[str]]:
        """Return BibTeX name parts as a v1-style dictionary."""
        parts = parse_single_name_into_parts(name, strict=False)
        return {
            "first": parts.first,
            "von": parts.von,
            "last": parts.last,
            "jr": parts.jr,
        }

else:
    from bibtexparser.bibdatabase import BibDatabase
    from bibtexparser.bparser import BibTexParser
    from bibtexparser.customization import splitname

    def parse_entries(bibtex: str) -> List[BibtexEntry]:
        """Parse *bibtex* and return v1-style entry dictionaries."""
        parser = BibTexParser(common_strings=False)
        return bibtexparser.loads(bibtex, parser=parser).entries

    def dump_entries(entries: List[BibtexEntry]) -> str:
        """Serialize v1-style entry dictionaries as BibTeX."""
        database = BibDatabase()
        database.entries = entries
        return bibtexparser.dumps(database)

    def split_name(name: str) -> Dict[str, List[str]]:
        """Return BibTeX name parts as a v1-style dictionary."""
        return splitname(name, strict_mode=False)
