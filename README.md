# Vinf — vyhľadávanie kníh s Wikipédiou (Kod11)

Semestrálny projekt: REGEX extrakcia údajov z FadedPage a Wikipédie,
spracovanie cez Apache Spark, prepojenie záznamov a konzolové vyhľadávanie
pomocou PyLucene. Výsledkom vyhľadávania je vždy kniha, doplnená o údaje
z článku o diele a samostatných článkov o autoroch/editoroch.

Tento repozitár obsahuje samostatne spustiteľnú zdrojovú verziu Kod11.
Veľké vstupné dáta a hotové Lucene indexy sa do Gitu neukladajú.

## Čo obsahuje repozitár

| Súbor / priečinok | Úloha |
|---|---|
| `extractors.py`, `text_utils.py` | REGEX extrakcia a normalizácia názvov/mien |
| `spark_job.py` | Kroky `html`, `wiki` a `join` |
| `lucene_index.py`, `search.py` | Vytvorenie indexov a vyhľadávanie |
| `records.py`, `prepare.py` | Čítanie záznamov a príprava pôvodného extraktora pre Spark |
| `legacy/` | Pôvodný crawler, extraktor a indexer z prvého odovzdania |
| `tests/`, `verify.py` | Testy a generovanie syntetických ukážkových dát |
| `compare.py`, `summarize.py` | Porovnanie vyhľadávania a prehľady joinu |
| `verify_real.py` | Voliteľná regresná kontrola voči pôvodnému Kod6 |
| `reports/` | Vybrané výsledky pôvodného behu nad celou kolekciou |
| `docs/` | [Dokumentácia konzultácií 3 a 4, v3](docs/Konzultacie_3_a_4_Kod11_v3.pdf) |

PDF opisuje pôvodný lokálny experiment: Kod11 použil hotovú extrakciu Kod6.
Repozitár upravuje iba umiestnenie vstupov a spúšťanie, aby nevyžadoval
vedľajšie priečinky Kod5/Kod6. Extrakcia, normalizácia, pravidlá joinu a
vyhľadávanie zostávajú rovnaké. Aktuálne príkazy a cesty sú uvedené tu.

## Rýchle overenie bez veľkého datasetu

Potrebný je Docker s podporou Linux kontajnerov a Docker Compose.
Vo Windows používame Docker Desktop a PowerShell. Príkazy spúšťaj z koreňa
repozitára; prvé zostavenie potrebuje internet na stiahnutie závislostí.

```powershell
git clone https://github.com/FilipChromek/Vinf.git
cd Vinf
New-Item -ItemType Directory -Force input
docker compose build
docker compose run --rm app python verify.py
```

Test vytvorí 11 syntetických kníh a malé wiki XML, spustí Spark extrakciu
a join, vytvorí dočasný Lucene index a preverí dopyty. Testuje aj stránku
presahujúcu hranicu XML bloku. Dočasné dáta po sebe odstráni; nevytvorí
produkčný index pre príkaz `search`.

Tri testy nad pôvodnými HTML sú voliteľné: bez `input/html` sa výslovne
preskočia. Ak adresár dodáš, musí obsahovať pôvodnú kolekciu alebo aspoň
20 platných stránok vrátane `20071202.html` a `20090213.html`.
Výsledok aktuálneho testovania sa zapisuje do ignorovaného
`reports/local_tests.json`. `reports/tests.json` zostáva záznamom pôvodného
plného overenia, vrátane reálnych HTML.

PowerShell alternatíva k zostaveniu a testu:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 build
powershell -ExecutionPolicy Bypass -File .\run.ps1 test
```

## Vstupné dáta a celá pipeline

Priprav túto lokálnu štruktúru. `input/` sa do kontajnera pripája ako
`/input` iba na čítanie a celý je v `.gitignore`.

```text
input/
  html/                 pôvodné HTML stránky kníh z FadedPage
  wiki.xml              rozbalený anglický Wikipedia pages-articles dump
  old/                  voliteľné súbory z prvého odovzdania
    knihy.csv           pôvodné metadáta pre kontrolované porovnanie
    index.tsv           pôvodný vlastný index pre compare.py
```

Pôvodný experiment použil dump
`enwiki-20261101-pages-articles-multistream.xml` (približne 118 GB).
Pre uvedené príkazy ho umiestni ako `input/wiki.xml`; predvolená cesta
očakáva rozbalené XML. Zdroj dumpov: [Wikimedia Downloads](https://dumps.wikimedia.org/enwiki/).
HTML pochádzajú z [FadedPage](https://www.fadedpage.com/).

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 html
powershell -ExecutionPolicy Bypass -File .\run.ps1 wiki
powershell -ExecutionPolicy Bypass -File .\run.ps1 join
powershell -ExecutionPolicy Bypass -File .\run.ps1 index
powershell -ExecutionPolicy Bypass -File .\run.ps1 search
```

- `html` vytvorí `data/books`.
- `wiki` vytvorí `data/wiki`.
- `join` číta tieto dve cesty, vytvorí `data/enriched` a prehľady prepojení.
- `index` vytvorí `indexes/plain` a `indexes/enriched`.
- `search` otvorí obohatený index; prázdny vstup ukončí konzolu.

Ak už máš hotovú extrakciu, môžeš skopírovať adresáre `books` a `wiki`
vrátane ich súborov `part-*` pod `data/` a začať krokom `join`.
Ak máš hotové obohatené záznamy Kod11, stačí ich adresár skopírovať ako
`data/enriched` a začať krokom `index`. Dáta ani indexy sa automaticky
nestiahnu. Spark a indexer odmietajú prepísať existujúce výstupy; na ďalší
experiment použi nové výstupné cesty cez argumenty Python skriptov.

Ak existuje `input/old/knihy.csv`, `run.ps1 index` ho použije pre pole
`contents` v oboch indexoch. Tým sa zachová pôvodný text použitý pri
porovnaní so starým indexerom. Bez tohto CSV sa `contents` zostaví
z extrahovaných kníh; aplikácia funguje, ale nejde o identický porovnávací
vstup ako v uložených reportoch. CSV musí obsahovať všetky indexované ID.

Spark beží lokálne cez `local[4]` s pamäťou drivera 4 GB. Docker kontajner
má limit 10 GB a 4 CPU. Viacpočítačový klaster nebol overovaný.

## Vyhľadávanie

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 search -Query 'title:"Two People"'
powershell -ExecutionPolicy Bypass -File .\run.ps1 search -Query 'authors:christie AND tags:mystery'
powershell -ExecutionPolicy Bypass -File .\run.ps1 search -Query 'wiki_match_method:title_exact'
powershell -ExecutionPolicy Bypass -File .\run.ps1 search -Query 'wiki_match_status:ambiguous'
powershell -ExecutionPolicy Bypass -File .\run.ps1 search -Author 'Rafael Sabatini' -YearFrom 1915 -YearTo 1915
```

Voľný text hľadá v `contents` a `wiki` s predvoleným **OR**. Podporované sú
polia, frázy, `AND`/`OR`/`NOT`, fuzzy, prefixy a filtre roku, autora a tagu.
Fuzzy dopyt nemení pravidlá joinu. Rozšírené prepínače používa priamo Python:

```powershell
docker compose run --rm app python search.py --help
docker compose run --rm app python search.py "war tribunal" --similarity bm25 --limit 5
docker compose run --rm app python search.py "detective mystery" --index indexes/plain --plain
```

## Pravidlá joinu Kod11

Pre dielo vyžadujeme presnú zhodu celého normalizovaného názvu alebo aliasu
a vhodný literárny typ článku. Autor ani rok nie sú podmienkou prijatia.
Normalizácia zjednotí veľkosť písmen, diakritiku a interpunkciu; podporuje
aj vybrané koncové dodatky, napríklad `(novel)` alebo označenie série.
Poradie slov sa zachováva; čiastočná zhoda ani pravidlo 2/3 sa nepoužíva.

Rovnako ako v Kod6 sa typ diela určuje podľa infoboxu `book`, `novel`,
`novella`, `short story`, `poem` alebo `play`. Nie je to kontrola skutočnej
wiki kategórie Books. Presmerovania sa riešia na jeden krok.

Autori a editori sa pripájajú nezávisle podľa normalizovaného mena/aliasu,
rovnako ako v Kod6. Nepoužíva sa nový odhad iba podľa iniciál a priezviska.
Meno pochádza z HTML knihy; samostatná autorova HTML stránka nie je potrebná.

Jedno rôzne wiki ID znamená `matched`, viac ID `ambiguous`, chýbajúci
kandidát `unmatched`. Ľavé spojenie zachová aj nepripojené knihy.
`author_agrees` v audite je iba informácia, nie filter.

## Pôvodné výsledky a porovnanie

Vybrané reporty v Gite pochádzajú z pôvodného behu Kod11 nad celou kolekciou:

| Ukazovateľ | Hodnota |
|---|---:|
| Knihy / dokumenty v každom indexe | 9 012 |
| Prijaté prepojenia diel | 1 256 |
| Nejednoznačné prepojenia diel | 104 |
| Knihy bez pripojeného diela | 7 652 |
| Unikátne wiki články o dielach | 1 239 |
| Unikátne wiki články o osobách | 1 199 |
| Unikátne wiki články spolu | 2 438 |

`reports/comparison.tsv` obsahuje päť dopytov, štyri varianty indexu
a top 10 výsledkov (200 riadkov). Sekcia 4.5 PDF porovnáva konkrétne knihy
a ich poradie. Relevantnosť nebola ručne vyhodnotená.

Na zopakovanie porovnania dodaj pôvodné `input/old/index.tsv` a
`input/old/knihy.csv`, vytvor oba Lucene indexy s týmto CSV a spusti:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 compare
```

Nový beh aktualizuje príslušné reporty. Generované plné prehľady
`book_links.tsv`, `person_links.tsv` a `title_matches.tsv` nie sú v Gite;
prvé dva vytvára `summarize.py`, tretí voliteľná kontrola nižšie.

**Známa hranica pravidla:** Canada od Jean Newton McIlwraith (1899)
sa pripojila ku Canada (novel) od Richarda Forda (2012). Názov a typ
vyhovujú, ale ide o rôzne diela. `reports/review_observation.json`
dokladá tento prípad; nejde o úplný ručný audit všetkých zhôd.

## Voliteľná kontrola zachovania výsledkov Kod6

`verify_real.py` je osobitná regresná kontrola, nepatrí k povinnému
spusteniu nového projektu. Potrebuje pôvodné `input/kod6/data/enriched`
a `input/kod6/indexes/plain`, kompletné výstupy joinu Kod11 aj oba nové
indexy vytvorené s pôvodným CSV. Potom možno spustiť:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 verify-real
```

Kontroluje všetky pôvodné metadáta a úplné záznamy osôb, rozhodnutia
podľa kandidátov, uložené wiki zdroje a zachovanie pôvodného vyhľadávania.
Bez referenčných dát Kod6 tento príkaz nemožno vykonať. Bežné `join`,
`index`, `search` a syntetické testy ich nepotrebujú.

## Pôvodný crawler

`legacy/crawler4.py` je zachovaný kód z prvého odovzdania. Nie je súčasťou
automatickej Spark pipeline ani testu. Pri samostatnom použití potrebuje
Python balík `requests` a pracovný priečinok `html`. Veľké stiahnuté
súbory zostávajú mimo Gitu; pre novú pipeline sa HTML ukladajú do `input/html`.
