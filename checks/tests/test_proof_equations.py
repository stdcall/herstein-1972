"""Local equation numbers follow their proof and remain distinct targets."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = '''#import "content/book-style.typ": book-style
#import "content/statements.typ": lemma, proof
#show: book-style
#counter(heading).update((5, 1))
$ a = a $ <eq:global-first>
#lemma[First assertion.] <lem:first>
#proof(equations: [@lem:first])[
  $ b = b $ <eq:first-proof-first>
  $ c = c $ <eq:first-proof-second>
]
#lemma[Second assertion.] <lem:second>
#proof(equations: [@lem:second])[
  $ d = d $ <eq:second-proof-first>
]
$ e = e $ <eq:global-second>
See @eq:first-proof-first, @eq:first-proof-second,
@eq:second-proof-first and @eq:global-second.
'''


class ProofEquations(unittest.TestCase):
    def test_local_sequences_and_outer_counter(self):
        with tempfile.TemporaryDirectory(prefix='herstein-equations-') as tmp:
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
            result = subprocess.run([
                'typst', 'eval', *args, 'query(<numbered>).map(it => it.value)',
                '--in', str(root/'sample.typ'), '--format', 'json'],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            equations = [r['number'] for r in json.loads(result.stdout)
                         if r.get('family') == 'eq']
            self.assertEqual(equations, [
                [5, 1, 1], [5, 1, 1, 1], [5, 1, 1, 2],
                [5, 1, 2, 1], [5, 1, 2]])


if __name__ == '__main__':
    unittest.main()
