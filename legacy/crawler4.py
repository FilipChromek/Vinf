import requests
import time

# Jedina externa kniznica je requests; time je sucastou Pythonu.
# Pred spustenim vytvor priecinok html (napr. mkdir html).

START_URL = "https://www.fadedpage.com/"
MAX_PAGES = 0  # 0 = bez limitu, napr. 30 = najviac 30 stranok za jedno spustenie

HEADERS = {
    "User-Agent": "FadedPageStudentCrawler/1.0",
    "Accept": "text/html,application/xhtml+xml",
}
TIMEOUT = (10, 30)  # 10 s na pripojenie, 30 s na necinnost pri citani
REQUEST_DELAY = 0  # Sekundy cakania pred kazdym requestom


def najdi_koniec_tagu(html, zaciatok):
    # Znak > v uvodzovkach nie je koniec tagu.
    uvodzovka = ""

    for i in range(zaciatok, len(html)):
        znak = html[i]

        if uvodzovka:
            if znak == uvodzovka:
                uvodzovka = ""
        elif znak == '"' or znak == "'":
            uvodzovka = znak
        elif znak == ">":
            return i

    return -1


def najdi_linky(html):
    linky = []
    male_html = html.lower()
    pozicia = 0

    while True:
        zaciatok = male_html.find("<a", pozicia)
        if zaciatok == -1:
            break

        # Nechceme omylom zachytit napr. <article>.
        if zaciatok + 2 < len(html) and html[zaciatok + 2] not in " \t\r\n>/":
            pozicia = zaciatok + 2
            continue

        koniec = najdi_koniec_tagu(html, zaciatok)
        if koniec == -1:
            break

        tag = html[zaciatok:koniec]
        maly_tag = tag.lower()
        pozicia = koniec + 1
        href = maly_tag.find("href")

        while href != -1:
            # Kontrola, aby sme si nepomylili href s data-href.
            pred = tag[href - 1] if href > 0 else ""
            za = tag[href + 4] if href + 4 < len(tag) else ""

            if pred.isspace() and (za.isspace() or za == "="):
                i = href + 4
                while i < len(tag) and tag[i].isspace():
                    i += 1

                if i < len(tag) and tag[i] == "=":
                    i += 1
                    while i < len(tag) and tag[i].isspace():
                        i += 1

                    if i < len(tag):
                        if tag[i] == '"' or tag[i] == "'":
                            uvodzovka = tag[i]
                            i += 1
                            j = tag.find(uvodzovka, i)
                            if j != -1:
                                linky.append(tag[i:j])
                        else:
                            j = i
                            while j < len(tag) and not tag[j].isspace():
                                j += 1
                            linky.append(tag[i:j])
                break

            href = maly_tag.find("href", href + 4)

    return linky


def sprav_url(aktualna_url, link):
    link = link.strip().replace("&amp;", "&")

    if not link or link.startswith("#"):
        return ""

    if link.startswith("http://") or link.startswith("https://"):
        url = link
    elif link.startswith("//"):
        url = aktualna_url.split(":")[0] + ":" + link
    elif link.startswith("/"):
        zaklad = aktualna_url.split("://")[0] + "://" + aktualna_url.split("/")[2]
        url = zaklad + link
    elif link.startswith("?"):
        url = aktualna_url.split("#")[0].split("?")[0] + link
    elif ":" in link:
        # Napriklad mailto:, javascript: alebo tel:.
        return ""
    else:
        zaklad = aktualna_url.split("#")[0].split("?")[0]
        url = zaklad.rsplit("/", 1)[0] + "/" + link

    return url.split("#")[0]



def preskoc_url(url):
    # Zakazane pripony suborov (okrem .html, co moze byt normalna webova stranka).
    male = url.lower()
    casti = male.split("?", 1)
    cesta = casti[0]

    if cesta.endswith((".txt", ".pdf", ".epub", ".mobi", ".zip",
                       ".azw", ".azw3", ".jpg", ".jpeg", ".png",
                       ".gif", ".svg", ".css", ".js")):
        return True

    # Preskocime kazdu URL, v ktorej sa nachadza text "file".
    # Napriklad link.php?file=20220713.epub.
    if "file" in male:
        return True

    return False


def pridaj_link(aktualna_url, link, domena, fronta, najdene, subor_queue):
    nova_url = sprav_url(aktualna_url, link)
    if not nova_url.startswith(("http://", "https://")):
        return

    if nova_url.split("/")[2].lower() != domena:
        return

    if preskoc_url(nova_url):
        return

    if nova_url not in najdene:
        najdene.add(nova_url)
        fronta.append(nova_url)
        subor_queue.write(nova_url + "\n")


def nacitaj_stav():
    # Z urls.txt nacitame uz stiahnute URL a posledne cislo HTML suboru.
    hotove = set()
    stare_stranky = []
    pocet = 0
    try:
        with open("html2/urls.txt", "r", encoding="utf-8") as f:
            for riadok in f:
                casti = riadok.strip().split(" ", 1)
                if len(casti) != 2:
                    continue

                nazov, url = casti
                hotove.add(url)
                stare_stranky.append((nazov, url))
                if nazov.startswith("page_") and nazov.endswith(".html"):
                    cislo = nazov[5:-5]
                    if cislo.isdigit() and int(cislo) > pocet:
                        pocet = int(cislo)
    except FileNotFoundError:
        pass

    # queue.txt obsahuje VSETKY objavene URL. Hotove z nej vynechame.
    domena = START_URL.split("/")[2].lower()
    fronta = []
    najdene = set()
    try:
        with open("html2/queue.txt", "r", encoding="utf-8") as f:
            for riadok in f:
                url = riadok.strip()
                # Preskocime aj nevhodne odkazy zo stareho queue.txt.
                if preskoc_url(url):
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                if url.split("/")[2].lower() != domena:
                    continue
                if url not in najdene:
                    najdene.add(url)
                    if url not in hotove:
                        fronta.append(url)
    except FileNotFoundError:
        # Pri starej verzii existuje urls.txt, ale este nie queue.txt.
        # V takom pripade vytiahneme odkazy zo starych ulozenych HTML.
        domena = START_URL.split("/")[2].lower()
        with open("html2/queue.txt", "a", encoding="utf-8") as f:
            for nazov, url in stare_stranky:
                if url not in najdene:
                    najdene.add(url)
                    f.write(url + "\n")

                try:
                    with open("html2/" + nazov, "rb") as stary_subor:
                        html = stary_subor.read().decode("utf-8", errors="ignore")
                    for link in najdi_linky(html):
                        pridaj_link(url, link, domena, fronta, najdene, f)
                except FileNotFoundError:
                    pass

    # Prve spustenie: vlozime uvodnu URL do fronty aj na disk.
    if START_URL not in najdene:
        najdene.add(START_URL)
        if START_URL not in hotove:
            fronta.insert(0, START_URL)
        with open("html2/queue.txt", "a", encoding="utf-8") as f:
            f.write(START_URL + "\n")

    return fronta, najdene, hotove, pocet


def crawl():
    domena = START_URL.split("/")[2].lower()
    fronta, najdene, hotove, pocet = nacitaj_stav()
    nove_stranky = 0

    while fronta and (MAX_PAGES == 0 or nove_stranky < MAX_PAGES):
        url = fronta.pop(0)
        # Dodatocna kontrola pred samotnym HTTP requestom.
        if preskoc_url(url) or url.split("/")[2].lower() != domena:
            continue
        if url in hotove:
            continue

        print("Stahujem:", url)
        time.sleep(REQUEST_DELAY)
        try:
            odpoved = requests.get(
                url,
                timeout=TIMEOUT,
                headers=HEADERS,
                allow_redirects=False
            )
            if odpoved.status_code != 200:
                print("HTTP chyba:", odpoved.status_code)
                continue
            if "text/html" not in odpoved.headers.get("Content-Type", "").lower():
                continue
        except requests.RequestException as chyba:
            print("Chyba:", chyba)
            continue

        # Ulozime cely HTML dokument.
        pocet += 1
        nove_stranky += 1
        subor = "page_" + str(pocet) + ".html"
        with open("html2/" + subor, "wb") as f:
            f.write(odpoved.content)

        # Nove odkazy zapiseme do queue.txt hned pri objaveni.
        # Takto sa pri preruseni nestratia.
        with open("html2/queue.txt", "a", encoding="utf-8") as f:
            for link in najdi_linky(odpoved.text):
                pridaj_link(url, link, domena, fronta, najdene, f)

        # Stranku oznacime za dokoncenu az po ulozeni novych URL.
        with open("html2/urls.txt", "a", encoding="utf-8") as f:
            f.write(subor + " " + url + "\n")
        hotove.add(url)

    print("Hotovo. Novych HTML stranok:", nove_stranky)
    print("Celkovo ulozenych HTML stranok:", pocet)
    print("Zostalo vo fronte:", len(fronta))


if __name__ == "__main__":
    crawl()
