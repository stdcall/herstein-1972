"""The reader's correction list has portable provenance and valid markup."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from lint_typst import MARKUP, from_roman, scan, view


class Corrections(unittest.TestCase):
    def test_required_fields_and_printed_pages(self):
        data = json.loads((ROOT/'corrections.json').read_text())
        self.assertEqual(set(data), {'entries'})
        fields = {'id', 'printed_page', 'section', 'place', 'original',
                  'corrected', 'reason', 'verified_by'}
        for n, entry in enumerate(data['entries'], 1):
            self.assertEqual(set(entry), fields)
            self.assertEqual(entry['id'], f'C{n:03d}')
            self.assertTrue(all(str(entry[f]).strip() for f in fields))
            self.assertNotEqual(entry['original'], entry['corrected'])
            page = entry['printed_page']
            if isinstance(page, int):
                self.assertTrue(1 <= page <= 191, entry['id'])
            else:
                self.assertRegex(page, r'^[ivxIVX]+$')
                self.assertTrue(1 <= from_roman(page.upper()) <= 12)

    def test_math_is_marked_as_math(self):
        formula = re.compile(r'(?<=\w)_(?=[\w(])|\^|\b(?:CC|RR|ZZ|QQ|HH)\b')
        for entry in json.loads((ROOT/'corrections.json').read_text())['entries']:
            for field in ('section', 'place'):
                self.assertNotRegex(entry[field], r'[$_^]')
            for field in ('original', 'corrected', 'reason'):
                markup = entry[field]
                kinds, _ = scan(markup)
                prose = re.sub(r'\\.', '  ', view(markup, kinds, (MARKUP,)))
                self.assertIsNone(formula.search(prose), (entry['id'], field))


if __name__ == '__main__':
    unittest.main()
