"""Compare the unchanged old index, Lucene without wiki and Lucene with wiki."""
import argparse
import csv
import statistics
import time
from pathlib import Path
from legacy import indexer
from search import BookSearch

QUERIES = ['fiction romance', 'war tribunal', 'Rosika Storey', 'Agatha Christie', 'detective mystery']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-index', default='/input/old/index.tsv')
    parser.add_argument('--plain-index', default='indexes/plain')
    parser.add_argument('--wiki-index', default='indexes/enriched')
    parser.add_argument('--output', default='reports/comparison.tsv')
    parser.add_argument('--queries', help='Optional UTF-8 text file: one query per line')
    args = parser.parse_args()
    indexer.INDEX_TSV = args.old_index
    docs, index = indexer.nacitaj_index()
    plain = BookSearch(args.plain_index, wiki=False)
    enriched = BookSearch(args.wiki_index)
    queries = Path(args.queries).read_text(encoding='utf-8').splitlines() if args.queries else QUERIES
    engines = {
        'old_classic': lambda q: [{'id': i, 'title': docs[i][0], 'score': s} for i,s in indexer.vyhladaj(docs,index,q,'classic',10)],
        'old_smooth': lambda q: [{'id': i, 'title': docs[i][0], 'score': s} for i,s in indexer.vyhladaj(docs,index,q,'smooth',10)],
        'lucene_plain': plain.search,
        'lucene_wiki': enriched.search,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(args.output, 'w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(['query','engine','rank','book_id','title','score','median_ms','relevant_manual'])
            for query in queries:
                if not query.strip(): continue
                for name, search in engines.items():
                    search(query)  # Warm up separately; index loading is not query time.
                    times = []
                    for _ in range(5):
                        start = time.perf_counter(); rows = search(query)
                        times.append((time.perf_counter()-start)*1000)
                    elapsed = round(statistics.median(times), 3)
                    for rank, row in enumerate(rows,1):
                        writer.writerow([query,name,rank,row['id'],row['title'],row['score'],elapsed,''])
                    if not rows: writer.writerow([query,name,0,'','','',elapsed,''])
                    print(query, name, 'top:', rows[0]['title'] if rows else '-', 'ms:', elapsed)
    finally:
        plain.close(); enriched.close()
    print('Written:', args.output, '(relevance must be judged manually; scores are not comparable across engines)')


if __name__ == '__main__':
    main()
