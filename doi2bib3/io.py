# Copyright (c) 2025 Archisman Panigrahi <apandada1ATgmail.com>

"""IO helpers for BibTeX output."""

import os


def save_bibtex_to_file(bib_str: str, path: str, append: bool = False) -> None:
    if not append:
        with open(path, "w", encoding="utf-8") as f:
            f.write(bib_str)
        return

    prefix = ""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                last = fh.read(1)
            if last != b"\n":
                prefix = "\n"
    except OSError:
        prefix = "\n"

    with open(path, "a", encoding="utf-8") as f:
        if prefix:
            f.write(prefix)
        f.write(bib_str)
