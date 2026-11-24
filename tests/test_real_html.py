"""Regression checks on 20 actual book pages, without network access."""
import os
import unittest
from pathlib import Path
from extractors import extract_book

HTML = Path(os.environ.get('HTML_INPUT', '/input/html'))


@unittest.skipUnless(HTML.is_dir(), 'Optional original HTML is missing; supply input/html to run these tests')
class RealHtmlTests(unittest.TestCase):
    def test_twenty_pages(self):
        files = sorted(HTML.glob('*.html'))[:20]
        self.assertEqual(len(files), 20, 'Expected the mounted original html directory')
        for path in files:
            with self.subTest(file=path.name):
                book = extract_book(path.read_text(encoding='utf-8'), path.name)
                self.assertIsNotNone(book)
                self.assertEqual(book['id'], path.stem)
                self.assertTrue(book['title'])
                self.assertEqual(len(book['authors']), len(set(book['authors'])))

    def test_known_multiple_authors(self):
        book = extract_book((HTML/'20071202.html').read_text(encoding='utf-8'))
        self.assertEqual(len(book['authors']), 2)
        self.assertIn('Michelant, H. (Henri)', book['authors'])

    def test_known_editor(self):
        book = extract_book((HTML/'20090213.html').read_text(encoding='utf-8'))
        self.assertEqual(book['authors'], [])
        self.assertEqual(book['editors'], ['Lang, Andrew'])
