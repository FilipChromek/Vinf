"""Export readable join evidence for consultation 3, with no invented matches."""
import argparse
import csv
from pathlib import Path
from records import read_books


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/enriched')
    parser.add_argument('--output', default='reports')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with (output/'book_links.tsv').open('w',encoding='utf-8',newline='') as book_file, (output/'person_links.tsv').open('w',encoding='utf-8',newline='') as person_file:
        books = csv.writer(book_file,delimiter='\t')
        people = csv.writer(person_file,delimiter='\t')
        books.writerow(['book_id','title','authors','editors','status','wiki_id','wiki_title','wiki_url','original_year','wiki_year','candidate_ids'])
        people.writerow(['book_id','name','role','status','wiki_id','wiki_title','wiki_url','candidate_ids'])
        for book in read_books(args.input):
            match = book.get('wiki_book_match', {})
            wiki = match.get('wiki', {})
            books.writerow([book['id'],book['title'],'; '.join(book.get('authors',[])),'; '.join(book.get('editors',[])),match.get('status'),wiki.get('id'),wiki.get('title'),wiki.get('url'),book.get('published_year'),wiki.get('first_publication_year'),'; '.join(match.get('candidate_ids',[]))])
            for person in book.get('wiki_people',[]):
                wiki = person.get('wiki',{})
                people.writerow([book['id'],person['name'],person['role'],person['status'],wiki.get('id'),wiki.get('title'),wiki.get('url'),'; '.join(person.get('candidate_ids',[]))])
    print('Join evidence written to', output)


if __name__ == '__main__':
    main()
