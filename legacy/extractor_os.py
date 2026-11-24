

import re
import os

HTML_DIR = "html"
CSV_FILE = "knihy.csv"
JSONL_FILE = "knihy.jsonl"
SINGLE_HTML = ""  # Napr. "20080307.html" pre test jednej knihy

FLAGS = re.I | re.S

BOOK_DETAILS_RE = re.compile(r"<b\b[^>]*>\s*Book Details\s*</b>", FLAGS)
END_DETAILS_RE = re.compile(r"<b\b[^>]*>\s*(?:Author Bio\b|Available Formats\b)", FLAGS)
LABELS = ("Title", "Author", "Illustrator", "Published", "Publisher",
          "Tags", "Description", "Comments", "Downloads", "Pages")
NEXT_LABEL_RE = re.compile(
    r"<tr\b[^>]*>\s*<td\b[^>]*>\s*(?:" + "|".join(LABELS) + r")\s*:", FLAGS
)
AUTHOR_LINK_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"][^'\"]*csearch\.php\?author=[^'\"]*['\"][^>]*>(.*?)</a>",
    FLAGS,
)
TAG_LINK_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"][^'\"]*csearch\.php\?tags=[^'\"]*['\"][^>]*>(.*?)</a>",
    FLAGS,
)
SUGGEST_RE = re.compile(r"<span\b[^>]*\bclass\s*=\s*['\"]suggest['\"][^>]*>.*?</span>", FLAGS)

# Bez kniznice html: zakladne HTML entity + numericke entity.
ENTITY_MAP = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
    "nbsp": " ", "ndash": "–", "mdash": "—", "hellip": "…",
    "lsquo": "‘", "rsquo": "’", "ldquo": "“", "rdquo": "”",
    "bull": "•", "copy": "©", "reg": "®", "trade": "™",
    "eacute": "é", "egrave": "è", "ecirc": "ê", "euml": "ë",
    "aacute": "á", "agrave": "à", "acirc": "â", "auml": "ä",
    "iacute": "í", "igrave": "ì", "icirc": "î", "iuml": "ï",
    "oacute": "ó", "ograve": "ò", "ocirc": "ô", "ouml": "ö",
    "uacute": "ú", "ugrave": "ù", "ucirc": "û", "uuml": "ü",
    "ntilde": "ñ", "ccedil": "ç", "szlig": "ß", "pound": "£",
}


def html_entita(zhoda):
    entita = zhoda.group(1)
    try:
        if entita.lower().startswith("#x"):
            kod = int(entita[2:], 16)
            return chr(kod) if 0 < kod <= 0x10FFFF and not 0xD800 <= kod <= 0xDFFF else ""
        if entita.startswith("#"):
            kod = int(entita[1:])
            return chr(kod) if 0 < kod <= 0x10FFFF and not 0xD800 <= kod <= 0xDFFF else ""
    except ValueError:
        return zhoda.group(0)
    return ENTITY_MAP.get(entita, ENTITY_MAP.get(entita.lower(), zhoda.group(0)))


def vycisti_text(text):
    text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", text or "", flags=FLAGS)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"&(#x[\da-f]+|#\d+|[a-z][a-z0-9]+);", html_entita, text, flags=re.I)
    return " ".join(text.split())


def detail_sekcia(html):
    zaciatok = BOOK_DETAILS_RE.search(html)
    if not zaciatok:
        return None
    koniec = END_DETAILS_RE.search(html, zaciatok.end())
    return html[zaciatok.end():koniec.start() if koniec else len(html)]


def hodnota_pola(sekcia, nazov):
    vzor = (
        r"<tr\b[^>]*>\s*<td\b[^>]*>\s*" + re.escape(nazov)
        + r"\s*:(?:\s|&nbsp;|&#160;|&#xA0;)*</td>\s*<td\b[^>]*>(.*?)</td>"
    )
    najdene = re.search(vzor, sekcia, FLAGS)
    return najdene.group(1) if najdene else ""


def blok_pola(sekcia, nazov):
    zaciatok = re.search(
        r"<tr\b[^>]*>\s*<td\b[^>]*>\s*" + re.escape(nazov)
        + r"\s*:</td>\s*<td\b[^>]*>", sekcia, FLAGS
    )
    if not zaciatok:
        return ""
    koniec = NEXT_LABEL_RE.search(sekcia, zaciatok.end())
    return sekcia[zaciatok.end():koniec.start() if koniec else len(sekcia)]


def osoby(sekcia, nazov):
    mena = [vycisti_text(m) for m in AUTHOR_LINK_RE.findall(blok_pola(sekcia, nazov))]
    mena = list(dict.fromkeys(m for m in mena if m))
    if not mena:
        fallback = vycisti_text(hodnota_pola(sekcia, nazov))
        if fallback:
            mena = [fallback]
    return mena


def cislo_pola(sekcia, nazov):
    hodnota = vycisti_text(hodnota_pola(sekcia, nazov))
    zhoda = re.search(r"\d[\d\s,]*", hodnota)
    return int(re.sub(r"\D", "", zhoda.group(0))) if zhoda else None


def extrahuj_biografiu(html):
    """Text v div.bio za nadpisom Author Bio for ..., inak prazdny text."""
    nadpis = re.search(r"<b\b[^>]*>\s*Author Bio for\s+.*?</b>", html, FLAGS)
    if not nadpis:
        return ""
    # Ohranicenie: neprejdeme omylom az do nesuvisiacej sekcie.
    koniec = re.search(r"<b\b[^>]*>\s*Available Formats\s*</b>", html[nadpis.end():], FLAGS)
    fragment = html[nadpis.end():nadpis.end() + koniec.start()] if koniec else html[nadpis.end():]
    bio = re.search(
        r"<div\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bbio\b[^'\"]*['\"][^>]*>(.*?)</div>",
        fragment, FLAGS,
    )
    return vycisti_text(bio.group(1)) if bio else ""


def extrahuj_knihu(html, source_file="", url=None):
    """Vrati udaje o knihe alebo None pre uvodnu/katalogovu stranku."""
    sekcia = detail_sekcia(html)
    if sekcia is None:
        return None

    identifikator = re.search(
        r"<input\b[^>]*\bname\s*=\s*['\"]bookid['\"][^>]*\bvalue\s*=\s*['\"](\d+)['\"]",
        html, FLAGS,
    )
    if not identifikator:
        identifikator = re.search(r"/books/(\d{8})/", html, FLAGS)
    nazov = vycisti_text(hodnota_pola(sekcia, "Title"))
    if not nazov:
        h1 = re.search(r"<h1\b[^>]*\bclass\s*=\s*['\"]title['\"][^>]*>(.*?)</h1>", html, FLAGS)
        nazov = vycisti_text(h1.group(1)) if h1 else ""
    if not identifikator or not nazov:
        return None

    id_knihy = identifikator.group(1)
    autori = osoby(sekcia, "Author")
    ilustratori = osoby(sekcia, "Illustrator")
    tagy = [vycisti_text(t) for t in TAG_LINK_RE.findall(hodnota_pola(sekcia, "Tags"))]
    tagy = list(dict.fromkeys(t for t in tagy if t))
    popis = vycisti_text(SUGGEST_RE.sub("", hodnota_pola(sekcia, "Description")))

    return {
        "id": id_knihy,
        "url": url or "https://www.fadedpage.com/showbook.php?pid=" + id_knihy,
        "title": nazov,
        "author": "; ".join(autori),
        "authors": autori,
        "illustrator": "; ".join(ilustratori) if ilustratori else None,
        "published_year": cislo_pola(sekcia, "Published"),
        "publisher": vycisti_text(hodnota_pola(sekcia, "Publisher")),
        "tags": tagy,
        "description": popis,
        "comments": vycisti_text(hodnota_pola(sekcia, "Comments")) or None,
        "downloads": cislo_pola(sekcia, "Downloads"),
        "pages": cislo_pola(sekcia, "Pages"),
        "author_bio": extrahuj_biografiu(html),
        "source_file": source_file,
    }


CSV_COLUMNS = (
    "id", "url", "source_file", "title", "author", "published",
    "publisher", "tags", "description", "downloads", "pages", "author_bio",
)


def csv_hodnota(hodnota):
    if hodnota is None:
        hodnota = ""
    if isinstance(hodnota, list):
        hodnota = "; ".join(str(x) for x in hodnota)
    # Kazdu bunku uzavrieme do uvodzoviek; uvodzovky v texte zdvojime.
    return '"' + str(hodnota).replace('"', '""') + '"'


def json_hodnota(hodnota):
    """Jednoduchy JSON zapis bez importu json (pre kompatibilitu s indexerom)."""
    if hodnota is None:
        return "null"
    if isinstance(hodnota, int):
        return str(hodnota)
    if isinstance(hodnota, list):
        return "[" + ",".join(json_hodnota(x) for x in hodnota) + "]"
    text = str(hodnota).replace("\\", "\\\\").replace('"', '\\"')
    text = re.sub(
        r"[\x00-\x1f]",
        lambda m: "\\u%04x" % ord(m.group(0)),
        text,
    )
    return '"' + text + '"'


def json_riadok(kniha):
    return "{" + ",".join(
        json_hodnota(k) + ":" + json_hodnota(v)
        for k, v in kniha.items()
    ) + "}"


def spracuj_subor(cesta, url, csv_vystup, jsonl_vystup):
    try:
        with open(cesta, "r", encoding="utf-8", errors="replace") as html_subor:
            obsah = html_subor.read()
    except OSError as chyba:
        print("Chyba citania:", cesta, chyba)
        return "error"

    nazov_suboru = cesta.replace("\\", "/").rsplit("/", 1)[-1]
    kniha = extrahuj_knihu(obsah, source_file=nazov_suboru, url=url)
    if kniha is None:
        return "skip"

    csv_zaznam = {
        **kniha,
        "published": kniha["published_year"],
    }
    csv_vystup.write(",".join(csv_hodnota(csv_zaznam.get(k)) for k in CSV_COLUMNS) + "\n")
    jsonl_vystup.write(json_riadok(kniha) + "\n")
    return "book"


def main():
    statistiky = {"book": 0, "skip": 0, "error": 0}

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as csv_vystup, \
         open(JSONL_FILE, "w", encoding="utf-8") as jsonl_vystup:
        csv_vystup.write(",".join(csv_hodnota(s) for s in CSV_COLUMNS) + "\n")

        if SINGLE_HTML:
            vysledok = spracuj_subor(SINGLE_HTML, None, csv_vystup, jsonl_vystup)
            statistiky[vysledok] += 1
        else:
            if not os.path.isdir(HTML_DIR):
                print("Nenasiel sa priecinok:", HTML_DIR)
                return

            for nazov_suboru in sorted(os.listdir(HTML_DIR)):
                if not nazov_suboru.lower().endswith(".html"):
                    continue

                cesta = os.path.join(HTML_DIR, nazov_suboru)
                if not os.path.isfile(cesta):
                    continue

                vysledok = spracuj_subor(
                    cesta,
                    None,  # URL sa v extrahuj_knihu zostavi z ID knihy.
                    csv_vystup,
                    jsonl_vystup,
                )
                statistiky[vysledok] += 1

    print("Extrahovane knihy:", statistiky["book"])
    print("Preskocene neknihove HTML:", statistiky["skip"])
    print("Chyby citania:", statistiky["error"])
    print("CSV:", CSV_FILE)
    print("JSONL pre indexer:", JSONL_FILE)


if __name__ == "__main__":
    main()
