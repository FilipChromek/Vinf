import unittest
from extractors import extract_book, extract_wiki, infobox, clean_wiki
from text_utils import person_keys, title_keys


def html_book(book_id="12345678", title="The Test Book", author="Example, Alice", extra=""):
    return f'''<b>Book Details</b><table><tr><td>Title:</td><td>{title}</td></tr>
    <tr><td>Author:</td><td><a href="/csearch.php?author=x">{author}</a></td></tr>{extra}
    <tr><td>Published:</td><td>1920</td></tr><tr><td>Tags:</td><td><a href="/csearch.php?tags=mystery">mystery</a></td></tr>
    <tr><td>Description:</td><td>A quiet detective mystery.</td></tr></table>
    <input name="bookid" value="{book_id}"><b>Available Formats</b>'''


def wiki_page(page_id, title, text, namespace=0, redirect=None):
    from html import escape
    target = f'<redirect title="{escape(redirect, quote=True)}" />' if redirect else ""
    return f'<page><title>{escape(title)}</title><ns>{namespace}</ns><id>{page_id}</id>{target}<revision><id>9999999</id><text xml:space="preserve">{escape(text)}</text></revision></page>'


class ExtractionTests(unittest.TestCase):
    def test_repeated_authors_and_editor_are_separate(self):
        extra = '<tr><td>Author:</td><td><a href="/csearch.php?author=y">Other, Bob</a></td></tr><tr><td>Editor:</td><td><a href="/csearch.php?author=z">Editor, Eve</a></td></tr>'
        b = extract_book(html_book(extra=extra))
        self.assertEqual(b['authors'], ['Example, Alice', 'Other, Bob'])
        self.assertEqual(b['editors'], ['Editor, Eve'])
        self.assertEqual(len(b['people']), 3)

    def test_editor_not_silently_called_author(self):
        b = extract_book(html_book().replace('Author:', 'Editor:'))
        self.assertEqual(b['authors'], [])
        self.assertEqual(b['editors'], ['Example, Alice'])

    def test_catalog_page_skipped(self):
        self.assertIsNone(extract_book('<h1>Catalog</h1>'))

    def test_names_and_series(self):
        self.assertIn('lucy maud montgomery', person_keys('Montgomery, L. M. (Lucy Maud)'))
        self.assertIn('biggles of the interpol', title_keys('Biggles of the Interpol (Biggles #58)'))

    def test_infobox_nested_templates_and_link_pipes(self):
        kind, fields = infobox('{{Infobox book|name=Example|author=[[Alice Example|Alice]]|genre={{ubl|Mystery|Crime}}|pub_date={{start date|1920|2|3}}}}')
        self.assertEqual(kind, 'book')
        self.assertEqual(fields['author'], '[[Alice Example|Alice]]')
        self.assertEqual(fields['genre'], '{{ubl|Mystery|Crime}}')
        self.assertIn('1920', fields['pub_date'])

    def test_page_id_is_not_revision_id_and_plot_is_clean(self):
        page = wiki_page(42, 'Example', "{{Infobox book|name=Example|author=[[Alice Example]]|pub_date={{start date|1920|1|1}}}}\n'''Example''' is a novel.<ref>Citation</ref>\n== Plot ==\nA [[detective]] visits London.\n== Reception ==\nIgnore this.")
        p = extract_wiki(page)
        self.assertEqual(p['id'], '42')
        self.assertEqual(p['first_publication_year'], 1920)
        self.assertEqual(p['plot'], 'A detective visits London.')
        self.assertNotIn('Citation', p['summary'])

    def test_namespace_redirect_and_disambiguation(self):
        self.assertIsNone(extract_wiki(wiki_page(1, 'Talk:Example', '{{Infobox book}}', 1)))
        self.assertIsNone(extract_wiki(wiki_page(2, 'Example', '{{disambiguation}}')))
        p = extract_wiki(wiki_page(3, 'Alias', '', redirect='Real & True'))
        self.assertEqual(p['target'], 'Real & True')

    def test_person_and_non_writer(self):
        p = extract_wiki(wiki_page(10, 'Alice Example', '{{Infobox writer|name=Alice Example}}\nAlice writes novels.'))
        self.assertEqual(p['kind'], 'person')
        self.assertIsNone(extract_wiki(wiki_page(11, 'Someone', '{{Infobox person|occupation=footballer}}')))

    def test_clean_markup(self):
        self.assertEqual(clean_wiki("'''A''' [[Book|novel]] {{citation needed}} &amp; text"), 'A novel & text')


if __name__ == '__main__':
    unittest.main()
