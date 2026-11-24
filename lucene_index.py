"""Create one Lucene document per book, following the lecture's IndexFiles example."""
import argparse
import json
import time
from pathlib import Path
import lucene
from records import read_books, legacy_text
from text_utils import normalize, person_names


def build_index(input_path, index_path, include_wiki=True, original_csv=None):
    if not lucene.getVMEnv():
        lucene.initVM(vmargs=["-Djava.awt.headless=true"])
    from java.nio.file import Paths
    from org.apache.lucene.analysis.standard import StandardAnalyzer
    from org.apache.lucene.document import Document, StringField, TextField, StoredField, IntPoint, Field
    from org.apache.lucene.index import IndexWriter, IndexWriterConfig
    from org.apache.lucene.store import FSDirectory
    from org.apache.lucene.search.similarities import ClassicSimilarity

    if Path(index_path).exists():
        raise ValueError("Index already exists; select a new --index directory: " + index_path)
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    # The catalog is small (~9,000 books), unlike the Wikipedia dump.
    originals = {b["id"]: b for b in read_books(original_csv)} if original_csv else {}
    analyzer = StandardAnalyzer()
    directory = FSDirectory.open(Paths.get(index_path))
    config = IndexWriterConfig(analyzer)
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
    config.setSimilarity(ClassicSimilarity())
    writer = IndexWriter(directory, config)
    count = 0
    seen = set()
    started = time.perf_counter()
    try:
        for book in read_books(input_path):
            if book["id"] in seen:
                raise ValueError("Duplicate book ID: " + book["id"])
            seen.add(book["id"])
            doc = Document()
            doc.add(StringField("book_id", book["id"], Field.Store.YES))
            doc.add(StringField("title_exact", normalize(book["title"]), Field.Store.NO))
            for field in ("title", "description", "author_bio", "publisher"):
                doc.add(TextField(field, book.get(field) or "", Field.Store.YES))
            names = [n for name in book.get("authors", []) for n in person_names(name)]
            doc.add(TextField("authors", "; ".join(names), Field.Store.YES))
            doc.add(TextField("editors", "; ".join(book.get("editors", [])), Field.Store.YES))
            for name in names:
                doc.add(StringField("author_exact", normalize(name), Field.Store.NO))
            for tag in book.get("tags", []):
                doc.add(StringField("tag_exact", normalize(tag), Field.Store.NO))
            doc.add(TextField("tags", "; ".join(book.get("tags", [])), Field.Store.YES))
            year = book.get("published_year")
            if year is not None:
                doc.add(IntPoint("year", int(year)))
                doc.add(StoredField("year", int(year)))
            doc.add(StoredField("url", book.get("url", "")))
            # This field stays identical in plain/enriched experiments when originals are supplied.
            if original_csv and book["id"] not in originals:
                raise ValueError("Book missing from original comparison corpus: " + book["id"])
            original = originals.get(book["id"], book)
            doc.add(TextField("contents", legacy_text(original), Field.Store.NO))
            wiki_book = book.get("wiki_book_match", {})
            wiki = wiki_book.get("wiki", {}) if wiki_book.get("status") == "matched" else {}
            doc.add(StringField('wiki_match_status', wiki_book.get('status', 'unmatched') if include_wiki else 'disabled', Field.Store.YES))
            doc.add(StringField('wiki_match_method', 'title_exact' if include_wiki and wiki else 'none', Field.Store.YES))
            doc.add(StoredField('wiki_book_title', wiki.get('title', '') if include_wiki else ''))
            people = [p["wiki"] for p in book.get("wiki_people", []) if p.get("status") == "matched"]
            wiki_text = []
            if include_wiki:
                for field, key in (("wiki_summary", "summary"), ("wiki_plot", "plot")):
                    doc.add(TextField(field, wiki.get(key, ""), Field.Store.YES))
                    wiki_text.append(wiki.get(key, ""))
                doc.add(TextField("wiki_genres", "; ".join(wiki.get("genres", [])), Field.Store.YES))
                wiki_text += wiki.get("genres", [])
                for role, field in (("author", "wiki_author_bio"), ("editor", "wiki_editor_bio")):
                    role_people = {p["wiki"]["id"]: p["wiki"] for p in book.get("wiki_people", [])
                                   if p["status"] == "matched" and p["role"] == role}
                    biographies = " ".join(p["summary"] for p in role_people.values())
                    doc.add(TextField(field, biographies, Field.Store.NO))
                    wiki_text.append(biographies)
                doc.add(StringField("wiki_language", normalize(wiki.get("language", "")), Field.Store.YES))
                doc.add(TextField("wiki_publisher", wiki.get("publisher", ""), Field.Store.YES))
                if wiki.get("first_publication_year") is not None:
                    doc.add(IntPoint("wiki_year", wiki["first_publication_year"]))
                    doc.add(StoredField("wiki_year", wiki["first_publication_year"]))
                for entity in ([wiki] if wiki else []) + people:
                    doc.add(StringField("wiki_id", entity["id"], Field.Store.YES))
                doc.add(StoredField("wiki_sources", json.dumps([p["url"] for p in ([wiki] if wiki else []) + people])))
            doc.add(TextField("wiki", " ".join(wiki_text), Field.Store.NO))
            doc.add(StoredField("wiki_enabled", "yes" if include_wiki else "no"))
            writer.addDocument(doc)
            count += 1
        writer.commit()
    finally:
        writer.close(); directory.close(); analyzer.close()
    report = {"documents": count, "seconds": round(time.perf_counter() - started, 3),
              "lucene": lucene.VERSION, "analyzer": "StandardAnalyzer", "similarity": "ClassicSimilarity",
              "wiki_enabled": include_wiki, "input": input_path, "original_csv": original_csv}
    Path(index_path, "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/enriched")
    parser.add_argument("--index", default="indexes/enriched")
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--original-csv", help="Original metadata for controlled comparison of the contents field")
    args = parser.parse_args()
    build_index(args.input, args.index, not args.plain, args.original_csv)
