"""Console search: field queries, Boolean/phrase/fuzzy queries and numeric years."""
import argparse
import json
import os
import lucene
from text_utils import normalize


class BookSearch:
    def __init__(self, path, similarity="classic", wiki=True):
        if not lucene.getVMEnv():
            lucene.initVM(vmargs=["-Djava.awt.headless=true"])
        from java.nio.file import Paths
        from org.apache.lucene.analysis.standard import StandardAnalyzer
        from org.apache.lucene.index import DirectoryReader
        from org.apache.lucene.store import FSDirectory
        from org.apache.lucene.search import IndexSearcher
        from org.apache.lucene.search.similarities import ClassicSimilarity, BM25Similarity
        self.directory = FSDirectory.open(Paths.get(path))
        self.reader = DirectoryReader.open(self.directory)
        self.searcher = IndexSearcher(self.reader)
        self.searcher.setSimilarity(ClassicSimilarity() if similarity == "classic" else BM25Similarity())
        self.analyzer = StandardAnalyzer()
        self.wiki = wiki

    def search(self, text, limit=10, year_from=None, year_to=None, tag=None, wiki_year=False, author=None):
        from org.apache.lucene.queryparser.classic import QueryParser, QueryParserBase, MultiFieldQueryParser
        from org.apache.lucene.search import BooleanQuery, BooleanClause, MatchAllDocsQuery, TermQuery
        from org.apache.lucene.index import Term
        from org.apache.lucene.document import IntPoint
        if limit < 1:
            raise ValueError("Limit must be positive")
        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("Start year must not be greater than end year")
        # Field-specific syntax (title:, authors:, etc.) also works with this parser.
        parser = MultiFieldQueryParser(["contents", "wiki"], self.analyzer) if self.wiki else QueryParser("contents", self.analyzer)
        # Explicit base call avoids PyLucene's overloaded static MultiField parse method.
        query = QueryParserBase.parse(parser, text) if text.strip() else MatchAllDocsQuery()
        builder = BooleanQuery.Builder()
        builder.add(query, BooleanClause.Occur.MUST)
        if year_from is not None or year_to is not None:
            field = "wiki_year" if wiki_year else "year"
            builder.add(IntPoint.newRangeQuery(field, year_from if year_from is not None else -2147483648,
                                              year_to if year_to is not None else 2147483647), BooleanClause.Occur.FILTER)
        if tag:
            builder.add(TermQuery(Term("tag_exact", normalize(tag))), BooleanClause.Occur.FILTER)
        if author:
            builder.add(TermQuery(Term("author_exact", normalize(author))), BooleanClause.Occur.FILTER)
        hits = self.searcher.search(builder.build(), limit)
        stored = self.searcher.storedFields()
        output = []
        for hit in hits.scoreDocs:
            doc = stored.document(hit.doc)
            output.append({"id": doc.get("book_id"), "title": doc.get("title"), "authors": doc.get("authors"),
                           "year": doc.get("year"), "score": float(hit.score), "url": doc.get("url"),
                           "wiki_sources": json.loads(doc.get("wiki_sources") or "[]"),
                           "wiki_match_method": doc.get('wiki_match_method'),
                           "wiki_match_status": doc.get('wiki_match_status'),
                           "wiki_book_title": doc.get('wiki_book_title')})
        return output

    def close(self):
        self.reader.close(); self.directory.close(); self.analyzer.close()


def print_results(rows):
    if not rows:
        print("Nenasli sa vysledky.")
    for i, row in enumerate(rows, 1):
        print(f"\n{i}. {row['title']} ({row['year'] or '?'})\n   {row['authors']}\n   ID: {row['id']} | skore: {row['score']:.4f}\n   {row['url']}")
        for url in row["wiki_sources"]:
            print("   Wiki:", url)
        if row.get('wiki_book_title'):
            print('   Wiki dielo:', row['wiki_book_title'], '| presny nazov/alias; autor sa nekontroloval')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--query-env", action="store_true", help="Read VINF_QUERY (used by the Windows launcher)")
    parser.add_argument("--index", default="indexes/enriched")
    parser.add_argument("--similarity", choices=["classic", "bm25"], default="classic")
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--wiki-year", action="store_true")
    parser.add_argument("--tag")
    parser.add_argument("--author", help="Exact normalized full author name")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.query_env:
        args.query = os.environ["VINF_QUERY"]
    searcher = BookSearch(args.index, args.similarity, not args.plain)
    try:
        if args.query is not None:
            print_results(searcher.search(args.query, args.limit, args.year_from, args.year_to, args.tag, args.wiki_year, args.author))
        else:
            print('Priklady: title:"Two People" | authors:christie AND tags:mystery | title:interpoll~1')
            print("Prazdny vstup ukonci program. Interval rokov: --year-from / --year-to.")
            while True:
                try:
                    query = input("\nDopyt: ").strip()
                    if not query: break
                    print_results(searcher.search(query, args.limit, args.year_from, args.year_to, args.tag, args.wiki_year, args.author))
                except EOFError:
                    break
                except Exception as error:
                    print("Chyba dopytu:", error)
    finally:
        searcher.close()


if __name__ == "__main__":
    main()
