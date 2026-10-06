"""Check the subject index marks, `#idx(..path)`, placed in the text.

A mark is `metadata((kind: "index-mark", path: ("Element", "nilpotent")))`:
the path of the entry in the index of the book, heading first. The page
numbers come from where the marks stand, so there is nothing to compare with
the printed index; what remains is what free-text marks get wrong on their
own. An older single-term form (`term`, optional `sub`) is still read, so a
change of the helper's signature does not silently empty the index.
"""
from collections import defaultdict
import re


def marks(metadata):
    for item in metadata:
        value = item.get('value', item)
        if isinstance(value, dict) and value.get('kind') == 'index-mark':
            yield value, item.get('position') or value.get('position')


def entry_path(value):
    path = value.get('path')
    if path is None and 'term' in value:
        sub = value.get('sub')
        path = [value['term']] + (sub if isinstance(sub, list)
                                  else [sub] if sub else [])
    return path


def spelling_key(level):
    return ' '.join(level.split()).casefold()


def index_checks(metadata, *, final=True):
    """Errors and warnings of the marks; an empty index is an error only in
    the finished book."""
    errors, warnings = [], []
    forms = defaultdict(set)
    count = 0
    for value, position in marks(metadata):
        where = f' (PDF page {position["page"]})' if position else ''
        path = entry_path(value)
        if isinstance(path, str):
            path = [path]
        if not isinstance(path, list) or not path:
            errors.append('an index mark carries no path' + where)
            continue
        if not all(isinstance(level, str) and level.strip() for level in path):
            errors.append(f'index path {path!r} has an empty level' + where)
            continue
        if any(level != level.strip() or re.search(r'\s{2,}', level)
               for level in path):
            errors.append(f'index path {path!r} has stray whitespace' + where)
        count += 1
        # A typo in a mark fails nothing by itself: it quietly splits one
        # entry into two that sort next to each other. Catch the near-miss
        # at every level of the path.
        for depth in range(1, len(path) + 1):
            prefix = tuple(path[:depth])
            forms[(value.get('index', 'subject'),
                   *tuple(spelling_key(p) for p in prefix))].add(prefix)
    if not count:
        (errors if final else warnings).append(
            'the index is empty: no #idx marks in the text')
    reported = set()
    for key, spellings in sorted(forms.items(), key=lambda kv: len(kv[0])):
        if len(spellings) < 2 or any(key[:d] in reported
                                     for d in range(1, len(key))):
            continue
        reported.add(key)
        errors.append('one index entry spelled several ways: '
                      + ', '.join(' / '.join(s) for s in sorted(spellings)))
    return errors, warnings
