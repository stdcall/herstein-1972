"""Insertion changes native markers/references, never their semantic targets."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import pymupdf

from test_navigation import ROOT, check_links

FIXTURE = '''#import "content/book-style.typ": book-style
#import "content/statements.typ": theorem, part-list, statement-part, example-item
#show: book-style
#counter(heading).update((1, 1))
INSERT_SECTION
INSERT_THEOREM
#theorem[Target theorem.] <th:target>
INSERT_EQUATION
$ z = z $ <eq:target>
#pagebreak()
#part-list[
  INSERT_PART
  + #statement-part[Target part.] <part:target>
]
INSERT_EXAMPLE
#example-item[Target example.] <exm:target>
#pagebreak()
Theorem reference: @th:target.
Equation reference: @eq:target.
Part reference: @part:target.
Example reference: @exm:target[].
'''


class CounterMutations(unittest.TestCase):
    def test_proof_equation_reference_uses_its_local_number(self):
        with tempfile.TemporaryDirectory(prefix='herstein-proof-equations-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            (root/'editorial.bib').write_text('')
            (root/'sample.typ').write_text(
                '#import "content/book-style.typ": book-style\n'
                '#import "content/statements.typ": theorem, proof\n'
                '#show: book-style\n'
                '#counter(heading).update((4, 4))\n'
                '#theorem[Target theorem.] <th:proof-target>\n'
                '#proof(equations: [@th:proof-target])[\n'
                '  $ x = x $ <eq:proof-target>\n'
                '  Inside: @eq:proof-target.\n]\n'
                'Outside: @eq:proof-target.\n')
            args = ['--root', str(root), '--ignore-system-fonts',
                    '--font-path', str(root/'assets/fonts')]
            for command in (
                ['compile', *args, str(root/'sample.typ'), str(root/'sample.pdf')],
                ['eval', *args, 'query(<cross-reference>).map(it => it.value)',
                 '--in', str(root/'sample.typ'), '--format', 'json'],
            ):
                result = subprocess.run(['typst', *command], capture_output=True,
                                        text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
            refs = json.loads(result.stdout)
            equations = [r for r in refs if r['target'] == 'eq:proof-target']
            self.assertEqual([r['printed'] for r in equations], ['1', '4.4.1.1'])
            self.assertEqual(check_links(root/'sample.pdf', refs)
                             ['semantic_references_checked'], len(refs))
            with pymupdf.open(root/'sample.pdf') as doc:
                text = ' '.join(doc[0].get_text().split())
                self.assertIn('Inside: (1).', text)
                self.assertIn('Outside: (4.4.1.1).', text)

    def test_insertions_shift_pdf_numbers_and_preserve_targets(self):
        with tempfile.TemporaryDirectory(prefix='herstein-counter-mutations-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            (root/'editorial.bib').write_text('')
            args = ['--root', str(root), '--ignore-system-fonts',
                    '--font-path', str(root/'assets/fonts')]
            for mutated in (False, True):
                with self.subTest(insertions=mutated):
                    source = FIXTURE
                    inserts = {
                        'SECTION': '== Inserted section',
                        'THEOREM': '#theorem[Preceding theorem.] <th:preceding>',
                        'EQUATION': '$ y = y $ <eq:preceding>',
                        'PART': '+ #statement-part[Preceding part.] <part:preceding>',
                        'EXAMPLE': '#example-item[Preceding example.] <exm:preceding>',
                    }
                    for key, value in inserts.items():
                        source = source.replace('INSERT_'+key, value if mutated else '')
                    (root/'sample.typ').write_text(source)
                    def run(command):
                        result = subprocess.run(['typst', *command],
                                                capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, '')
                        return result.stdout
                    run(['compile', *args, str(root/'sample.typ'), str(root/'sample.pdf')])
                    references = json.loads(run([
                        'eval', *args, 'query(<cross-reference>).map(it => it.value)',
                        '--in', str(root/'sample.typ'), '--format', 'json']))
                    number = '1.2.2' if mutated else '1.1.1'
                    part = '2' if mutated else '1'
                    self.assertEqual({r['target']: r['printed'] for r in references},
                                     {'th:target': number, 'eq:target': number,
                                      'part:target': part, 'exm:target': part})
                    self.assertEqual(check_links(root/'sample.pdf', references)
                                     ['semantic_references_checked'], 4)
                    with pymupdf.open(root/'sample.pdf') as doc:
                        text = [' '.join(p.get_text().split()) for p in doc]
                        self.assertIn(f'Теорема {number}. Target theorem.', text[0])
                        self.assertIn(f'({part})', text[0])
                        self.assertIn(f'({part}) Target part.', text[1])
                        self.assertIn(f'Theorem reference: {number}.', text[2])
                        self.assertIn(f'Equation reference: ({number}).', text[2])
                        self.assertIn(f'Part reference: ({part}).', text[2])
                        self.assertIn(f'Example reference: {part}.', text[2])
                        self.assertIn(f'({part}) Target example.', text[1])
                        for ref in references:
                            page = 2 if ref['target'] in ('part:target', 'exm:target') else 1
                            self.assertEqual(ref['target-position']['page'], page)
                            # Link to the target's line, not an earlier inserted item.
                            needle = {'th:target': 'Target theorem.',
                                      'eq:target': f'({part})',
                                      'part:target': 'Target part.',
                                      'exm:target': 'Target example.'}[ref['target']]
                            matches = doc[page-1].search_for(needle)
                            self.assertEqual(len(matches), 1)
                            y = float(ref['target-position']['y'][:-2])
                            self.assertLess(abs(y-matches[0].y0), 15)


if __name__ == '__main__':
    unittest.main()
