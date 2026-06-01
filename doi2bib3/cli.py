"""Command-line interface for ``doi2bib3``.

Two subcommands:

* ``doi2bib3 fetch <identifier> [-o FILE]`` -- the historical behaviour:
  resolve a DOI / arXiv id / URL / title and emit the BibTeX.
* ``doi2bib3 verify <path> [--json]`` -- check a ``.bib`` file (or a folder
  that contains ``.bib`` / ``.tex`` files) against authoritative databases
  and report unverifiable, mismatched or unresolved references.

For backward compatibility, ``doi2bib3 <identifier>`` (with no recognised
subcommand) is treated as ``doi2bib3 fetch <identifier>``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backend import fetch_bibtex
from .io import save_bibtex_to_file
from .verify import (
    STATUS_ICON,
    VERIFIED,
    check_cite_keys,
    parse_bibtex,
    summary,
    verify_entries,
)

_SUBCOMMANDS = ("fetch", "verify")
_HELP_FLAGS = ("-h", "--help", "help", "-V", "--version")


def main(argv: list[str] | None = None) -> int:
    """Run the doi2bib3 CLI.

    Returns a process exit code:
    ``0`` on success, ``1`` on a runtime/network error, ``2`` when verify
    surfaces references that need attention or undefined cite keys.
    """
    # Keep output crash-free when a reference title contains characters the
    # console encoding cannot represent (common on Windows code pages).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    argv = list(sys.argv[1:] if argv is None else argv)

    # Legacy form: ``doi2bib3 10.1038/...`` (no subcommand) -> treat as ``fetch``.
    if argv and argv[0] not in _SUBCOMMANDS and argv[0] not in _HELP_FLAGS:
        argv = ["fetch", *argv]

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "fetch":
        return _cmd_fetch(args)
    if args.command == "verify":
        return _cmd_verify(args)
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doi2bib3",
        description=(
            "Fetch BibTeX from a DOI/arXiv id/URL/title, "
            "or verify references against CrossRef/arXiv."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_fetch = sub.add_parser(
        "fetch",
        help="Fetch BibTeX for a single identifier (DOI, arXiv id, URL, title).",
        description=(
            "Resolve an identifier to a DOI and emit the normalized BibTeX entry."
        ),
    )
    p_fetch.add_argument(
        "identifier",
        nargs="?",
        help="DOI, DOI URL, arXiv id/URL, publisher URL, or article title.",
    )
    p_fetch.add_argument("-o", "--out", help="Write .bib file to this path (append).")

    p_verify = sub.add_parser(
        "verify",
        help="Verify BibTeX references against authoritative databases.",
        description=(
            "Check every entry in a .bib file (or folder of .bib/.tex files) "
            "against CrossRef, arXiv and the DOI registry."
        ),
    )
    p_verify.add_argument(
        "source",
        nargs="?",
        help="Path to a .bib file or a folder containing .bib/.tex files.",
    )
    p_verify.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent lookups (default: 4).",
    )
    p_verify.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Per-request timeout in seconds.",
    )
    p_verify.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text report.",
    )

    return parser


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------

def _cmd_fetch(args) -> int:
    if not args.identifier:
        print(
            "doi2bib3 fetch: provide a DOI, arXiv id, URL, or article title.",
            file=sys.stderr,
        )
        return 2
    try:
        bib = fetch_bibtex(args.identifier)
    except Exception as exc:  # noqa: BLE001 - surface any backend error
        print("Error:", exc, file=sys.stderr)
        return 1

    if args.out:
        save_bibtex_to_file(bib, args.out, append=True)
        print("Wrote", args.out)
    else:
        print(bib)
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def _cmd_verify(args) -> int:
    if not args.source:
        print(
            "doi2bib3 verify: provide a .bib file or a folder.",
            file=sys.stderr,
        )
        return 2

    try:
        entries, tex_sources, label = _collect(Path(args.source))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not entries:
        print(f"No BibTeX entries found in {label}.", file=sys.stderr)
        return 1

    show_progress = not args.json
    results = verify_entries(
        entries,
        timeout=args.timeout,
        max_workers=args.workers,
        progress=_progress if show_progress else None,
    )
    if show_progress:
        print("", file=sys.stderr)

    cite = None
    if tex_sources:
        cite = check_cite_keys(tex_sources, {e.key for e in entries if e.key})

    if args.json:
        _print_json(label, results, cite)
    else:
        _print_report(label, results, cite)

    flagged = any(r.needs_attention for r in results)
    bad_keys = bool(cite and cite.undefined)
    return 1 if (flagged or bad_keys) else 0


def _collect(path: Path) -> tuple[list, list[str], str]:
    """Read a .bib file, a .tex file, or a folder containing both."""
    entries: list = []
    tex_sources: list[str] = []

    if not path.exists():
        raise OSError(f"No such file or folder: {path}")

    if path.is_dir():
        for bib in sorted(path.rglob("*.bib")):
            entries += parse_bibtex(_read(bib))
        tex_sources = [_read(t) for t in sorted(path.rglob("*.tex"))]
        return entries, tex_sources, str(path)

    text = _read(path)
    if path.suffix.lower() == ".tex":
        tex_sources.append(text)
    else:
        entries = parse_bibtex(text)
    return entries, tex_sources, str(path)


def _read(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _progress(done: int, total: int) -> None:
    print(f"\rVerifying references... {done}/{total}", end="", file=sys.stderr)


def _print_report(label: str, results: list, cite) -> None:
    counts = summary(results)
    print("doi2bib3 reference verifier")
    print(f"Source: {label}")
    print(
        f"Checked {counts['total']} references - "
        f"{counts['verified']} verified, {counts['review']} review, "
        f"{counts['mismatch']} mismatch, {counts['not_found']} unresolved, "
        f"{counts['unverified'] + counts['error']} unverified"
    )
    print()

    flagged = [r for r in results if r.status != VERIFIED]
    if not flagged:
        print("  [OK] All references verified against CrossRef / arXiv.")
    for r in flagged:
        print(f"  [{STATUS_ICON.get(r.status, r.status)}] {r.key}")
        if r.title:
            print(f"      title : {r.title}")
        print(f"      {r.reason}")
        for issue in r.issues:
            print(f"      - {issue}")
        print()

    if cite is not None:
        print(f"Cite-key check: {len(cite.cited)} cited, {len(cite.defined)} defined")
        if cite.undefined:
            print(
                "  Cited but NOT defined in any .bib (possibly invented keys): "
                + ", ".join(sorted(cite.undefined))
            )
        if cite.unused:
            print("  Defined but never cited: " + ", ".join(sorted(cite.unused)))
        if not cite.undefined and not cite.unused:
            print("  [OK] Every cited key is defined.")


def _print_json(label: str, results: list, cite) -> None:
    payload = {
        "source": label,
        "summary": summary(results),
        "results": [r.to_dict() for r in results],
    }
    if cite is not None:
        payload["citeCheck"] = cite.to_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
