"""Compile the Lean checks of checks/lean-proofs.json and audit their axioms.

Every listed file is compiled on its own with `lake env lean FILE`. It must
compile without errors or warnings, its `#print axioms` lines must cover
exactly the declarations listed for it, and these may depend only on
propext, Classical.choice and Quot.sound. Every passage label of a record
must be written in the book's Typst sources (content/), the records must list
every file of checks/lean/Herstein/, and the root module must import
exactly these files.

Where `lake env lean` runs:
* in CI (the default): in checks/lean, after `lake build` there;
* locally: in a prebuilt mathlib checkout of the pinned commit, given by
  `--mathlib PATH` or the environment variable LEAN_MATHLIB. Nothing is
  built, updated or downloaded; the toolchain and the mathlib commit of the
  checkout must match checks/lean/lean-toolchain and lake-manifest.json.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

LEAN_DIR = Path(__file__).resolve().parent
ROOT = LEAN_DIR.parents[1]
MANIFEST = ROOT / 'checks' / 'lean-proofs.json'
CONTENT = ROOT / 'content'
PACKAGE = 'Herstein'
ALLOWED = {'propext', 'Classical.choice', 'Quot.sound'}
KEYS = {'file', 'declarations', 'book', 'limitations', 'passages'}
# `passages` binds a proof to the text of the book: the labels of the
# statements, formulas and hints whose claims it checks (`pr:…`, `eq:…`,
# `hint:…`). When such a passage or the proof changes, review their
# correspondence; the check makes sure only that the labels exist.
AXIOMS = re.compile(r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]"
                    r"|does not depend on any axioms)")
DIAGNOSTIC = re.compile(r'^\S.*?:\d+:\d+: (error|warning)', re.MULTILINE)
LABEL = re.compile(r'<([\w:.-]+)>')
# The style files quote labels in their comments (`#theorem[…] <th:…>`).
COMMENT_LINE = re.compile(r'^[ \t]*//.*$', re.MULTILINE)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_name(path):
    return '.'.join(path.relative_to(LEAN_DIR).with_suffix('').parts)


def written_labels(content=CONTENT):
    """The labels written in the Typst sources, outside comment lines."""
    return {label for path in content.rglob('*.typ')
            for label in LABEL.findall(COMMENT_LINE.sub('', path.read_text()))}


def passage_problems(record, labels):
    passages = record['passages']
    problems = []
    if not passages or len(set(passages)) != len(passages):
        problems.append(f'{record["file"]}: empty or repeated passages')
    for label in passages:
        if label not in labels:
            problems.append(f'{record["file"]}: no label <{label}> in content/')
    return problems


def load_records():
    records = json.loads(MANIFEST.read_text())
    labels = written_labels()
    problems = []
    seen = set()
    for record in records:
        if set(record) != KEYS:
            problems.append(f'{record.get("file")}: keys {sorted(record)}')
            continue
        declarations = record['declarations']
        if not declarations or len(set(declarations)) != len(declarations):
            problems.append(f'{record["file"]}: empty or repeated declarations')
        if seen & set(declarations):
            problems.append(f'{record["file"]}: declarations listed twice')
        seen |= set(declarations)
        path = (ROOT / record['file']).resolve()
        if not path.is_file() or LEAN_DIR / PACKAGE not in path.parents:
            problems.append(f'{record["file"]}: not a file of checks/lean/{PACKAGE}')
        problems += passage_problems(record, labels)
    listed = {(ROOT / r['file']).resolve() for r in records}
    present = {p.resolve() for p in (LEAN_DIR / PACKAGE).rglob('*.lean')}
    for path in sorted(present - listed):
        problems.append(f'{path.relative_to(ROOT)}: not listed in lean-proofs.json')
    root = (LEAN_DIR / f'{PACKAGE}.lean').read_text()
    imports = set(re.findall(r'^import (\S+)', root, re.MULTILINE))
    if imports != {module_name(p) for p in listed if LEAN_DIR in p.parents}:
        problems.append(f'{PACKAGE}.lean does not import exactly the listed files')
    return records, problems


def check_local_pins(mathlib):
    """The local checkout must be the pinned toolchain and mathlib commit."""
    problems = []
    ours = (LEAN_DIR / 'lean-toolchain').read_text().strip()
    theirs = (mathlib / 'lean-toolchain').read_text().strip()
    if ours != theirs:
        problems.append(f'toolchain {theirs} in {mathlib}, pinned {ours}')
    manifest = json.loads((LEAN_DIR / 'lake-manifest.json').read_text())
    pinned = next(p['rev'] for p in manifest['packages'] if p['name'] == 'mathlib')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=mathlib, text=True,
                          capture_output=True, check=True).stdout.strip()
    if head != pinned:
        problems.append(f'mathlib commit {head} in {mathlib}, pinned {pinned}')
    return problems


def audit(record, output, returncode):
    problems = []
    if returncode != 0:
        problems.append(f'lean exited with {returncode}')
    for match in DIAGNOSTIC.finditer(output):
        problems.append(f'compiler {match[1]}')
    if 'sorryAx' in output:
        problems.append('sorryAx')
    found = {}
    for match in AXIOMS.finditer(output):
        name = match[1]
        if name in found:
            problems.append(f'axioms of {name} printed twice')
        found[name] = {a.strip() for a in (match[2] or '').split(',') if a.strip()}
    expected = set(record['declarations'])
    if set(found) != expected:
        missing = sorted(expected - set(found))
        extra = sorted(set(found) - expected)
        problems.append(f'#print axioms: missing {missing}, unlisted {extra}')
    for name, axioms in found.items():
        if axioms - ALLOWED:
            problems.append(f'{name} uses {sorted(axioms - ALLOWED)}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--mathlib', type=Path, default=os.environ.get('LEAN_MATHLIB'),
                        help='prebuilt mathlib checkout (default: $LEAN_MATHLIB; '
                             'unset: run in checks/lean as in CI)')
    parser.add_argument('--lake', default=os.environ.get('LAKE') or shutil.which('lake')
                        or str(Path.home() / '.elan' / 'bin' / 'lake'))
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()

    records, problems = load_records()
    if args.mathlib:
        cwd = Path(args.mathlib).expanduser().resolve()
        problems += check_local_pins(cwd)
    else:
        cwd = LEAN_DIR
    if problems:
        sys.exit('\n'.join(['Lean check records:'] + problems))

    # The files must not change while they are compiled.
    compiled = {r['file']: sha256(ROOT / r['file']) for r in records}
    failed = False
    total = 0
    for record in records:
        path = ROOT / record['file']
        run = subprocess.run([args.lake, 'env', 'lean', str(path)], cwd=cwd, text=True,
                             capture_output=True, timeout=args.timeout)
        output = run.stdout + run.stderr
        problems = audit(record, output, run.returncode)
        if problems:
            failed = True
            print(f'FAIL {record["file"]}')
            for problem in problems:
                print(f'  {problem}')
            print(output)
        else:
            total += len(record['declarations'])
            print(f'ok   {record["file"]}: {len(record["declarations"])} declarations')
    changed = [f for f, digest in compiled.items() if sha256(ROOT / f) != digest]
    if changed:
        failed = True
        print(f'changed during the run: {changed}')
    if failed:
        sys.exit(1)
    print(f'{len(records)} files, {total} declarations: only {sorted(ALLOWED)}')


if __name__ == '__main__':
    main()
