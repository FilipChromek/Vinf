"""Create explicitly synthetic data for a reproducible end-to-end test."""
from pathlib import Path
import os
from tests.test_extractors import html_book, wiki_page

root = Path(os.environ.get('DEMO_ROOT', 'data/demo'))
(root / 'html').mkdir(parents=True, exist_ok=True)
books = [('10000001', 'The Test Book', 'Example, Alice'), ('10000002', 'Old Title', 'Example, Alice'),
         ('10000003', 'Missing Book', 'Unknown, Nobody'), ('10000004', 'Shared Story', 'Example, Alice'),
         ('10000005', 'Wrong Author', 'Other, Bob')]
for book_id, title, author in books:
    (root / 'html' / (book_id + '.html')).write_text(html_book(book_id, title, author), encoding='utf-8')
pages = [wiki_page(10, 'The Test Book (novel)', '{{Infobox book|name=The Test Book|author=[[Alice Example]]|genre=Mystery|pub_date=1919}}\nA synthetic story about a zeppelin.\n== Plot ==\nA detective boards a zeppelin.'),
         wiki_page(11, 'Old Title', '', redirect='The Test Book (novel)'),
         wiki_page(12, 'Alice Example', '{{Infobox writer|name=Alice Example}}\nAlice is a fictional novelist used in tests.'),
         wiki_page(13, 'Shared Story (novel)', '{{Infobox book|name=Shared Story|author=[[Alice Example]]}}\nOne book.'),
         wiki_page(14, 'Shared Story (book)', '{{Infobox book|name=Shared Story|author=[[Alice Example]]}}\nAnother book.'),
         wiki_page(15, 'Wrong Author', '{{Infobox book|name=Wrong Author|author=[[Alice Example]]}}\nWrong author.'),
         wiki_page(16, 'Talk:Ignore', '{{Infobox book|name=Ignore}}', namespace=1)]
extra_books = [('10000006', 'Book The Test', 'Example, A.'),
               ('10000007', 'The Test', 'Example, A.'),
               ('10000008', 'Movie Title', 'Example, A.'),
               ('10000009', 'Person Title', 'Example, A.'),
               ('10000010', 'Unlisted Work', 'Scientist, Case'),
               ('10000011', 'Poem Title', 'Example, A.')]
for book_id, title, author in extra_books:
    (root/'html'/(book_id+'.html')).write_text(html_book(book_id, title, author).replace('1920','1900'),encoding='utf-8')
pages += [wiki_page(20, 'Movie Title', '{{Infobox film|name=Movie Title}}\nA film.'),
          wiki_page(21, 'Person Title', '{{Infobox writer|name=Person Title}}\nA writer.'),
          wiki_page(22, 'Case Scientist', '{{Infobox scientist|name=Case Scientist|occupation=Physicist}}\nA scientist.'),
          wiki_page(23, 'Poem Title', '{{Infobox poem|name=Poem Title|author=[[Different Author]]}}\nA poem.')]
(root / 'wiki.xml').write_text('<mediawiki>\n' + '\n'.join(pages) + '\n</mediawiki>', encoding='utf-8')
print('Synthetic fixtures created in', root)
