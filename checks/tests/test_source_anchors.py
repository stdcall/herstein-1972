"""Invisible index marks do not turn a new paragraph into a split sentence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from lint_typst import pitfall_checks, scan


class SourceAnchors(unittest.TestCase):
    def findings(self, text):
        kinds, ends = scan(text)
        return [f for f in pitfall_checks('content/44-crossed-products.typ',
                                        text, kinds, ends)
                if f['rule'] == 'T044']

    def test_completed_paragraph_with_index_mark(self):
        text = ('A complete sentence. <def:factor-set>\n'
                '#idx("Factor set", target: <def:factor-set>)\n\n'
                '#source(123)Let $f$, $g$ be factor sets.\n')
        self.assertEqual(self.findings(text), [])

    def test_incomplete_sentence_with_index_mark(self):
        text = ('This sentence continues\n#idx("Factor set")\n\n'
                '#source(123)on the next page.\n')
        self.assertEqual(len(self.findings(text)), 1)

    def test_completed_paragraph_with_footnote(self):
        text = ('A complete sentence.#footnote[An explanation.\n'
                '  — _Прим. перев._]\n\n'
                '#source(158)The next paragraph.\n')
        self.assertEqual(self.findings(text), [])

    def test_incomplete_sentence_with_footnote(self):
        text = ('This sentence continues#footnote[An explanation.\n'
                '  — _Прим. перев._]\n\n'
                '#source(158)on the next page.\n')
        self.assertEqual(len(self.findings(text)), 1)


if __name__ == '__main__':
    unittest.main()
