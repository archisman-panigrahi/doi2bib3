# Copyright (c) 2025 Archisman Panigrahi <apandada1ATgmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""BibTeX normalization helpers."""

from typing import Optional
import html
import json
import unicodedata
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET

import bibtexparser
from bibtexparser.bparser import BibTexParser
import requests

from .constants import USER_AGENT

LATEX_DIACRITIC_COMMANDS = {
    "\u0300": "\\`",
    "\u0301": "\\'",
    "\u0302": "\\^",
    "\u0303": "\\~",
    "\u0304": "\\=",
    "\u0306": "\\u",
    "\u0307": "\\.",
    "\u0308": "\\\"",
    "\u030a": "\\r",
    "\u030b": "\\H",
    "\u030c": "\\v",
    "\u0327": "\\c",
    "\u0328": "\\k",
    "\u0331": "\\b",
}

SPECIAL_CHARS = {
    "\u00ae": "{\\textregistered}",
    "\u00df": "{\\ss}",
    "\u00d0": "{\\DH}",
    "\u00f0": "{\\dh}",
    "\u00de": "{\\TH}",
    "\u00fe": "{\\th}",
    "\u0141": "{\\L}",
    "\u0142": "{\\l}",
    "\u0152": "{\\OE}",
    "\u0153": "{\\oe}",
    "\u00c6": "{\\AE}",
    "\u00e6": "{\\ae}",
    "\u00d8": "{\\O}",
    "\u00f8": "{\\o}",
    "\u0110": "{\\DJ}",
    "\u0111": "{\\dj}",
    "\u0131": "{\\i}",
    "\u0237": "{\\j}",
}

_TEXT_FIELDS_LATEX_ENCODING = {"author", "booktitle", "title"}

_MONTH_STRING_DEFINITIONS = """@string{jan = \"January\"}
@string{january = \"January\"}
@string{feb = \"February\"}
@string{february = \"February\"}
@string{mar = \"March\"}
@string{march = \"March\"}
@string{apr = \"April\"}
@string{april = \"April\"}
@string{may = \"May\"}
@string{jun = \"June\"}
@string{june = \"June\"}
@string{jul = \"July\"}
@string{july = \"July\"}
@string{aug = \"August\"}
@string{august = \"August\"}
@string{sep = \"September\"}
@string{sept = \"September\"}
@string{september = \"September\"}
@string{oct = \"October\"}
@string{october = \"October\"}
@string{nov = \"November\"}
@string{november = \"November\"}
@string{dec = \"December\"}
@string{december = \"December\"}
"""

VAR_RE = re.compile(r"(\\{)(\\var[A-Z]?[a-z]*)(\\})")

ASCII_BIBTEX_KEY_CHARS = str.maketrans(
    {
        "ß": "ss",
        "Ð": "D",
        "ð": "d",
        "Þ": "Th",
        "þ": "th",
        "Ł": "L",
        "ł": "l",
        "Œ": "OE",
        "œ": "oe",
        "Æ": "AE",
        "æ": "ae",
        "Ø": "O",
        "ø": "o",
        "Đ": "D",
        "đ": "d",
        "ı": "i",
        "ȷ": "j",
    }
)

GREEK_LATEX = {
    char: f"\\{name}"
    for char, name in zip(
        "αβγδεζηθικλμνξπρστυφχψω",
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi pi rho sigma tau upsilon phi chi psi omega".split(),
    )
}
GREEK_LATEX.update(
    {
        "Γ": "\\Gamma",
        "Δ": "\\Delta",
        "Θ": "\\Theta",
        "Λ": "\\Lambda",
        "Ξ": "\\Xi",
        "Π": "\\Pi",
        "Σ": "\\Sigma",
        "Υ": "\\Upsilon",
        "Φ": "\\Phi",
        "Ψ": "\\Psi",
        "Ω": "\\Omega",
    }
)

MATHML_RE = re.compile(
    r"<(?P<prefix>[A-Za-z_][\w.-]*:)?math\b.*?</(?P=prefix)math>",
    flags=re.DOTALL | re.IGNORECASE,
)
ELEMENT = r"[A-Z][a-z]?"
MIXED_SITE_GROUP = rf"\({ELEMENT}(?:,{ELEMENT})+\)"
CHEMICAL_FORMULA_RE = re.compile(
    rf"(?<![A-Za-z\\])(?P<formula>(?:{MIXED_SITE_GROUP}|{ELEMENT})"
    rf"(?:\d+(?:\.\d+)?|{MIXED_SITE_GROUP}|{ELEMENT}|[+\-−]|[δδε])+)(?![a-z])"
)
FORMULA_TOKEN_RE = re.compile(
    rf"{MIXED_SITE_GROUP}|{ELEMENT}|\d+(?:\.\d+)?(?:[+\-−][δδε])?|[δδε]|[+\-−]"
)
ELEMENT_RE = re.compile(ELEMENT)


def _load_journal_replacements():
    """Load journal name replacement dictionaries from JSON files."""
    replacements = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))

    for json_file in [
        "APS_replacement.json",
        "Nature_replacement.json",
        "IOP_replacement.json",
    ]:
        file_path = os.path.join(current_dir, json_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                replacements.update(data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return replacements


_JOURNAL_REPLACEMENTS = _load_journal_replacements()


def abbreviate_journal_name(journal: str) -> str:
    """Replace journal name with its abbreviation if found in replacement dicts."""
    if not journal:
        return journal

    if journal in _JOURNAL_REPLACEMENTS:
        return _JOURNAL_REPLACEMENTS[journal]

    for full_name, abbrev in _JOURNAL_REPLACEMENTS.items():
        if full_name.lower() == journal.lower():
            return abbrev

    return journal


def escape_latex_chars(value: str, chars: str) -> str:
    value = html.unescape(value)
    return re.sub(rf"(?<!\\)([{re.escape(chars)}])", r"\\\1", value)


def insert_dollars(title: str) -> str:
    return VAR_RE.sub(r"\\1$\\2$\\3", title)


def protect_capitalized_words(title: str) -> str:
    """Wrap capitalized words in curly braces for BibTeX title protection."""
    result = []
    i = 0
    while i < len(title):
        if title[i] == "{":
            brace_count = 1
            j = i + 1
            while j < len(title) and brace_count > 0:
                if title[j] == "{":
                    brace_count += 1
                elif title[j] == "}":
                    brace_count -= 1
                j += 1
            result.append(title[i:j])
            i = j
        elif title[i].isupper():
            j = i
            while j < len(title) and (title[j].isalnum() or title[j] == "-"):
                j += 1
            word = title[i:j]
            result.append("{" + word + "}")
            i = j
        else:
            result.append(title[i])
            i += 1

    return "".join(result)


def encode_special_chars(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    encoded = []
    for char in value:
        special_char = SPECIAL_CHARS.get(char)
        if special_char:
            encoded.append(special_char)
            continue

        if ord(char) < 128:
            encoded.append(char)
            continue

        normalized = unicodedata.normalize("NFD", char)
        if len(normalized) == 1:
            encoded.append(char)
            continue

        base = normalized[0]
        marks = normalized[1:]
        if not base.isalpha() or not all(mark in LATEX_DIACRITIC_COMMANDS for mark in marks):
            encoded.append(char)
            continue

        letter = base
        for mark in marks:
            letter = f"{LATEX_DIACRITIC_COMMANDS[mark]}{{{letter}}}"
        encoded.append(letter)

    return "".join(encoded)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag.rsplit(":", 1)[-1]


def _latex_escape(text: str) -> str:
    special = {
        "\\": r"\backslash{}",
        "{": r"\{",
        "}": r"\}",
        "_": r"\_",
        "^": r"\^{}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "$": r"\$",
    }
    return "".join(special.get(char, char) for char in text)


def _math_char_to_latex(char: str) -> str:
    return GREEK_LATEX.get(char, "-" if char == "−" else _latex_escape(char))


def _mathml_element_to_latex(element: ET.Element) -> str:
    tag = _local_name(element.tag)
    children = list(element)
    text = "".join(element.itertext()).strip().strip("{}")

    if tag == "math":
        return "$" + "".join(_mathml_element_to_latex(child) for child in children) + "$"
    if tag == "mrow" or (children and tag not in {"msub", "msup", "msubsup"}):
        return "".join(_mathml_element_to_latex(child) for child in children)
    if tag == "mi":
        return GREEK_LATEX.get(
            text,
            r"\mathrm{" + text + "}"
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]+", text)
            else _latex_escape(text),
        )
    if tag in {"mn", "mo"}:
        return _latex_escape(text.replace("−", "-"))
    if tag == "mtext":
        if text in {"−", "-", "‐", "‑", "‒", "–", "—"}:
            return r"\text{-}"
        return r"\text{" + _latex_escape(text) + "}"
    if tag in {"msub", "msup"} and len(children) >= 2:
        op = "_" if tag == "msub" else "^"
        base = _mathml_element_to_latex(children[0])
        script = _mathml_element_to_latex(children[1])
        return "{" + base + "}" + op + "{" + script + "}"
    if tag == "msubsup" and len(children) >= 3:
        base, subscript, superscript = (
            _mathml_element_to_latex(child) for child in children[:3]
        )
        return "{" + base + "}_{" + subscript + "}^{" + superscript + "}"
    return _latex_escape(text)


def _plain_mathml_to_latex(mathml: str) -> str:
    text = re.sub(r"<[^>]+>", "", mathml)
    text = re.sub(r"\s+", " ", text).strip()
    return "$" + "".join(_math_char_to_latex(char) for char in text) + "$"


def _convert_mathml_match(match: re.Match) -> str:
    mathml = match.group(0)
    xml = mathml.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return _plain_mathml_to_latex(mathml)
    return _mathml_element_to_latex(root)


def mathml_to_latex(value: str) -> str:
    return MATHML_RE.sub(_convert_mathml_match, value)


def _formula_token_to_latex(token: str) -> str:
    if re.fullmatch(MIXED_SITE_GROUP, token):
        elements = token[1:-1].split(",")
        return "(" + ",".join(r"\mathrm{" + element + "}" for element in elements) + ")"
    if ELEMENT_RE.fullmatch(token):
        return r"\mathrm{" + token + "}"
    if token[0].isdigit():
        subscript = "".join(_math_char_to_latex(char) for char in token)
        return "_{" + subscript + "}"
    return GREEK_LATEX.get(token, "-" if token == "−" else token)


def _chemical_formula_to_latex(formula: str) -> str:
    latex = "".join(
        _formula_token_to_latex(match.group(0))
        for match in FORMULA_TOKEN_RE.finditer(formula)
    )
    return "$" + latex + "$"


def _convert_chemical_formula_match(match: re.Match) -> str:
    formula = match.group("formula")
    has_subscript_marker = re.search(r"\d", formula) or any(
        char in GREEK_LATEX for char in formula
    )
    if not (ELEMENT_RE.search(formula) and has_subscript_marker):
        return formula
    return _chemical_formula_to_latex(formula)


def chemical_formulas_to_latex(value: str) -> str:
    parts = re.split(r"(\$[^$]*\$)", value)
    for idx in range(0, len(parts), 2):
        parts[idx] = CHEMICAL_FORMULA_RE.sub(_convert_chemical_formula_match, parts[idx])
    return "".join(parts)


def plus_minus_to_latex(value: str) -> str:
    if "+-" not in value and "±" not in value:
        return value

    parts = re.split(r"(\$[^$]*\$)", value)
    for idx, part in enumerate(parts):
        replacement = r"\pm" if idx % 2 else r"$\pm$"
        parts[idx] = part.replace("+-", replacement).replace("±", replacement)
    return "".join(parts)


def ensure_space_around_math(title: str) -> str:
    """Separate inline math from neighboring title text."""
    def _space_math_match(match: re.Match) -> str:
        start, end = match.span()
        before = title[start - 1] if start else ""
        after = title[end] if end < len(title) else ""
        prefix = " " if before and not before.isspace() and before not in "([{" else ""
        suffix = (
            " "
            if after and after != "$" and not after.isspace() and after not in ".,;:!?)]}"
            else ""
        )
        return prefix + match.group(0) + suffix

    return re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", _space_math_match, title)


def ascii_for_bibtex_key(value: str) -> str:
    value = unicodedata.normalize("NFD", value.translate(ASCII_BIBTEX_KEY_CHARS))
    return "".join(char for char in value if not unicodedata.combining(char))


def fetch_article_number_from_crossref(doi: str, timeout: int = 10) -> Optional[str]:
    """Fetch article-number from Crossref API for a given DOI."""
    try:
        doi_clean = doi.strip()
        if doi_clean.lower().startswith("doi:"):
            doi_clean = doi_clean[4:].strip()

        url = f'https://api.crossref.org/works/{urllib.parse.quote(doi_clean, safe="")}'
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)

        if resp.status_code == 200:
            data = resp.json()
            message = data.get("message", {})
            return message.get("article-number")
    except Exception:
        pass

    return None


def normalize_bibtex(
    bib_str: str,
    arxiv_id: Optional[str] = None,
    primary_class: Optional[str] = None,
    include_arxiv_fields: bool = False,
) -> str:
    # Some providers return month macros like month=july without defining
    # them, which makes bibtexparser raise UndefinedString.
    parser = BibTexParser(common_strings=False)
    bib_db = bibtexparser.loads(
        _MONTH_STRING_DEFINITIONS + "\n" + bib_str,
        parser=parser,
    )
    # Keep resolved values in entries while omitting helper @string blocks.
    bib_db.strings = {}
    for entry in bib_db.entries:
        if "ID" in entry:
            entry["ID"] = entry["ID"].replace("_", "")

    def _make_bibtex_key(entry):
        def _clean(s, lower=True):
            if not s:
                return ""
            s = ascii_for_bibtex_key(s)
            s = s.strip()
            s = re.sub(r'^[{\"\']+|[}\"\']+$', "", s)
            if lower:
                s = s.lower()
                s = re.sub(r"[^a-z0-9\-]+", "", s)
            else:
                s = re.sub(r"[^A-Za-z0-9\-]+", "", s)
            return s

        auth = entry.get("author", "")
        firstname_lastname = ""
        if auth:
            first_author = auth.split(" and ")[0].strip()
            if "," in first_author:
                lastname = first_author.split(",", 1)[0].strip()
            else:
                parts = first_author.split()
                lastname = parts[-1] if parts else ""
            firstname_lastname = _clean(lastname, lower=False)

        title = entry.get("title", "")
        firstword = ""
        if title:
            t = re.sub(r"[{}]", "", title)
            tw = re.split(r"\s+", t.strip())
            if tw:
                firstword = _clean(tw[0])

        year = _clean(entry.get("year", ""))

        base = "_".join(p for p in (firstname_lastname, firstword, year) if p)
        if not base:
            base = _clean(entry.get("ID", "entry")) or "entry"

        return base

    for entry in bib_db.entries:
        new_id = _make_bibtex_key(entry)
        entry["ID"] = new_id
        pages = entry.get("pages")
        if pages:
            norm = pages.strip().lower()
            if norm in ("n/a-n/a", "na-na", "n/a", "na"):
                entry.pop("pages", None)
            else:
                p = pages
                p = p.replace("\u2013", "--").replace("\u2014", "--")
                p = p.replace("–", "--").replace("—", "--")
                p = re.sub(r"(?<=\d)\s*-[\u2013\u2014-]?\s*(?=\d)", "--", p)
                entry["pages"] = p

        if not pages:
            doi = entry.get("doi", "").strip()
            if doi:
                article_num = fetch_article_number_from_crossref(doi)
                if article_num:
                    entry["pages"] = article_num

        if "url" in entry:
            entry["url"] = urllib.parse.unquote(entry["url"])
            entry.pop("doi", None)

        if "title" in entry:
            entry["title"] = unicodedata.normalize("NFC", entry["title"])
            entry["title"] = mathml_to_latex(entry["title"])
            entry["title"] = insert_dollars(entry["title"])
            entry["title"] = plus_minus_to_latex(entry["title"])
            entry["title"] = chemical_formulas_to_latex(entry["title"])
            entry["title"] = ensure_space_around_math(entry["title"])
            entry["title"] = escape_latex_chars(entry["title"], "&%#")
            entry["title"] = protect_capitalized_words(entry["title"])

        if "journal" in entry:
            entry["journal"] = abbreviate_journal_name(entry["journal"])
            entry["journal"] = escape_latex_chars(entry["journal"], "&")

        if "month" in entry:
            entry["month"] = entry["month"].strip()
            if entry["month"].startswith("{") and entry["month"].endswith("}"):
                entry["month"] = entry["month"][1:-1]

        if include_arxiv_fields and arxiv_id:
            entry["archivePrefix"] = "arXiv"
            entry["eprint"] = arxiv_id
            if primary_class:
                entry["primaryClass"] = primary_class

        for key in _TEXT_FIELDS_LATEX_ENCODING:
            if key in entry:
                entry[key] = encode_special_chars(entry[key])

    return bibtexparser.dumps(bib_db)
