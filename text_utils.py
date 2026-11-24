"""Shared normalization; entity matching deliberately does not use fuzzy names."""
import re
import unicodedata
from html import unescape


def normalize(value):
    value = unicodedata.normalize("NFKD", unescape(value or "").casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", value, re.UNICODE))


def person_names(value):
    """Keep full names and expand catalog initials, e.g. Montgomery, L. M. (Lucy Maud)."""
    value = unescape(value or "").strip()
    base = re.sub(r"\s*\([^)]*\)", "", value).strip()
    names = [base]
    if "," in base:
        surname, given = base.split(",", 1)
        names.append(given.strip() + " " + surname.strip())
        expanded = re.search(r"\(([^)]+)\)", value)
        if expanded and re.fullmatch(r"[A-Z.\s]+", given.strip()):
            names.append(expanded.group(1) + " " + surname.strip())
    return list(dict.fromkeys(n for n in names if n))


def person_keys(value):
    return sorted({normalize(n) for n in person_names(value)} - {""})


def title_keys(value):
    base = re.sub(r"\s*\([^)]*#\s*\d+[^)]*\)\s*$", "", value or "")
    base = re.sub(r"\s*\((?:\d{4}\s+)?(?:novel|book|novella|short story|poem|play|writer|author|poet|novelist)(?:\s+by\s+[^)]+)?\)\s*$", "", base, flags=re.I)
    return sorted({normalize(value), normalize(base)} - {""})
