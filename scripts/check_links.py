"""Verify actual PDF link rectangles and destinations against Typst references.

Every resolved cross-reference of the book (`@pr:…`, `@eq:…`, `@bib:…`, ...)
records its own position and its target's in metadata. For this project's
unrotated, full-page Typst export, Typst puts the destination 10pt above its
target. Validate positions, not just page existence.
"""
import hashlib
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import NameObject, TextStringObject


def pt(value):
    assert value.endswith('pt'), value
    return float(value[:-2])


def set_link_descriptions(document, references):
    """Coordinate links need the printed page label, not a physical-page
    tooltip. Only references that carry a `description` are touched."""
    for ref in references:
        if not ref.get('description'):
            continue
        source = ref['position']
        page = document.pages[source['page'] - 1]
        height = float(page.mediabox.height)
        matches = []
        for item in page.get('/Annots', []):
            annotation = item.get_object()
            if annotation.get('/Subtype') != '/Link':
                continue
            rect = [float(v) for v in annotation['/Rect']]
            if (abs(rect[0] - pt(source['x'])) < 0.03 and
                    height - rect[3] - 0.03 <= pt(source['y'])
                    <= height - rect[1] + 0.03):
                matches.append(annotation)
        assert len(matches) == 1, 'Expected one link for its description'
        matches[0][NameObject('/Contents')] = TextStringObject(
            ref['description'])


def check_links(pdf, references):
    reader = PdfReader(pdf)
    page_ids = {p.indirect_reference.idnum: i+1
                for i, p in enumerate(reader.pages)}
    records = []
    for number, page in enumerate(reader.pages, 1):
        assert page.get('/Rotate', 0) == 0
        assert list(page.cropbox) == list(page.mediabox)
        assert list(page.mediabox)[:2] == [0, 0]
        height = float(page.mediabox.height)
        for ref in page.get('/Annots', []):
            annotation = ref.get_object()
            if annotation.get('/Subtype') != '/Link':
                continue
            action = annotation.get('/A', {}).get_object() \
                if '/A' in annotation else {}
            if action.get('/S') == '/URI':
                continue
            assert not action or action.get('/S') == '/GoTo', \
                'Unexpected link action'
            dest = annotation.get('/Dest', action.get('/D'))
            if hasattr(dest, 'get_object'):
                dest = dest.get_object()
            if isinstance(dest, str):
                dest = reader.named_destinations[dest].dest_array
            assert len(dest) == 5 and dest[1] == '/XYZ', dest
            target_page = page_ids[dest[0].idnum]
            target_height = float(reader.pages[target_page-1].mediabox.height)
            assert 0 <= float(dest[3]) <= target_height
            rect = [float(v) for v in annotation['/Rect']]
            assert 0 <= rect[0] < rect[2] <= float(page.mediabox.width)
            assert 0 <= rect[1] < rect[3] <= height
            records.append({
                'from_page': number, 'to_page': target_page,
                'rect_top_origin': [rect[0], height-rect[3], rect[2],
                                    height-rect[1]],
                'target_top_origin': target_height-float(dest[3]),
                'type': '/XYZ',
                'description': str(annotation.get('/Contents', ''))})
    checked = []
    absent = []
    for ref in references:
        target = ref.get('target')
        if not ref['resolved']:
            absent.append(target)
            continue
        source = ref['position']
        destination = ref['target-position']
        matching = [r for r in records if r['from_page'] == source['page']
                    and abs(r['rect_top_origin'][0]-pt(source['x'])) < 0.03
                    and r['rect_top_origin'][1]-0.03 <= pt(source['y'])
                    <= r['rect_top_origin'][3]+0.03]
        assert len(matching) == 1, (f'{target}: expected one clickable '
                                    f'rectangle at {source}; got {matching}')
        actual = matching[0]
        assert actual['to_page'] == destination['page'], \
            f'{target}: wrong target page'
        expected_top = max(0, pt(destination['y'])
                           -ref.get('destination-offset-pt', 10))
        assert abs(actual['target_top_origin']-expected_top) < 0.03, \
            f'{target}: wrong target height'
        if ref.get('description'):
            assert actual['description'] == ref['description'], \
                f'{target}: wrong accessible page description'
        checked.append({'target': target, **actual})
    return {'sha256': hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),
            'status': 'passed', 'internal_link_annotations': len(records),
            'semantic_references_checked': len(checked),
            'bibliography_references_checked': sum(
                r['target'].startswith('bib:') for r in checked),
            'references': checked,
            'unresolved_targets': sorted(set(absent)),
            'links': records,
            'viewer_click_test': 'not performed; actual PDF objects checked'}


def link_at(records, position):
    """The link rectangles that start at a recorded position."""
    return [r for r in records if r['from_page'] == position['page']
            and abs(r['rect_top_origin'][0] - pt(position['x'])) < 0.03
            and r['rect_top_origin'][1] - 0.03 <= pt(position['y'])
            <= r['rect_top_origin'][3] + 0.03]


def check_hint_links(links, hint_links):
    """A problem and its hint (the book's solution) lead to each other.

    `hint_links` are the records the book leaves (statements.typ,
    `hint-link`): the head of every problem, "Problem 3.", and every number
    of a hint, "3." or each of "1, 2.". The head of a problem with a hint
    must be a link to the hint, every number of a hint a link back to the
    head of its problem, both to the recorded place; the head of a problem
    without a hint must be no link. `links` is the report of `check_links`.
    """
    records = links['links']
    counts = {'problems_with_hint': 0, 'problems_without_hint': 0,
              'hint_numbers': 0}
    failures = []
    for item in hint_links:
        name = (item['from'] + ' '
                + '.'.join(str(n) for n in item['number']))
        found = link_at(records, item['position'])
        target = item.get('target-position')
        if target is None:
            if found:
                failures.append(f'{name}: a problem without a hint is a link')
            counts['problems_without_hint'] += 1
            continue
        if len(found) != 1:
            failures.append(f'{name}: expected one link at {item["position"]}'
                            f', got {len(found)}')
            continue
        actual = found[0]
        expected_top = max(0, pt(target['y']) - 10)
        if actual['to_page'] != target['page'] \
                or abs(actual['target_top_origin'] - expected_top) >= 0.03:
            failures.append(f'{name}: leads to page {actual["to_page"]}, not '
                            f'to the place on page {target["page"]}')
            continue
        counts['problems_with_hint' if item['from'] == 'problem'
               else 'hint_numbers'] += 1
    assert not failures, failures[:12]
    # Every problem that a hint names has its head linked to that hint.
    named = {tuple(i['number']) for i in hint_links if i['from'] == 'hint'}
    linked = {tuple(i['number']) for i in hint_links
              if i['from'] == 'problem' and i.get('target-position')}
    assert named <= linked, sorted(named - linked)[:12]
    return counts
