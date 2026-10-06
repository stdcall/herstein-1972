"""Advisory Russian prose check using Vale's Typst parser.

Vale reads Typst through typst2vast, excluding math and code. Findings
refer to source lines. A report with findings is advisory; failure to
obtain a report is an error. Pass file paths to check only changed prose.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from project import cache_path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'checks/vale/.vale.ini'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', type=Path)
    parser.add_argument('--fail-on-findings', action='store_true')
    args = parser.parse_args()
    for program in ('vale', 'typst2vast'):
        if shutil.which(program) is None:
            raise SystemExit(f'{program} is required for the prose check')
    sources = ([path.resolve() for path in args.paths]
               or sorted((ROOT/'content').rglob('*.typ')))
    result = subprocess.run(
        ['vale', '--config', str(CONFIG), '--output', 'JSON',
         *map(str, sources)], capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(f'Vale did not return JSON: {result.stderr}') from error
    if result.returncode not in (0, 1) or not isinstance(report, dict):
        raise SystemExit(f'Vale failed ({result.returncode}): {result.stderr}')
    cache = cache_path()
    cache.mkdir(parents=True, exist_ok=True)
    (cache/'prose-report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    counts = {}
    for name, issues in sorted(report.items()):
        for issue in issues:
            rule = issue['Check']
            counts[rule] = counts.get(rule, 0) + 1
            print(f'{Path(name).resolve().relative_to(ROOT)}:{issue["Line"]}:'
                  f'{issue["Span"][0]} {rule}: {issue["Message"]}')
    print('Vale:', sum(counts.values()), 'findings')
    for rule, count in sorted(counts.items()):
        print(f'  {rule}: {count}')
    if counts and args.fail_on_findings:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
