"""REGEX extraction from FadedPage HTML and Wikipedia page records.

The original extractor is retained in legacy/. New code fixes repeated people
rows and keeps editors separate. No DOM, XML or wikitext parser is used.
"""
import re
from html import unescape
from urllib.parse import quote
from legacy.extractor_os import extrahuj_knihu
from text_utils import normalize, person_keys, title_keys

FLAGS = re.I | re.S
LABEL_RE = re.compile(r"<tr\b[^>]*>\s*<td\b[^>]*>\s*([A-Za-z][A-Za-z ]*):(?:\s|&nbsp;|&#160;|&#xA0;)*</td>\s*<td\b[^>]*>", FLAGS)
LINK_RE = re.compile(r"<a\b[^>]*href\s*=\s*['\"][^'\"]*csearch\.php\?author=[^'\"]*['\"][^>]*>(.*?)</a>", FLAGS)


def clean_html(value):
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value or "")).split())


def extract_book(html, source_file=""):
    book = extrahuj_knihu(html, source_file=source_file)
    if not book:
        return None
    start = re.search(r"Book Details\s*</b>", html, FLAGS)
    end = re.search(r"<b[^>]*>\s*(?:Author Bio|Available Formats)", html[start.end():], FLAGS)
    details = html[start.end():start.end() + end.start()] if end else html[start.end():]
    labels = list(LABEL_RE.finditer(details))
    people = {"author": [], "editor": [], "illustrator": [], "translator": []}
    for i, match in enumerate(labels):
        role = match.group(1).strip().lower()
        if role not in people:
            continue
        block = details[match.end():labels[i + 1].start() if i + 1 < len(labels) else len(details)]
        names = [clean_html(n) for n in LINK_RE.findall(block)]
        if not names:
            names = [clean_html(block.split("</td>", 1)[0])]
        people[role].extend(n for n in names if n)
    for role in people:
        people[role] = list(dict.fromkeys(people[role]))
    book.update(authors=people["author"], editors=people["editor"],
                illustrators=people["illustrator"], translators=people["translator"])
    book["author"] = "; ".join(book["authors"])
    book["people"] = [{"name": name, "role": role} for role in ("author", "editor") for name in people[role]]
    book["title_keys"] = title_keys(book["title"])
    book["author_keys"] = sorted({k for name in book["authors"] + book["editors"] for k in person_keys(name)})
    return book


def split_top_level(value):
    """Split infobox arguments without splitting nested templates or wiki links."""
    braces = links = 0
    start = 0
    parts = []
    for match in re.finditer(r"\{\{|\}\}|\[\[|\]\]|\|", value):
        token = match.group()
        if token == "{{": braces += 1
        elif token == "}}": braces = max(0, braces - 1)
        elif token == "[[": links += 1
        elif token == "]]": links = max(0, links - 1)
        elif not braces and not links:
            parts.append(value[start:match.start()]); start = match.end()
    return parts + [value[start:]]


def infobox(text):
    match = re.search(r"\{\{\s*Infobox[ _]+([^|\n{}]+)", text, re.I)
    if not match:
        return "", {}
    depth = 1
    stop = None
    for token in re.finditer(r"\{\{|\}\}", text[match.end():]):
        depth += 1 if token.group() == "{{" else -1
        if depth == 0:
            stop = match.end() + token.start(); break
    if stop is None:
        return "", {}
    fields = {}
    for item in split_top_level(text[match.end():stop]):
        if "=" in item:
            key, value = item.split("=", 1)
            fields[key.strip().lower().replace(" ", "_")] = value.strip()
    return normalize(match.group(1)), fields


def clean_wiki(value):
    value = re.sub(r"<!--.*?-->|<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", " ", value or "", flags=FLAGS)
    value = re.sub(r"\[\[(?:File|Image|Category):[^\n]*?\]\]", " ", value, flags=re.I)
    value = re.sub(r"\[\[([^\[\]]+)\]\]", lambda m: m.group(1).split("|")[-1], value)
    # Preserve useful list template values, then remove remaining nested templates.
    value = re.sub(r"\{\{\s*(?:plainlist|unbulleted list|ubl|hlist|flatlist)\s*\|([^{}]*)\}\}", lambda m: m.group(1).replace("|", "; "), value, flags=FLAGS)
    for _ in range(30):
        cleaned = re.sub(r"\{\{[^{}]*\}\}", " ", value)
        if cleaned == value: break
        value = cleaned
    value = re.sub(r"\[https?://\S+\s+([^]]+)\]", r"\1", value)
    value = re.sub(r"<[^>]*>|'{2,}|={2,}|^\s*[*#:;]+", " ", value, flags=re.M)
    return " ".join(unescape(value).split())


def field_values(value):
    links = re.findall(r"\[\[([^\[\]]+)\]\]", value or "")
    if links:
        return list(dict.fromkeys(clean_wiki(x.split("|", 1)[0]) for x in links))
    return [s.strip() for s in re.split(r";|<br\s*/?>|\n\s*\*", clean_wiki(value)) if s.strip()]


def extract_wiki(record):
    """Input is one Hadoop-delimited page; revision IDs never become page IDs."""
    header = record.split("<revision>", 1)[0]
    title = re.search(r"<title>(.*?)</title>", header, re.S)
    page_id = re.search(r"<id>(\d+)</id>", header)
    namespace = re.search(r"<ns>(\d+)</ns>", header)
    if not title or not page_id or not namespace or namespace.group(1) != "0":
        return None
    title = unescape(title.group(1))
    redirect = re.search(r'<redirect\b[^>]*\btitle=[\"\x27](.*?)[\"\x27]', header)
    if redirect:
        return {"kind": "redirect", "title": title, "target": unescape(redirect.group(1)), "id": page_id.group(1)}
    content = re.search(r"<text\b[^>]*>(.*?)</text>", record, re.S)
    if not content:
        return None
    text = unescape(content.group(1))
    if re.search(r"\{\{\s*(?:disambiguation|disambig|dab|hndis)\b", text, re.I):
        return None
    box_type, fields = infobox(text)
    categories = re.findall(r"\[\[Category:([^]|]+)", text, re.I)
    if box_type in {"book", "novel", "novella", "short story", "poem", "play"}:
        kind = "book"
    elif box_type in {"writer", "author", "poet"} or (
        box_type in {"person", "scientist", "philosopher", "academic"}
        and re.search(r"writer|novelist|poet|author|journalist|editor", fields.get("occupation", "") + " ".join(categories), re.I)
    ) or re.search(r"\b(?:novelists|writers|poets)\b", " ".join(categories), re.I):
        kind = "person"
    else:
        return None
    authors = field_values(fields.get("author", ""))
    names = [title, clean_wiki(fields.get("name", ""))]
    if kind == "person":
        names += field_values(fields.get("pseudonym", "")) + field_values(fields.get("birth_name", ""))
    summary = clean_wiki(re.split(r"(?m)^==+[^=]", text, maxsplit=1)[0])[:6000]
    plot = re.search(r"(?im)^==\s*(?:Plot(?: summary| synopsis)?|Synopsis)\s*==\s*\n(.*?)(?=^==[^=]|\Z)", text, re.S)
    date = fields.get("pub_date", fields.get("release_date", fields.get("publication_date", "")))
    year = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", date)
    return {
        "kind": kind, "id": page_id.group(1), "title": title,
        "url": "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()_"),
        "keys": sorted({k for n in names if n for k in (person_keys(n) if kind == "person" else title_keys(n))}),
        "authors": authors, "author_keys": sorted({k for a in authors for k in person_keys(a)}),
        "summary": summary, "plot": clean_wiki(plot.group(1))[:20000] if plot else "",
        "genres": field_values(fields.get("genre", "")), "language": clean_wiki(fields.get("language", "")),
        "publisher": clean_wiki(fields.get("publisher", "")), "first_publication_year": int(year.group(1)) if year else None,
        "nationality": clean_wiki(fields.get("nationality", "")), "occupation": clean_wiki(fields.get("occupation", "")),
        "infobox_type": box_type,
    }
