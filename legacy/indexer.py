
import csv
import math
import re

KNIHY_CSV = "knihy.csv"
INDEX_TSV = "index.tsv"

# Polia, v ktorych sa vyhladava
POLIA = (
    "title",
    "author",
    "published",
    "publisher",
    "tags",
    "description",
    "author_bio"
)

# Zakladne anglicke stop slova
STOP_SLOVA = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at",
    "for", "by", "with", "is", "are", "was", "were", "be", "been",
    "as", "that", "this", "these", "those", "it", "its", "from",
    "he", "she", "they", "them", "his", "her", "their", "who",
    "which", "what", "when", "where", "but", "not", "into", "about"
}

TOKEN_RE = re.compile(
    r"[^\W_]+(?:[-'’][^\W_]+)*",
    re.UNICODE
)


def tokenizuj(text):
    """Rozdeli text na slova a odstrani stop slova."""
    return [
        slovo
        for slovo in TOKEN_RE.findall(str(text).casefold())
        if slovo not in STOP_SLOVA
    ]


def vytvor_index():
    """Vytvori TF index z CSV a ulozi ho do TSV."""

    dokumenty = {}
    index = {}
    preskocene = 0

    with open(KNIHY_CSV, "r", encoding="utf-8-sig", newline="") as subor:
        reader = csv.DictReader(subor)

        if not reader.fieldnames or not {"id", "title"}.issubset(reader.fieldnames):
            raise ValueError("CSV musi obsahovat stlpce id a title")

        for kniha in reader:

            id_knihy = (kniha.get("id") or "").strip()
            title = (kniha.get("title") or "").strip()

            if not id_knihy or not title or id_knihy in dokumenty:
                preskocene += 1
                continue

            # Spojime textove polia knihy
            text = " ".join(
                kniha.get(pole) or ""
                for pole in POLIA
            )

            slova = tokenizuj(text)

            if not slova:
                preskocene += 1
                continue

            # Ulozime zakladne informacie o knihe
            dokumenty[id_knihy] = (
                title,
                kniha.get("author") or "",
                kniha.get("published") or "",
                kniha.get("url") or ""
            )

            # Pocitanie TF (Term Frequency)
            pocty = {}

            for slovo in slova:
                pocty[slovo] = pocty.get(slovo, 0) + 1

            # Invertovany index: slovo -> kniha -> TF
            for slovo, pocet in pocty.items():
                index.setdefault(slovo, {})[id_knihy] = pocet

    # Ulozenie indexu do TSV
    with open(INDEX_TSV, "w", encoding="utf-8", newline="") as subor:
        writer = csv.writer(subor, delimiter="\t")

        # D = dokument
        for id_knihy, (title, author, published, url) in dokumenty.items():
            writer.writerow([
                "D", id_knihy, title, author, published, url
            ])

        # T = termin a jeho vyskyt
        for slovo, postingy in index.items():
            for id_knihy, tf in postingy.items():
                writer.writerow([
                    "T", slovo, id_knihy, tf
                ])

    print("\nIndex bol vytvoreny:", INDEX_TSV)
    print("Indexovanych knih:", len(dokumenty))
    print("Unikatnych slov:", len(index))
    print("Preskocenych zaznamov:", preskocene)

    return dokumenty, index


def nacitaj_index():
    """Nacita existujuci index.tsv."""

    dokumenty = {}
    index = {}

    with open(INDEX_TSV, "r", encoding="utf-8", newline="") as subor:
        reader = csv.reader(subor, delimiter="\t")

        for zaznam in reader:

            if not zaznam:
                continue

            if zaznam[0] == "D" and len(zaznam) == 6:
                dokumenty[zaznam[1]] = tuple(zaznam[2:6])

            elif zaznam[0] == "T" and len(zaznam) == 4:
                index.setdefault(
                    zaznam[1], {}
                )[zaznam[2]] = int(zaznam[3])

    return dokumenty, index


def idf(n, df, metoda):
    """Vypocet dvoch metod IDF."""

    if metoda == "classic":
        return math.log(n / df)

    if metoda == "smooth":
        return math.log((n + 1) / (df + 1)) + 1

    raise ValueError("Neznama IDF metoda")


def vyhladaj(dokumenty, index, dopyt, metoda, limit=10):
    """Vyhladavanie pomocou TF-IDF."""

    n = len(dokumenty)

    if n == 0:
        return []

    # Tokenizacia dopytu
    slova_dopytu = {}

    for slovo in tokenizuj(dopyt):
        slova_dopytu[slovo] = slova_dopytu.get(slovo, 0) + 1

    skore = {}

    # Prejdeme jednotlive slova dopytu
    for slovo, tf_dopytu in slova_dopytu.items():

        postingy = index.get(slovo, {})

        if not postingy:
            continue

        df = len(postingy)
        vaha = idf(n, df, metoda)

        # Vypocet TF-IDF pre kazdu knihu
        for id_knihy, tf in postingy.items():

            skore[id_knihy] = (
                skore.get(id_knihy, 0)
                + tf * vaha * tf_dopytu
            )

    # Vyberieme knihy s kladnym skore
    vysledky = [
        (id_knihy, hodnota)
        for id_knihy, hodnota in skore.items()
        if hodnota > 0
    ]

    # Zoradenie od najlepsieho vysledku
    vysledky.sort(key=lambda x: (-x[1], x[0]))

    return vysledky[:limit]


def vypis_vysledky(dokumenty, index, dopyt, metoda):
    """Zobrazi vyhladane knihy."""

    print("\n---------------------------------")
    print("Dopyt:", dopyt)
    print("IDF metoda:", metoda)
    print("---------------------------------")

    vysledky = vyhladaj(
        dokumenty,
        index,
        dopyt,
        metoda
    )

    if not vysledky:
        print("Nenasli sa ziadne vysledky s kladnym skore.")
        return

    for poradie, (id_knihy, skore) in enumerate(vysledky, 1):

        title, author, published, url = dokumenty[id_knihy]

        print(f"\n{poradie}. {title}")
        print(f"   Autor: {author}")
        print(f"   Rok: {published}")
        print(f"   ID: {id_knihy}")
        print(f"   Skore: {skore:.4f}")
        print(f"   URL: {url}")


def main():

    # Pokusime sa nacitat existujuci index
    try:
        dokumenty, index = nacitaj_index()

        print("Existujuci index bol nacitany.")
        print("Pocet knih:", len(dokumenty))
        print("Pocet slov:", len(index))

    except FileNotFoundError:

        print("Index neexistuje. Vytvaram novy...")

        try:
            dokumenty, index = vytvor_index()

        except (OSError, ValueError, csv.Error) as chyba:
            print("Chyba:", chyba)
            return

    # Hlavne menu programu
    while True:

        print("\n========== FADEDPAGE ==========")
        print("1 - Vyhladavanie: klasicke IDF")
        print("2 - Vyhladavanie: vyhladene IDF")
        print("3 - Porovnanie oboch IDF metod")
        print("4 - Porovnanie na 3 dopytoch")
        print("5 - Znovu vytvorit index")
        print("0 - Koniec")
        print("================================")

        volba = input("Vyber moznost: ").strip()

        if volba == "0":
            print("Koniec programu.")
            break

        elif volba in ("1", "2", "3"):

            metoda = "classic" if volba == "1" else "smooth"

            while True:

                dopyt = input(
                    "\nZadaj dopyt (ENTER = spat): "
                ).strip()

                if not dopyt:
                    break

                if volba == "3":

                    vypis_vysledky(
                        dokumenty, index, dopyt, "classic"
                    )

                    vypis_vysledky(
                        dokumenty, index, dopyt, "smooth"
                    )

                else:

                    vypis_vysledky(
                        dokumenty, index, dopyt, metoda
                    )

        elif volba == "4":

            dopyty = (
                "fiction romance",
                "war tribunal",
                "Rosika Storey"
            )

            for dopyt in dopyty:

                vypis_vysledky(
                    dokumenty, index, dopyt, "classic"
                )

                vypis_vysledky(
                    dokumenty, index, dopyt, "smooth"
                )

        elif volba == "5":

            try:
                dokumenty, index = vytvor_index()

            except (OSError, ValueError, csv.Error) as chyba:
                print("Chyba pri vytvarani indexu:", chyba)

        else:
            print("Neplatna moznost.")


if __name__ == "__main__":
    main()
