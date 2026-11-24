"""Verify Kod6 preservation, exact-title candidates and optionally both indexes."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from records import read_books


def coverage(books):
    matches = [b['wiki_book_match'] for b in books if b['wiki_book_match']['status'] == 'matched']
    works = {m['wiki']['id'] for m in matches}
    people = {p['wiki']['id'] for b in books for p in b['wiki_people'] if p['status'] == 'matched'}
    return {'books':len(books), 'matched_works':len(matches),
            'work_statuses':dict(Counter(b['wiki_book_match']['status'] for b in books)),
            'unique_work_articles':len(works), 'unique_person_articles':len(people),
            'unique_articles':len(works | people)}


def check_data():
    old_rows = list(read_books('/input/kod6/data/enriched'))
    rows = list(read_books('data/enriched'))
    old, new = {b['id']:b for b in old_rows}, {b['id']:b for b in rows}
    assert len(old) == len(old_rows) and len(new) == len(rows) and old.keys() == new.keys()
    candidates, keys = defaultdict(set), defaultdict(set)
    for row in read_books('data/enriched_book_candidates'):
        assert row['matched_key'] in new[row['book_id']]['title_keys']
        candidates[row['book_id']].add(row['wiki_id'])
        keys[row['book_id']].add(row['matched_key'])
    transitions = Counter()
    same_work = new_work = 0
    exported = []
    for book_id, before in old.items():
        after = new[book_id]
        # Includes complete wiki_people dictionaries, not just IDs or counts.
        assert {k:v for k,v in before.items() if k != 'wiki_book_match'} == {
            k:v for k,v in after.items() if k != 'wiki_book_match'}, 'Metadata or person link changed: '+book_id
        match = after['wiki_book_match']
        assert match['author_checked'] is False
        expected = candidates[book_id]
        if len(expected) == 1:
            assert match['status'] == 'matched' and match['wiki']['id'] in expected
            assert match['method'] == 'title_exact' and match['wiki']['kind'] == 'book'
            wiki = match['wiki']
            assert wiki['infobox_type'] in {'book','novel','novella','short story','poem','play'}
            previous = before['wiki_book_match']
            if previous['status'] == 'matched':
                assert previous['wiki']['id'] == wiki['id'], 'Existing unique work changed'
                same_work += 1
            else:
                new_work += 1
            exported.append([book_id,after['title'],'; '.join(after['authors'] + after['editors']),
                             wiki['id'],wiki['title'],'; '.join(wiki['authors']),
                             '; '.join(sorted(keys[book_id])),wiki['infobox_type'],
                             bool(set(after['author_keys']) & set(wiki['author_keys'])),wiki['url']])
        elif expected:
            assert match['status'] == 'ambiguous' and set(match['candidate_ids']) == expected
        else:
            assert match['status'] == 'unmatched'
        transitions[before['wiki_book_match']['status']+' -> '+match['status']] += 1
    report = {'passed':True, 'kod6':coverage(old_rows), 'kod11':coverage(rows),
              'original_metadata_and_all_person_links_identical':True,
              'exact_title_candidate_decisions_checked':True, 'literary_work_types_checked':True,
              'same_previously_matched_work':same_work, 'newly_matched_works':new_work,
              'work_transitions':dict(transitions)}
    Path('reports').mkdir(exist_ok=True)
    Path('reports/version_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with Path('reports/title_matches.tsv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t')
        writer.writerow(['book_id','title','source_authors_editors','wiki_id','wiki_title','wiki_authors',
                         'matched_keys','infobox_type','author_agrees_information_only','wiki_url'])
        writer.writerows(sorted(exported))
    print(json.dumps(report,indent=2))
    return rows


def check_indexes(books):
    from search import BookSearch
    from compare import QUERIES
    expected = {b['id']:b for b in books}
    for label in ('plain','enriched'):
        engine = BookSearch('indexes/'+label, wiki=label=='enriched')
        try:
            rows = engine.search('*:*',limit=len(books)+1)
            assert engine.reader.numDocs() == len(books) and len(rows) == len(books)
            assert {r['id'] for r in rows} == expected.keys()
            for row in rows:
                book = expected[row['id']]; match = book['wiki_book_match']
                if label == 'plain':
                    assert not row['wiki_sources'] and row['wiki_match_status'] == 'disabled'
                    continue
                assert row['wiki_match_status'] == match['status']
                assert row['wiki_match_method'] == ('title_exact' if match['status']=='matched' else 'none')
                entities = ([match['wiki']] if match['status']=='matched' else []) + [
                    p['wiki'] for p in book['wiki_people'] if p['status']=='matched']
                assert row['wiki_sources'] == [w['url'] for w in entities]
                assert row['wiki_book_title'] == match.get('wiki',{}).get('title','')
            if label == 'enriched':
                assert len(engine.search('wiki_match_method:title_exact',limit=len(books)+1)) == coverage(books)['matched_works']
        finally:
            engine.close()
    before, after = BookSearch('/input/kod6/indexes/plain',wiki=False), BookSearch('indexes/plain',wiki=False)
    try:
        for query in QUERIES:
            a = {r['id']:r['score'] for r in before.search(query,limit=10000)}
            b = {r['id']:r['score'] for r in after.search(query,limit=10000)}
            assert a.keys() == b.keys() and all(abs(score-b[key]) < 0.00001 for key,score in a.items()), query
    finally:
        before.close(); after.close()
    report={'passed':True,'documents_each':len(books),'stored_work_methods_and_all_wiki_sources_checked':True,
            'plain_search_ids_and_scores_preserved':True,'queries':QUERIES}
    Path('reports/real_index_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--indexes',action='store_true')
    args=parser.parse_args()
    books=check_data()
    if args.indexes: check_indexes(books)
