"""Three visible steps: HTML -> books, XML -> wiki, books + wiki -> enriched books."""
import argparse
import json
import time
from pathlib import Path
from pyspark import StorageLevel
from pyspark.sql import SparkSession
from extractors import extract_book, extract_wiki
from text_utils import normalize, person_keys
from prepare import prepare


def read_json(sc, path):
    return sc.textFile(path + "/part-*").map(json.loads)


def save_json(records, path):
    # Spark writes several part files; no collect() of the Wikipedia dataset.
    records.map(lambda row: json.dumps(row, ensure_ascii=False)).saveAsTextFile(path)


def unique_match(candidates):
    by_id = {row["id"]: row for row in candidates}
    if len(by_id) == 1:
        return {"status": "matched", "wiki": next(iter(by_id.values()))}
    return {"status": "ambiguous", "candidate_ids": sorted(by_id)}


def extract_html(sc, args):
    files = sc.wholeTextFiles(args.html + "/*.html", minPartitions=args.partitions)
    books = files.map(lambda item: extract_book(item[1], item[0].rsplit("/", 1)[-1])).filter(lambda b: b is not None)
    # Repeated saved pages must not duplicate books.
    books = books.map(lambda b: (b["id"], b)).reduceByKey(lambda a, b: min((a, b), key=lambda x: x["source_file"])).values()
    books.persist(StorageLevel.DISK_ONLY)
    count = books.count()
    save_json(books, args.output)
    return {"books": count, "html_files": files.count(), "authors": books.flatMap(lambda b: b["authors"]).distinct().count(),
            "editors": books.flatMap(lambda b: b["editors"]).distinct().count(), "books_without_authors": books.filter(lambda b: not b["authors"]).count()}


def extract_dump(sc, args):
    # Hadoop handles records spanning input splits. A line is NOT a wiki page.
    raw = sc.newAPIHadoopFile(
        args.dump, "org.apache.hadoop.mapreduce.lib.input.TextInputFormat",
        "org.apache.hadoop.io.LongWritable", "org.apache.hadoop.io.Text",
        conf={"textinputformat.record.delimiter": "</page>",
              "mapreduce.input.fileinputformat.split.maxsize": str(args.split_mb * 1024 * 1024)})
    records = raw.values().map(extract_wiki).filter(lambda page: page is not None)
    records.persist(StorageLevel.DISK_ONLY)
    counts = dict(records.map(lambda p: (p["kind"], 1)).reduceByKey(lambda a, b: a + b).collect())
    save_json(records, args.output)
    return {"retained_pages_by_kind": counts, "input_partitions": raw.getNumPartitions(), "dump": args.dump}


def finish_book(item):
    book_id, ((book, book_match), people) = item
    result = dict(book)
    result["wiki_book_match"] = dict(book_match, method='title_exact', author_checked=False) if book_match else {
        "status": "unmatched", "author_checked": False}
    result["wiki_people"] = sorted(people or [], key=lambda p: (p["name"], p["role"]))
    return result


def join_data(sc, args):
    books = read_json(sc, args.books).persist(StorageLevel.DISK_ONLY)
    wiki = read_json(sc, args.wiki).persist(StorageLevel.DISK_ONLY)
    entities = wiki.filter(lambda p: p["kind"] != "redirect")
    # Each alias points to the full canonical entity, not to a redirect page.
    direct = entities.flatMap(lambda p: [(key, p) for key in p["keys"]])
    by_title = entities.map(lambda p: (normalize(p["title"]), p))
    redirects = wiki.filter(lambda p: p["kind"] == "redirect").map(lambda p: (normalize(p["target"]), normalize(p["title"])))
    redirected = redirects.join(by_title, args.partitions).map(lambda pair: (pair[1][0], pair[1][1]))
    aliases = direct.union(redirected).persist(StorageLevel.DISK_ONLY)

    book_keys = books.flatMap(lambda b: [(key, b) for key in b["title_keys"]])
    candidates = book_keys.join(aliases.filter(lambda pair: pair[1]["kind"] == "book"), args.partitions)
    # Exact title/alias and literary-work type suffice. Do not filter by author.
    matches = candidates.map(lambda pair: (pair[1][0]["id"], pair[1][1])).groupByKey(args.partitions).mapValues(unique_match)
    audit = candidates.map(lambda pair: {
        "book_id": pair[1][0]["id"], "wiki_id": pair[1][1]["id"], "wiki_title": pair[1][1]["title"],
        "matched_key": pair[0], "author_agrees": bool(set(pair[1][0]["author_keys"]) & set(pair[1][1]["author_keys"]))})

    # A person is extracted from the book page; no separate author HTML is needed.
    people = books.flatMap(lambda b: [p["name"] for p in b["people"]]).distinct()
    person_queries = people.flatMap(lambda name: [(key, name) for key in person_keys(name)])
    person_candidates = person_queries.join(aliases.filter(lambda pair: pair[1]["kind"] == "person"), args.partitions)
    person_matches = person_candidates.map(lambda pair: (pair[1][0], pair[1][1])).groupByKey(args.partitions).mapValues(unique_match)
    people_in_books = books.flatMap(lambda b: [(p["name"], (b["id"], p["role"])) for p in b["people"]])
    linked_people = people_in_books.leftOuterJoin(person_matches, args.partitions).map(lambda pair: (
        pair[1][0][0], {"name": pair[0], "role": pair[1][0][1], **(pair[1][1] or {"status": "unmatched"})}))
    grouped_people = linked_people.groupByKey(args.partitions).mapValues(list)
    output = books.map(lambda b: (b["id"], b)).leftOuterJoin(matches, args.partitions).leftOuterJoin(grouped_people, args.partitions).map(finish_book)
    output.persist(StorageLevel.DISK_ONLY)
    save_json(output, args.output)
    # Dictionaries are unhashable; deduplicate serialized audit entries.
    audit.map(lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)).distinct().saveAsTextFile(args.output + "_book_candidates")
    save_json(person_matches.map(lambda pair: {"name": pair[0], **pair[1]}), args.output + "_people_matches")
    book_ids = output.filter(lambda b: b["wiki_book_match"]["status"] == "matched").map(lambda b: b["wiki_book_match"]["wiki"]["id"])
    person_ids = output.flatMap(lambda b: [p["wiki"]["id"] for p in b["wiki_people"] if p["status"] == "matched"])
    return {"books": output.count(), "book_matches": dict(output.map(lambda b: (b["wiki_book_match"]["status"], 1)).reduceByKey(lambda a,b:a+b).collect()),
            "unique_wiki_books": book_ids.distinct().count(), "unique_wiki_people": person_ids.distinct().count(),
            "unique_wiki_pages_total": book_ids.union(person_ids).distinct().count(),
            "books_with_wiki_person": output.filter(lambda b: any(p["status"] == "matched" for p in b["wiki_people"])).count(),
            "matching_rule": "exact normalized title/alias AND literary-work type; people: original Kod6 normalized full name/alias",
            "author_checked_for_work": False, "redirect_support": "one hop"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["html", "wiki", "join"])
    parser.add_argument("--html", default="/input/html")
    parser.add_argument("--dump", default="/input/wiki.xml")
    parser.add_argument("--books", default="data/books")
    parser.add_argument("--wiki", default="data/wiki")
    parser.add_argument("--output", required=True, help="New output directory; existing output is never overwritten")
    parser.add_argument("--partitions", type=int, default=16)
    parser.add_argument("--split-mb", type=int, default=128)
    parser.add_argument("--report", help="Optional statistics JSON path")
    args = parser.parse_args()
    if args.partitions < 1 or args.split_mb < 1:
        parser.error("Partitions and split size must be positive")
    prepare()
    started = time.perf_counter()
    spark = SparkSession.builder.appName("FadedPage-" + args.step).getOrCreate()
    sc = spark.sparkContext
    sc.setLogLevel("WARN")
    # Ship our small Python modules to executors, including when using spark-submit on a cluster.
    for name in ("extractors.py", "text_utils.py", "legacy.zip"):
        sc.addPyFile(str(Path(__file__).parent / name))
    try:
        report = {"html": extract_html, "wiki": extract_dump, "join": join_data}[args.step](sc, args)
        report.update(step=args.step, seconds=round(time.perf_counter() - started, 3), spark_version=spark.version,
                      master=sc.master, output=args.output)
        Path("reports").mkdir(exist_ok=True)
        report_path = Path(args.report) if args.report else Path("reports", Path(args.output).name + "_stats.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
