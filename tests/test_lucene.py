import tempfile
import unittest
import os
from pathlib import Path
from lucene_index import build_index
from search import BookSearch


class LuceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        path = str(Path(cls.temp.name) / 'index')
        build_index(os.environ.get('DEMO_ENRICHED', 'data/demo/enriched'), path)
        cls.engine = BookSearch(path)

    @classmethod
    def tearDownClass(cls):
        cls.engine.close()
        cls.temp.cleanup()

    def test_phrase_and_field(self):
        self.assertEqual([r['id'] for r in self.engine.search('title:"The Test Book"')], ['10000001'])

    def test_wiki_enrichment(self):
        self.assertEqual({r['id'] for r in self.engine.search('wiki_plot:zeppelin')}, {'10000001', '10000002'})

    def test_boolean_fuzzy_and_range(self):
        self.assertEqual(len(self.engine.search('title:missing OR title:wrong')), 2)
        self.assertEqual({r['id'] for r in self.engine.search('title:tset~1')}, {'10000001','10000006','10000007'})
        self.assertEqual(len(self.engine.search('', year_from=1920, year_to=1920, tag='mystery')), 5)
        self.assertEqual(self.engine.search('', year_from=1921), [])
        self.assertEqual(len(self.engine.search('', year_from=1919, year_to=1919, wiki_year=True)), 2)
        self.assertEqual(len(self.engine.search('', author='Alice Example')), 3)
        self.assertEqual(self.engine.search('', author='Not An Author'), [])
        with self.assertRaises(ValueError):
            self.engine.search('', year_from=1930, year_to=1900)

    def test_title_method_and_type_filter(self):
        self.assertEqual({r['id'] for r in self.engine.search('wiki_match_method:title_exact')},
                         {'10000001','10000002','10000005','10000011'})
        row = self.engine.search('book_id:10000005')[0]
        self.assertEqual(row['wiki_book_title'], 'Wrong Author')
        self.assertEqual(row['wiki_match_status'], 'matched')


if __name__ == '__main__':
    unittest.main()
