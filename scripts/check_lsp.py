"""Check the editor's navigation in the book with the Tinymist LSP.

The source scanner of the lint tells the references in the text from the
examples in comments. Every reference of
the sources is a native `@` reference (`@th:algebraic-closure-same-derived`;
a hint names its problems by references too, `#hint[@pr:…][…]`), and every
label is written literally after its object (`#theorem[…] <th:…>`). The check
asks Tinymist, with `content/main.typ` selected as the main file by the lock
database as in the editor:

- for the definition of every referenced label, which must be exactly the
  literal label `<th:…>` at its object (the range of the label, on one line);
- how many of these jumps go to another file of the book;
- for completion after `@` and after a prefix `@th:`, which must offer the
  label.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lint_typst import CITED, MARKUP, scan  # noqa: E402

REFERENCE = re.compile(r'@([a-z][\w-]*:[\w:.-]+)')
# Wrappers of references of older setups; the book writes `@label`.
LEGACY = re.compile(
    r'#(?:xref|book-ref|eq-ref|equation-ref|section-ref|chapter-ref|'
    r'part-ref|theorem-ref|lemma-ref|proposition-ref|corollary-ref|'
    r'figure-ref|sec-ref|ch-ref|sec-ch-ref|fig-ref|idx-ref|number-ref)'
    r'\s*\(\s*(?:<|")')


def position(text, offset):
    before = text[:offset]
    return {'line': before.count('\n'), 'character':
            len(before.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}


def references(root):
    """(file, label, offset inside the label) of the first reference to each
    label in the text of the sources (not in comments or strings), and of
    every reference by which a hint names its problem or a restatement its
    theorem (`#hint[@pr:…]`, `prime: [@th:…]`)."""
    cases, seen = [], set()
    for path in sorted((root / 'content').rglob('*.typ')):
        text = path.read_text()
        kinds, _ = scan(text)
        if re.match(r'\d\d-', path.name):
            prose = ''.join(c for c, k in zip(text, kinds)
                            if k not in ('/',))
            assert LEGACY.search(prose) is None, (
                str(path.relative_to(root)), 'Use a native @label reference')
        heads = [m.span() for m in re.finditer(
            r'#hint\[[^\]]*\]|\bprime:\s*\[[^\]]*\]', text)]
        for m in REFERENCE.finditer(text):
            if kinds[m.start()] not in (MARKUP, CITED):
                continue
            label = m.group(1).rstrip('.:')
            named = any(a <= m.start() < b for a, b in heads)
            if label not in seen or named:
                cases.append((path, label, m.start(1) + 1))
                seen.add(label)
    assert cases, 'No native references found'
    return cases


@contextmanager
def editor_registration(root):
    """Restore the local registration even if compilation fails."""
    lock = root / 'tinymist.lock'
    saved = lock.read_bytes() if lock.exists() else None
    try:
        yield
    finally:
        if saved is None:
            lock.unlink(missing_ok=True)
        else:
            lock.write_bytes(saved)


def check(root=ROOT):
    cases = references(root)
    with editor_registration(root), tempfile.TemporaryFile() as log, \
            tempfile.TemporaryDirectory() as tmp:
        # The lock database (tinymist.lock) names content/main.typ as the
        # main file of every chapter, as for the editor.
        subprocess.run(['tinymist', 'compile', '--save-lock', '--root', '.',
                        '--font-path', 'assets/fonts', 'content/main.typ',
                        str(Path(tmp) / 'book.pdf')], cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=log)
        process = subprocess.Popen(['tinymist', 'lsp'], cwd=root.parent,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log)
        inbox = queue.Queue()
        events = []
        serial = 0

        def receive():
            while True:
                headers = {}
                while line := process.stdout.readline():
                    if line == b'\r\n':
                        break
                    k, v = line.decode().split(':', 1)
                    headers[k.lower()] = v.strip()
                if not headers:
                    return
                inbox.put(json.loads(process.stdout.read(
                    int(headers['content-length']))))

        threading.Thread(target=receive, daemon=True).start()

        def send(method, params, request=True):
            nonlocal serial
            serial += 1
            message = {'jsonrpc': '2.0', 'method': method, 'params': params}
            if request:
                message['id'] = serial
            data = json.dumps(message).encode()
            process.stdin.write(f'Content-Length: {len(data)}\r\n\r\n'
                                .encode() + data)
            process.stdin.flush()
            if request:
                while True:
                    reply = inbox.get(timeout=90)
                    if reply.get('id') == serial:
                        assert 'error' not in reply, reply
                        return reply.get('result')
                    events.append(reply)

        opened = set()

        def open_document(path):
            if path in opened:
                return
            send('textDocument/didOpen', {'textDocument': {
                'uri': path.as_uri(), 'languageId': 'typst', 'version': 1,
                'text': path.read_text()}}, request=False)
            opened.add(path)

        try:
            send('initialize', {
                'processId': os.getpid(), 'rootUri': root.as_uri(),
                'capabilities': {'textDocument': {
                    'definition': {'linkSupport': True}}},
                'initializationOptions': {
                    'rootPath': str(root), 'compileStatus': 'enable',
                    'fontPaths': [str(root / 'assets/fonts')],
                    'projectResolution': 'lockDatabase'}})
            send('initialized', {}, request=False)
            # A chapter is opened first: the main file must be chosen for it.
            first = cases[0][0]
            open_document(first)
            send('workspace/executeCommand', {
                'command': 'tinymist.focusMain', 'arguments': [str(first)]})
            while True:
                event = events.pop(0) if events else inbox.get(timeout=90)
                if event.get('method') == 'tinymist/compileStatus':
                    status = event['params']['status']
                    assert status != 'compileError', event
                    if status == 'compileSuccess':
                        assert event['params']['path'] == \
                            '/content/main.typ', event
                        break
            failures = []
            cross_file = 0
            for path, label, offset in cases:
                open_document(path)
                result = send('textDocument/definition', {
                    'textDocument': {'uri': path.as_uri()},
                    'position': position(path.read_text(), offset)})
                if not result or len(result) != 1:
                    failures.append((str(path.relative_to(root)), label,
                                     result))
                    continue
                target = result[0]
                destination = Path(unquote(urlparse(target['targetUri'])
                                           .path))
                region = target['targetSelectionRange']
                if region['start']['line'] != region['end']['line']:
                    failures.append((label, 'multi-line selection', target))
                    continue
                line = destination.read_text().splitlines()[
                    region['start']['line']]
                encoded = line.encode('utf-16-le')
                selected = encoded[2 * region['start']['character']:
                                   2 * region['end']['character']
                                   ].decode('utf-16-le')
                if selected != '<' + label + '>':
                    failures.append((label,
                                     str(destination.relative_to(root)),
                                     selected))
                cross_file += destination != path
            assert not failures, json.dumps(failures[:12], ensure_ascii=False,
                                            indent=2)
            assert cross_file, 'No reference to another file was checked'
            # Completion is requested in real markup: a probe appended to a
            # file that has a reference, after `@` and after `@prefix:`.
            path, label, _ = next(c for c in cases
                                  if re.match(r'\d\d-', c[0].name))
            original = path.read_text()
            for version, prefix in enumerate(
                    ('@', '@' + label.split(':')[0] + ':'), 2):
                probe = original + '\n#let navigation-completion = ['
                start = len(probe)
                modified = probe + prefix + ']\n'
                send('textDocument/didChange', {
                    'textDocument': {'uri': path.as_uri(),
                                     'version': version},
                    'contentChanges': [{'text': modified}]}, request=False)
                reply = send('textDocument/completion', {
                    'textDocument': {'uri': path.as_uri()},
                    'position': position(modified, start + len(prefix)),
                    'context': {'triggerKind': 1}})
                items = reply.get('items', []) if isinstance(reply, dict) \
                    else reply
                assert any(i['label'] == label for i in items or []), prefix
            send('shutdown', None)
            send('exit', None, request=False)
            process.wait(timeout=10)
            print(f'Tinymist: {len(cases)} exact label destinations '
                  f'({cross_file} cross-file); main file and completion OK')
            return {'labels': len(cases), 'cross_file': cross_file}
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()


if __name__ == '__main__':
    check()
