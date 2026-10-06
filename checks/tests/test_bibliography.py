"""Check bibliography data through the actual compiler and PDF links."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

import pymupdf

ROOT = Path(__file__).resolve().parents[2]

FIXTURE = '''@article{Probe1964,
  author = {Original Author},
  title = {Original title},
  journal = {Original Journal},
  volume = {37},
  year = {1964},
  pages = {100-125},
  language = {english},
  doi = {10.1234/original-probe},
  related = {Related1965},
  annotation = {{author}, {title}, {journal}, {volume} ({year}), {pages}. Related: {Related1965.title}, {Related1965.pages}.},
}
@article{Related1965,
  author = {Related Author},
  title = {Related title},
  year = {1965},
  pages = {126-136},
  annotation = {{author}, {title}, {year}, {pages}.},
}
'''


class BibliographySource(unittest.TestCase):
    def test_backlinks_exclude_bibliography_references(self):
        with tempfile.TemporaryDirectory(prefix='herstein-bib-mentions-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            (root/'references.bib').write_text(FIXTURE)
            (root/'editorial.bib').write_text('')
            (root/'sample.typ').write_text(
                '#import "content/book-style.typ": book-style\n'
                '#import "content/statements.typ": bib-item\n'
                '#import "content/bibliography-style.typ": bib-description\n'
                '#show: book-style\n'
                '#set page(header: none, footer: none)\n'
                'First mention: @bib:Related1965.\n#pagebreak()\n'
                'Second mention: @bib:Related1965.\n#pagebreak()\n'
                '#bib-item[#bib-description("Probe1964") '
                'Related: @bib:Related1965.] <bib:Probe1964>\n'
                '#bib-item[#bib-description("Related1965") '
                'Bibliography-only: @bib:Probe1964.] <bib:Related1965>\n')
            args = ['--root', str(root), '--ignore-system-fonts',
                    '--font-path', str(root/'assets/fonts')]
            result = subprocess.run([
                'typst', 'compile', *args, str(root/'sample.typ'),
                str(root/'sample.pdf')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            result = subprocess.run([
                'typst', 'eval', *args,
                'query(metadata).map(it => it.value).filter(it => '
                'type(it) == dictionary and '
                'it.at("kind", default: none) == "page-reference")',
                '--in', str(root/'sample.typ'), '--format', 'json'],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            mentions = json.loads(result.stdout)
            self.assertEqual([m['target-position']['page'] for m in mentions],
                             [1, 2])
            with pymupdf.open(root/'sample.pdf') as doc:
                targets = [link['page'] for link in doc[2].get_links()
                           if link.get('kind') == pymupdf.LINK_GOTO]
                self.assertEqual(targets.count(0), 1)
                self.assertEqual(targets.count(1), 1)
                self.assertEqual(targets.count(2), 2)

    def test_data_changes_reach_text_and_links(self):
        with tempfile.TemporaryDirectory(prefix='herstein-bib-') as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'content', root/'content')
            shutil.copytree(ROOT/'assets/fonts', root/'assets/fonts')
            data = root/'references.bib'
            data.write_text(FIXTURE)
            (root/'editorial.bib').write_text('')
            (root/'sample.typ').write_text(
                '#import "content/book-style.typ": book-style\n'
                '#import "content/statements.typ": bib-item\n'
                '#import "content/bibliography-style.typ": '
                'bib-description, chapter-bibliography\n'
                '#show: book-style\n'
                '#set page(header: none, footer: none)\n'
                '#chapter-bibliography[Work: @bib:Probe1964.]\n'
                '#pagebreak()\n'
                '#bib-item[#bib-description("Probe1964")] <bib:Probe1964>\n')

            def compile_pdf(name):
                result = subprocess.run([
                    'typst', 'compile', '--root', str(root),
                    '--ignore-system-fonts', '--font-path',
                    str(root/'assets/fonts'), str(root/'sample.typ'),
                    str(root/name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '', result.stderr)
                with pymupdf.open(root/name) as doc:
                    text = ' '.join(' '.join(p.get_text().split()) for p in doc)
                    text = re.sub(r'\u00ad\s*', '', text)
                    links = {link['uri'] for page in doc
                             for link in page.get_links() if 'uri' in link}
                return text, links

            before, old_links = compile_pdf('before.pdf')
            for phrase in ('Original Author', 'Original title',
                           'Original Journal', '100-125', '126-136'):
                self.assertIn(phrase, before)
            self.assertIn('https://doi.org/10.1234/original-probe', old_links)
            self.assertEqual(before.count('Original title'), 2)
            changed = FIXTURE.replace('Original Author',
                                      'Author, Jr., Changed and Second Author')
            changed = changed.replace('Original title', 'Changed title')
            changed = changed.replace('journal = {Original Journal},',
                                      'journal = {Original Journal},\n'
                                      '  shortjournal = {Changed Journal},')
            changed = changed.replace('100-125', '9001-9002')
            changed = changed.replace('126-136', '9003-9004')
            changed = changed.replace('language = {english}',
                                      'language = {russian}')
            changed = changed.replace('original-probe', 'changed-probe')
            data.write_text(changed)
            after, new_links = compile_pdf('after.pdf')
            for phrase in ('Changed Author, Jr.', 'Changed title',
                           'Changed Journal', '9001-9002', '9003-9004',
                           'и Second Author'):
                self.assertIn(phrase, after)
            for phrase in ('Original Author', 'Original title',
                           'Original Journal', '100-125', '126-136'):
                self.assertNotIn(phrase, after)
            self.assertIn('https://doi.org/10.1234/changed-probe', new_links)
            self.assertEqual(after.count('Changed title'), 2)
            self.assertNotIn('https://doi.org/10.1234/original-probe', new_links)


if __name__ == '__main__':
    unittest.main()
