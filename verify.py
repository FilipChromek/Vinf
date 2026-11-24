"""Re-runnable integration test in its own temporary directory."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from records import read_books


def run(*command, env=None):
    subprocess.run(command, check=True, env=env)


def main():
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_extractors.py', '-v')
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_real_html.py', '-v')
    Path('data').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='check_', dir='data') as folder:
        root = Path(folder)
        env = dict(os.environ, DEMO_ROOT=str(root), DEMO_ENRICHED=str(root/'enriched'))
        run(sys.executable, '-m', 'tests.make_demo', env=env)
        # Force one XML page to cross the 1 MiB Hadoop split boundary.
        xml = root/'wiki.xml'
        content = xml.read_text(encoding='utf-8')
        content = content.replace('A synthetic story', '<!--' + 'x' * 2200000 + '-->A synthetic story')
        xml.write_text(content, encoding='utf-8')
        common = ['spark-submit', '--master', 'local[2]', '--driver-memory', '2g', 'spark_job.py']
        for step, options in [
            ('html', ['--html', str(root/'html')]),
            ('wiki', ['--dump', str(xml), '--split-mb', '1']),
            ('join', ['--books', str(root/'html_output'), '--wiki', str(root/'wiki_output')])]:
            output = root/'enriched' if step == 'join' else root/(step+'_output')
            run(*common, step, *options, '--output', str(output), '--partitions', '2', '--report', str(root/(step+'_stats.json')))
        books = {b['id']: b for b in read_books(root/'enriched')}
        assert len(books) == 11, 'A left join must preserve every book exactly once'
        assert books['10000001']['wiki_book_match']['status'] == 'matched'
        assert books['10000002']['wiki_book_match']['wiki']['id'] == '10', 'Redirect should resolve to canonical page'
        assert books['10000003']['wiki_book_match']['status'] == 'unmatched'
        assert books['10000004']['wiki_book_match']['status'] == 'ambiguous'
        assert books['10000005']['wiki_book_match']['status'] == 'matched', 'Work author must not decide title matching'
        for book_id in ('10000006','10000007','10000008','10000009','10000010'):
            assert books[book_id]['wiki_book_match']['status'] == 'unmatched', book_id
        assert books['10000011']['wiki_book_match']['wiki']['id'] == '23', 'Poems remain literary works as in Kod6'
        assert books['10000006']['wiki_people'][0]['status'] == 'unmatched', 'No new initials matching'
        assert books['10000010']['wiki_people'][0]['status'] == 'unmatched', 'A non-writer scientist is not an author candidate'
        assert books['10000001']['wiki_people'][0]['wiki']['id'] == '12'
        assert all(b['wiki_book_match']['author_checked'] is False for b in books.values())
        stats = json.loads((root/'wiki_stats.json').read_text())
        assert stats['input_partitions'] > 1
        assert stats['retained_pages_by_kind'] == {'book': 5, 'redirect': 1, 'person': 2}, 'No missing/duplicate split records'
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_lucene.py', '-v', env=env)
    Path('reports').mkdir(exist_ok=True)
    real_html_available = Path(os.environ.get('HTML_INPUT', '/input/html')).is_dir()
    Path('reports/local_tests.json').write_text(json.dumps({'passed': True,
        'real_html_tests': 'passed' if real_html_available else 'skipped: input/html not supplied',
        'real_html_pages': 20 if real_html_available else 0,
        'synthetic_books':11,
        'checks': ['title without author', 'literary-work types', 'no reordered or partial titles',
                   'original name matching without initials fallback', 'non-writer excluded',
                   'repeated authors', 'editors', 'nested infobox', 'XML input split boundary',
                   'join and ambiguity', 'Lucene phrase, fuzzy, Boolean, range']}), encoding='utf-8')
    print('All checks passed.')


if __name__ == '__main__':
    main()
