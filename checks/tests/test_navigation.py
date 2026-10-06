"""Named index targets must supply both destinations and printed pages."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from check_links import check_links

FIXTURE = '''#import "content/book-style.typ": book-style
#import "content/main-defs.typ": idx
#import "content/statements.typ": theorem
#import "content/index-style.typ": book-index
#show: book-style
#set page(numbering: "1")
#counter(heading).update((1, 1))
#theorem[The object begins on the first page.] <th:probe>
#block[The term's definition.] <term:probe>
See @term:probe[the definition].
#pagebreak()
Marks are deliberately placed on the second page.
#idx("Probe", target: <th:probe>)
#idx("Probe", target: <th:probe>, index: "name")
#book-index("Subject Index") <part:subject-index>
#book-index("Name Index", index: "name") <part:name-index>
'''


class NavigationTargets(unittest.TestCase):
    def test_subject_aliases_merge_and_keep_both_destinations(self):
        fixture = '''#import "content/book-style.typ": book-style
#import "content/main-defs.typ": idx
#import "content/index-style.typ": book-index
#show: book-style
#set page(numbering: "1")
First mention. #idx("Голди теорема")
#pagebreak()
Second mention. #idx("Голди", "теорема")
#book-index("Subject Index")
'''
        with tempfile.TemporaryDirectory(prefix='herstein-index-alias-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            (root/'editorial.bib').write_text('')
            (root/'sample.typ').write_text(fixture)
            result = subprocess.run([
                'typst', 'compile', '--root', str(root),
                '--ignore-system-fonts', '--font-path',
                str(root/'assets/fonts'), str(root/'sample.typ'),
                str(root/'sample.pdf')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            with pymupdf.open(root/'sample.pdf') as doc:
                text = ' '.join(doc[2].get_text().split())
                self.assertIn('Голди, теорема 1, 2', text)
                self.assertEqual(text.count('Голди'), 1)
                links = doc[2].get_links()
                self.assertEqual(sorted(link['page'] for link in links), [0, 1])

    def test_late_marks_link_to_object_and_print_its_page(self):
        with tempfile.TemporaryDirectory(prefix='herstein-navigation-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            (root/'editorial.bib').write_text('')
            (root/'sample.typ').write_text(FIXTURE)
            args = ['--root', str(root), '--ignore-system-fonts',
                    '--font-path', str(root/'assets/fonts')]
            result = subprocess.run([
                'typst', 'compile', *args, str(root/'sample.typ'),
                str(root/'sample.pdf')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            expression = ('query(metadata).map(it => '
                          '(value: it.value, position: it.location().position()))')
            result = subprocess.run([
                'typst', 'eval', *args, expression, '--in',
                str(root/'sample.typ'), '--format', 'json'],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            references = [d['value'] for d in data
                          if isinstance(d['value'], dict)
                          and d['value'].get('kind') == 'cross-reference']
            probe = [r for r in references if r['target'] == 'th:probe']
            self.assertEqual(len(probe), 2)
            self.assertTrue(all(r['target-position']['page'] == 1 for r in probe))
            self.assertTrue(all(r['position']['page'] >= 3 for r in probe))
            report = check_links(root/'sample.pdf', references)
            self.assertEqual(report['semantic_references_checked'], 3)
            with pymupdf.open(root/'sample.pdf') as doc:
                for page in (doc[2], doc[3]):
                    self.assertIn('Probe 1', ' '.join(page.get_text().split()))


if __name__ == '__main__':
    unittest.main()
