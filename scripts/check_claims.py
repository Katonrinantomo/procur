#!/usr/bin/env python3
"""Check that the numbers the README claims match the code.

Run from anywhere with the backend venv's Python:
    backend\\.venv\\Scripts\\python.exe scripts\\check_claims.py

Test count: the README's "<N> tests" claims are compared with the number of
tests pytest COLLECTS (`pytest --collect-only -q` in backend/), not the
number that pass: live tests are collected but skipped unless `-m live`, so
collected = passed + skipped on a green offline run.

Coverage: if backend/coverage.json exists (written by scripts/release_check.ps1)
and the README states "<P>% line coverage", the whole-number percentages
must agree.

Exit code 0 when every claim matches, 1 otherwise.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
README = ROOT / 'README.md'

TESTS_CLAIM = re.compile(r'\b(\d+) tests\b')
COVERAGE_CLAIM = re.compile(r'\b(\d+)% line coverage\b')
COLLECTED = re.compile(r'^(\d+) tests? collected', re.MULTILINE)


def collected_tests() -> int:
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider'],
        cwd=BACKEND, capture_output=True, text=True,
    )
    m = COLLECTED.search(proc.stdout)
    if proc.returncode != 0 or not m:
        print(proc.stdout[-2000:], proc.stderr[-2000:], sep='\n')
        raise SystemExit('check_claims: pytest --collect-only failed')
    return int(m.group(1))


def main() -> int:
    readme = README.read_text(encoding='utf-8')
    failures = []

    claims = [int(n) for n in TESTS_CLAIM.findall(readme)]
    actual = collected_tests()
    if not claims:
        failures.append('README states no "<N> tests" claim')
    for n in claims:
        if n != actual:
            failures.append(f'README says {n} tests; pytest collects {actual}')
    print(f'tests: README {sorted(set(claims))}, pytest --collect-only {actual}')

    cov_file = BACKEND / 'coverage.json'
    cov_claims = [int(n) for n in COVERAGE_CLAIM.findall(readme)]
    if cov_file.exists() and cov_claims:
        pct = json.loads(cov_file.read_text(encoding='utf-8'))['totals']['percent_covered']
        for n in cov_claims:
            if n != round(pct):
                failures.append(f'README says {n}% line coverage; last run measured {pct:.1f}%')
        print(f'coverage: README {sorted(set(cov_claims))}%, last run {pct:.1f}%')

    for f in failures:
        print(f'FAIL: {f}')
    if not failures:
        print('Claims check passed.')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
