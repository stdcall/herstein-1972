"""Build the book, its no-notes edition and the corrections sheet, and check
every PDF before it replaces the previous one.

Bookmarks keep the reader's zoom: each outline destination is rewritten to
`[page /XYZ left top null]`. `left = null` would keep the horizontal
position as well, but MuPDF-based viewers drop the vertical target when left
is null (checked with PyMuPDF 1.27.2.3: `/XYZ null 300 null` resolves to no
point, `/XYZ 0 300 null` to the heading), so the left edge comes from
`pdf_navigation.outline_left` in config/project.json, 0. Zoom stays null:
the view keeps its scale.

Page labels are Typst's own, from `page(numbering: ...)`: the cover without
a folio, preliminary pages 2–8 with selected folios suppressed, and the body
in Arabic from 9. They are validated, not rewritten.

Typst does not see system fonts; a Typst font warning fails the build, and
every PDF is checked to contain no font other than those in the book's font
directories (not even one bundled with Typst) and no missing glyph.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

import pymupdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, FloatObject, NameObject, NullObject
from check_links import check_hint_links, check_links, set_link_descriptions
from check_whitespace import check_whitespace
from lint_typst import (lint, input_hashes, evaluate, tool_versions,
                        unresolved_references, write_unresolved, from_roman)
from project import settings, stage, tool_env, cache_path, typst_inputs

ROOT = Path(__file__).resolve().parents[1]
SUBSET_TAG = re.compile(r'^[A-Z]{6}\+')


def run(args):
    result = subprocess.run(args, cwd=ROOT, env=tool_env(ROOT),
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed:\n{result.stdout}\n'
                           f'{result.stderr}')
    # A missing font family or math font is only a warning in Typst.
    if re.search(r'^warning: .*font', result.stderr, re.MULTILINE):
        raise RuntimeError(f'{args[0]}: Typst font warning:\n{result.stderr}')
    return result


def book_font_names():
    """PostScript names (OpenType name ID 6) of the font files of the book."""
    names = set()
    for directory in settings()['font_paths']:
        for path in sorted((ROOT/directory).rglob('*')):
            if path.suffix.lower() not in {'.otf', '.ttf'}:
                continue
            data = path.read_bytes()
            for index in range(struct.unpack_from('>H', data, 4)[0]):
                tag, _, table, _ = struct.unpack_from('>4sIII', data,
                                                      12 + 16*index)
                if tag != b'name':
                    continue
                _, count, strings = struct.unpack_from('>3H', data, table)
                for record in range(count):
                    platform, _, _, name_id, length, offset = \
                        struct.unpack_from('>6H', data, table + 6 + 12*record)
                    if name_id == 6:
                        start = table + strings + offset
                        names.add(data[start:start+length].decode(
                            'utf-16-be' if platform in (0, 3) else 'latin-1'))
    if not names:
        raise ValueError('No fonts found in '
                         + ', '.join(settings()['font_paths']))
    return names


def check_fonts(pdf, label):
    """Fail if the PDF has a font outside the book's fonts or a missing
    glyph."""
    allowed = book_font_names()
    found = defaultdict(dict)  # problem -> {PDF page: text set in the font}
    for page in pymupdf.open(pdf):
        number, foreign = page.number + 1, {}
        for _, _, kind, name, _, encoding, *_ in page.get_fonts(full=True):
            name = SUBSET_TAG.sub('', name)
            if kind == 'Type0':  # a composite font's name ends in its encoding
                name = name.removesuffix(f'-{encoding}')
            if name not in allowed:
                foreign[name] = found[f'font {name} is not a book font']
                foreign[name][number] = ''
        text = ''
        for span in page.get_texttrace():
            chars = ''.join(chr(c) if c > 0 else '?'
                            for c, *_ in span['chars'])
            chars = chars.replace('\xad', '-')
            # MuPDF shortens the font names of spans.
            for name, pages in foreign.items():
                if name.startswith(span['font']):
                    pages[number] += chars
            if any(name.startswith(span['font']) for name in allowed):
                for index, (_, glyph, *_) in enumerate(span['chars']):
                    if glyph == 0:
                        context = (text + chars[:index])[-40:]
                        found['no book font has the glyph after '
                              f'"{context}"'][number] = ''
            text += chars
    if found:
        raise ValueError(f'{label}:' + ''.join(
            f'\n  {problem}: ' + ', '.join(
                f'PDF page {page}' + (f' "{sample[:30]}"' if sample else '')
                for page, sample in list(pages.items())[:8]
            ) + (f' and {len(pages) - 8} more pages' if len(pages) > 8
                 else '')
            for problem, pages in found.items()))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def accessibility_signature(reader):
    """Compare the tagged structure and embedded fonts across finalization."""
    from pypdf.generic import IndirectObject, StreamObject, BooleanObject
    seen = {}
    page_ids = {p.indirect_reference.idnum: i
                for i, p in enumerate(reader.pages)}
    embedded = set()
    structures = set()

    def canonical(value):
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if value.idnum in page_ids:
                return ['page', page_ids[value.idnum]]
            if key in seen:
                return ['ref', seen[key]]
            seen[key] = len(seen)
            return ['object', seen[key], canonical(value.get_object())]
        if isinstance(value, dict):
            if value.get('/Type') == '/StructElem':
                structures.add(value.indirect_reference.idnum)
            for key in ['/FontFile', '/FontFile2', '/FontFile3']:
                if key in value:
                    embedded.add(hashlib.sha256(
                        value[key].get_data()).hexdigest())
            result = {str(k): canonical(v) for k, v in sorted(value.items())
                      if k not in ('/Length', '/Filter', '/DecodeParms')}
            if isinstance(value, StreamObject):
                result['decoded_stream_sha256'] = hashlib.sha256(
                    value.get_data()).hexdigest()
            return result
        if isinstance(value, (list, tuple)):
            return [canonical(v) for v in value]
        if isinstance(value, NullObject):
            return None
        if isinstance(value, BooleanObject):
            return value.value
        if isinstance(value, bytes):
            return value.hex()
        if isinstance(value, (int, float)):
            return float(value)
        return str(value)

    catalog = reader.trailer['/Root']
    assert '/StructTreeRoot' in catalog, 'PDF accessibility tags missing'
    tags = {key: catalog.raw_get(key) for key in
            ['/StructTreeRoot', '/MarkInfo', '/Lang'] if key in catalog}
    fonts = [page['/Resources'].get('/Font') for page in reader.pages]
    data = canonical([tags, fonts])
    assert embedded, 'No embedded fonts'
    return {'sha256': hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()).hexdigest(),
            'structure_elements': len(structures),
            'embedded_font_programs': len(embedded),
            'font_program_sha256': sorted(embedded)}


def normalize_outline_destinations(writer, original, *, left=None,
                                   chapter_starts=False):
    """Keep heading heights and inherited zoom in every nested bookmark."""
    count = 0

    def walk(ref):
        nonlocal count
        while ref:
            node = ref.get_object()
            holder, key = node, '/Dest'
            if '/A' in node:
                holder = node['/A'].get_object()
                if holder.get('/S') != '/GoTo':
                    raise ValueError('Unexpected non-GoTo outline action')
                key = '/D'
            dest = holder.get(key)
            if hasattr(dest, 'get_object'):
                dest = dest.get_object()
            if isinstance(dest, str):
                dest = original.named_destinations[dest].dest_array
            if not isinstance(dest, (list, ArrayObject)) or len(dest) != 5 \
                    or dest[1] != '/XYZ':
                raise ValueError(f'Unexpected destination: {dest}')
            x = NullObject() if left is None else FloatObject(left)
            top = dest[3]
            if chapter_starts and str(node.get('/Title', '')).startswith(('Chapter ', 'Глава ')):
                page = dest[0].get_object()
                assert page.get('/Rotate', 0) == 0
                assert list(page.get('/CropBox', page['/MediaBox'])) == list(page['/MediaBox'])
                top = FloatObject(page['/MediaBox'][3])
            holder[NameObject(key)] = ArrayObject([
                dest[0], NameObject('/XYZ'), x, top, NullObject()])
            count += 1
            if node.get('/First'):
                walk(node['/First'])
            ref = node.get('/Next')

    if '/Outlines' in writer.root_object:
        walk(writer.root_object['/Outlines'].get('/First'))
    return count


def page_label_problems(labels, scheme=None):
    """Page labels as Typst sets them, checked for sense.

    Unnumbered pages (the cover, blank pages) carry an empty label. The
    numbered ones form at most one roman run and then one Arabic run.
    The book's configuration gives the first Arabic label and preliminary
    sequence. Within a run the folio follows the physical page.
    """
    scheme = scheme or {}
    problems, runs = [], []
    initial = scheme.get('initial_labels', [])
    if labels[:len(initial)] != initial:
        problems.append('preliminary page labels differ from the book scheme')
    for index, label in enumerate(labels):
        if label == '':
            continue
        if label.isdecimal():
            style, value = 'arabic', int(label)
        elif re.fullmatch(r'[ivxlcdm]+|[IVXLCDM]+', label) \
                and from_roman(label):
            style, value = 'roman', from_roman(label)
        else:
            problems.append(f'PDF page {index + 1}: label {label!r} is '
                            'neither roman nor arabic')
            continue
        if runs and runs[-1][0] == style:
            expected = runs[-1][2] + index - runs[-1][1]
            if value != expected:
                problems.append(f'PDF page {index + 1}: label {label!r} '
                                f'breaks the {style} sequence')
                runs[-1] = [style, index, value]
        else:
            runs.append([style, index, value])
    styles = [run[0] for run in runs]
    if styles not in (['arabic'], ['roman', 'arabic']):
        problems.append(f'page numbering runs {styles}: expected roman front '
                        'matter (optional) and then one arabic run')
    arabic = [run for run in runs if run[0] == 'arabic']
    start = scheme.get('arabic_start', 1)
    if arabic and arabic[0][2] != start:
        problems.append(f'first Arabic label is {arabic[0][2]}, not {start}')
    return problems


def normalize_outlines(raw, output, *, label, book=True, references=()):
    """Write `output` from Typst's `raw` PDF: zoom-preserving bookmarks,
    link descriptions; everything else checked unchanged. `label` names the
    PDF in the font check's errors."""
    original = PdfReader(raw)
    writer = PdfWriter(raw, incremental=True)
    # Coordinate links get the printed page label as their description,
    # not Typst's physical-page tooltip (index locators).
    set_link_descriptions(original, references)
    set_link_descriptions(writer, references)
    preserved = accessibility_signature(original)
    left = settings()['pdf_navigation']['outline_left']
    count = normalize_outline_destinations(writer, original, left=left,
                                          chapter_starts=book)
    assert '/OpenAction' not in writer.root_object
    tmp = Path(output).with_suffix('.tmp.pdf')
    writer.write(tmp)
    check_fonts(tmp, label)
    checked = PdfReader(tmp)
    assert accessibility_signature(checked) == preserved, \
        'Tags or embedded fonts changed'
    labels = checked.page_labels
    if book:
        problems = page_label_problems(labels, settings().get('page_labels'))
        assert not problems, 'Page labels: ' + '; '.join(problems)
    records = []

    def validate(items, depth=0):
        for item in items:
            if isinstance(item, list):
                validate(item, depth+1)
                continue
            dest = item.dest_array
            assert len(dest) == 5 and dest[1] == '/XYZ'
            assert (isinstance(dest[2], NullObject) if left is None
                    else float(dest[2]) == left)
            assert isinstance(dest[4], NullObject), 'Bookmark sets a zoom'
            page = checked.get_destination_page_number(item)
            assert page is not None and 0 <= page < len(checked.pages)
            assert 0 <= float(dest[3]) <= float(checked.pages[page].mediabox.top)
            records.append({'title': item.title, 'depth': depth,
                            'pdf_page': page+1, 'page_label': labels[page],
                            'top': float(dest[3]), 'left': left, 'zoom': None,
                            'type': 'XYZ'})

    validate(checked.outline)
    assert len(records) == count
    assert len(original.pages) == len(checked.pages)
    for before, after in zip(original.pages, checked.pages):
        assert list(before.mediabox) == list(after.mediabox)
        assert list(before.cropbox) == list(after.cropbox)
        assert before.get('/Rotate', 0) == after.get('/Rotate', 0)
        assert before.get_contents().get_data() == \
            after.get_contents().get_data()
        assert len(before.get('/Annots', [])) == len(after.get('/Annots', []))
    text = '\n'.join(p.extract_text() for p in checked.pages)
    phrases = settings().get('required_text', []) if book else []
    for phrase in phrases:
        assert phrase in text, f'Required text missing from the PDF: {phrase}'
    assert '\N{REPLACEMENT CHARACTER}' not in text and '\x00' not in text
    assert sum(len(p.images) for p in checked.pages) == 0, \
        'Unexpected raster image in the new setting'
    tmp.replace(output)
    return {'pdf_pages': len(checked.pages), 'bookmark_count': count,
            'accessibility_and_fonts_unchanged': preserved,
            'page_labels': labels, 'bookmarks': records,
            'page_streams_unchanged_after_outline_normalization': True,
            'geometry_and_annotation_counts_unchanged': True,
            'raster_images': 0, 'text_search_checks': phrases,
            'viewer_zoom_test': 'not performed; PDF objects validated'}


def output_path(notes=True):
    output = ROOT/settings()['output']
    return output if notes else output.with_name(output.stem +
                                                 '.no-notes.pdf')


def ensure_lint(fingerprint):
    """Run the lint unless it has passed on exactly these inputs."""
    path = cache_path(ROOT)/'typst-lint.json'
    if path.exists() and (cache_path(ROOT)/'document.json').exists():
        report = json.loads(path.read_text())
        if report.get('status') == 'passed' and \
                report.get('fingerprint') == fingerprint:
            return
    if lint()['status'] != 'passed':
        raise SystemExit('Lint failed; PDF was not replaced.')


def build(force=False, thorough=False, exported=None, notes=True):
    """Build the book (`notes=False`: the edition without editorial notes)."""
    cache = cache_path(ROOT)
    cache.mkdir(parents=True, exist_ok=True)
    variant = '' if notes else '.no-notes'
    output = output_path(notes)
    # A fresh clone has no build/ yet (it is ignored by Git); the
    # intermediates are in the cache, not there.
    output.parent.mkdir(parents=True, exist_ok=True)
    current_stage = stage()
    fingerprint = {'sources': input_hashes(ROOT), 'tools': tool_versions(),
                   'stage': current_stage}
    state_path = cache/f'build-state{variant}.json'
    if not force and exported is None and state_path.exists() \
            and output.exists():
        state = json.loads(state_path.read_text())
        if state['fingerprint'] == fingerprint and \
                state['pdf_sha256'] == digest(output):
            print('PDF is current: '+str(output.relative_to(ROOT)))
            return
    ensure_lint(fingerprint)
    start = time.perf_counter()
    raw = cache/f'book{variant}-raw.pdf'
    if exported is None:
        result = run(['typst', 'compile', *typst_inputs(notes=notes),
                      settings()['entry'], str(raw)])
        (cache/f'typst{variant}.log').write_text(result.stdout+result.stderr)
    else:
        if not exported.is_file():
            raise RuntimeError('Tinymist produced no PDF at '+str(exported)
                               + '; inspect its export task log.')
        shutil.copyfile(exported, raw)
    raw_reader = PdfReader(raw)
    assert '/StructTreeRoot' in raw_reader.trailer['/Root'], \
        'PDF accessibility tags missing'
    if notes:
        # The lint evaluated exactly these inputs a moment ago.
        document = json.loads((cache/'document.json').read_text())
    else:
        result, document = evaluate(ROOT, notes=False)
        if document is None:
            raise RuntimeError('typst eval failed:\n' + result.stderr)
    metadata = [x['value'] for x in document['metadata']
                if isinstance(x['value'], dict)]
    references = [x for x in metadata
                  if x.get('kind') in ('cross-reference', 'page-reference')]
    unresolved = unresolved_references(document, current_stage)
    if current_stage == 'final' and unresolved['count']:
        raise SystemExit('Unresolved references in the final stage: '
                         + ', '.join(t['target'] for t in unresolved['targets']))
    staged = cache/f'book{variant}-checked.pdf'
    report = normalize_outlines(raw, staged, label=output.name,
                                references=references)
    links = check_links(staged, references)
    # A problem's head leads to its hint and the hint's number back.
    links['hint_links'] = check_hint_links(
        links, [x for x in metadata if x.get('kind') == 'hint-link'])
    report['output_sha256'] = digest(staged)
    report['source_input_sha256'] = fingerprint['sources']
    report['tools'] = fingerprint['tools']
    report['stage'] = current_stage
    report['editorial_notes'] = notes
    report['unresolved_references'] = unresolved['count']
    if thorough:
        whitespace = check_whitespace(staged, report['bookmarks'])
        (cache/f'whitespace-report{variant}.json').write_text(
            json.dumps(whitespace, indent=2)+'\n')
        if whitespace['status'] != 'passed':
            print('Layout advisory (does not fail the build): bottom gaps on '
                  'PDF pages ' + str(whitespace['pages_requiring_review'])
                  + '; see ' + str(cache/f'whitespace-report{variant}.json'))
    assert fingerprint['sources'] == input_hashes(ROOT), \
        'Sources changed during build'
    shutil.move(staged, output)
    raw.unlink()
    (cache/f'pdf-report{variant}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (cache/f'internal-links{variant}.json').write_text(
        json.dumps(links, ensure_ascii=False, indent=2)+'\n')
    state_path.write_text(json.dumps({
        'fingerprint': fingerprint,
        'pdf_sha256': report['output_sha256']}, indent=2)+'\n')
    summary = {'pdf': str(output.relative_to(ROOT)),
               'pages': report['pdf_pages'],
               'bookmarks': report['bookmark_count'],
               'links': links['internal_link_annotations'],
               'references_checked': links['semantic_references_checked'],
               'hint_links': links['hint_links'],
               'unresolved_references': unresolved['count'],
               'seconds': round(time.perf_counter()-start, 2)}
    print(json.dumps(summary))
    if notes and unresolved['count']:
        _, path = write_unresolved(ROOT, document)
        print(f'{unresolved["count"]} unresolved references to '
              f'{len(unresolved["targets"])} targets ({current_stage}; '
              f'printed unlinked, listed in {path})')


def build_corrections():
    """The reader's list of corrections, typeset from corrections.json.

    `corrections_entry` (content/corrections.typ) reads corrections.json and
    marks every entry it prints with `#metadata((correction: <id>))`; the
    marks must name each id of corrections.json exactly once.
    """
    config = settings()
    cache = cache_path(ROOT)
    cache.mkdir(parents=True, exist_ok=True)
    entry = config['corrections_entry']
    if not (ROOT/entry).is_file():
        raise SystemExit(
            f'{entry} is missing: it typesets corrections.json for the reader '
            'and marks every entry with #metadata((correction: id)).')
    raw = cache/'corrections-raw.pdf'
    run(['typst', 'compile', *typst_inputs(), entry, str(raw)])
    expr = ('query(metadata).map(m => m.value).filter(v => type(v) == '
            'dictionary and "correction" in v).map(v => v.correction)')
    ids = json.loads(run(['typst', 'eval', *typst_inputs(), expr, '--in',
                          entry, '--format', 'json']).stdout)
    expected = [e['id'] for e in
                json.loads((ROOT/'corrections.json').read_text())['entries']]
    missing = sorted(set(expected) - set(ids))
    unknown = sorted(set(ids) - set(expected))
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    assert not (missing or unknown or repeated), (
        f'Correction list does not match corrections.json: missing {missing}, '
        f'unknown {unknown}, repeated {repeated}')
    output = ROOT/config['corrections_output']
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = cache/'corrections-checked.pdf'
    report = normalize_outlines(raw, staged, label=output.name, book=False)
    report['output_sha256'] = digest(staged)
    shutil.move(staged, output)
    (cache/'corrections-report.json').write_text(
        json.dumps(report, indent=2)+'\n')
    raw.unlink()
    print(f'Corrections: {len(ids)} entries; {report["pdf_pages"]} pages')
