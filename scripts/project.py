#!/usr/bin/env python3
"""Project commands; formatting, layout and lint policy live in config files."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGES = ('draft', 'final')


def settings(root=ROOT):
    config = json.loads((root/'config/project.json').read_text())
    local = root/'config/local.json'
    if local.exists():
        config.update(json.loads(local.read_text()))
    return config


def layout_settings(root=ROOT):
    return json.loads((root/'config/page-layout.json').read_text())


def stage(root=ROOT):
    """`final` for the complete book; `draft` tolerates missing targets.

    Every Typst run gets it as `--input stage=...` (see main-defs.typ): in
    draft a reference whose target is missing prints unlinked and is
    reported; in the final stage it fails the lint and the build.
    """
    value = settings(root).get('stage', 'final')
    if value not in STAGES:
        raise SystemExit(f'config/project.json: stage must be one of {STAGES}, '
                         f'not {value!r}')
    return value


def typst_inputs(root=ROOT, *, notes=True):
    """`--input` arguments of every typst/tinymist run of this book."""
    args = ['--input', 'stage='+stage(root)]
    if not notes:
        # Editorial notes (#ed-note) switched off: the no-notes edition.
        args += ['--input', 'editorial-notes=off']
    return args


def cache_path(root=ROOT):
    """Build intermediates: raw PDFs, the lint and build reports, the build
    state. They live outside the tree (`cache` in config/project.json), so
    that build/ holds only the finished PDFs."""
    configured = os.environ.get('BOOK_BUILD_CACHE', settings(root).get('cache', '~/.cache/' + root.name))
    return Path(configured).expanduser()


def tool_env(root=ROOT):
    env = os.environ.copy()
    env['TYPST_ROOT'] = str(root)
    env['TYPST_FONT_PATHS'] = os.pathsep.join(
        str(root/p) for p in settings(root)['font_paths'])
    # Only the book's fonts: system fonts are ignored. Typst's bundled fonts
    # stay visible, so text the style does not cover lands in one of them and
    # the PDF font check (build.check_fonts) rejects it.
    env['TYPST_IGNORE_SYSTEM_FONTS'] = 'true'
    return env


def editor_settings(root=ROOT):
    return json.loads((root/'.vscode/settings.json').read_text())


def formatter_command(root=ROOT, *, check=False, inplace=False):
    # Typstyle 0.15.1 has no native configuration-file switch. Read the actual
    # Tinymist workspace settings, so editor and CLI share the same policy.
    config = editor_settings(root)
    prose_wrap = config['tinymist.formatterProseWrap']
    if not isinstance(prose_wrap, bool):
        raise ValueError('tinymist.formatterProseWrap must be a boolean')
    args = ['typstyle', '--line-width',
            str(config['tinymist.formatterPrintWidth']),
            '--indent-width', str(config['tinymist.formatterIndentSize']),
            '--wrap-text='+('fill' if prose_wrap else 'none')]
    if check:
        args.append('--check')
    if inplace:
        args.append('--inplace')
    return args + settings(root)['format_sources']


def editor_export_path(root=ROOT):
    """Where Tinymist writes the PDF of the book (`tinymist.outputPath`).

    The VS Code build task exports with Tinymist and then validates that very
    file, so the path is read from the same setting the editor uses.
    """
    pattern = editor_settings(root).get('tinymist.outputPath', '$dir/$name')
    if '$dir' in pattern:
        raise SystemExit('tinymist.outputPath: use $root and $name only')
    entry = Path(settings(root)['entry'])
    return Path(pattern.replace('$root', str(root))
                .replace('$name', entry.stem) + '.pdf')


def run(args):
    subprocess.run(args, cwd=ROOT, env=tool_env(), check=True)


def tests():
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'checks/tests',
         '-v'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=[
        'fmt', 'lint', 'build', 'build-no-notes', 'check', 'test',
        'corrections', 'clean', 'editor-prepare', 'editor-finish'])
    parser.add_argument('--force', action='store_true',
                        help='rebuild even when the PDF is current')
    args = parser.parse_args()
    os.chdir(ROOT)
    command = args.command
    if command == 'clean':
        shutil.rmtree(ROOT/'build', ignore_errors=True)
        shutil.rmtree(cache_path(), ignore_errors=True)
        return
    cache_path().mkdir(parents=True, exist_ok=True)
    if command == 'fmt':
        run(formatter_command(inplace=True))
        return
    if command == 'editor-prepare':
        from lint_typst import input_hashes
        editor_export_path().unlink(missing_ok=True)
        (cache_path()/'editor-inputs.json').write_text(
            json.dumps(input_hashes(ROOT)))
        return
    if command == 'editor-finish':
        from lint_typst import input_hashes
        before = json.loads((cache_path()/'editor-inputs.json').read_text())
        if before != input_hashes(ROOT):
            raise SystemExit('Sources changed during export; '
                             'run the build task again.')
        from build import build
        build(force=True, exported=editor_export_path())
        return
    if command == 'lint':
        from lint_typst import lint
        raise SystemExit(0 if lint()['status'] == 'passed' else 1)
    if command == 'test':
        tests()
        return
    from build import build, build_corrections
    if command == 'corrections':
        build_corrections()
        return
    if command == 'build-no-notes':
        build(force=args.force, notes=False)
        return
    build(force=args.force or command == 'check',
          thorough=command == 'check')
    if command == 'check':
        tests()
        build_corrections()
        # The no-notes edition must build as well: a label or a reference
        # target inside an editorial note would vanish with the note.
        build(force=True, notes=False)


if __name__ == '__main__':
    main()
