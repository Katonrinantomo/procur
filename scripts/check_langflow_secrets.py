#!/usr/bin/env python3
"""Check that langflow/*.json exports contain no secrets.
Run before committing a new export: python scripts/check_langflow_secrets.py

Ported from the Tilas repo (tilas-ai-maker-checker, Agiel). Changes: reads
files as UTF-8, resolves langflow/ relative to this script, and also flags
any non-empty api_key field that is not loaded from a Langflow global
variable (catches keys the regex misses, such as Serper's hex keys).
"""
import json
import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r'\b(sk-[A-Za-z0-9_-]{16,}'
    r'|AIza[0-9A-Za-z_-]{20,}'
    r'|Bearer [A-Za-z0-9._-]{20,}'
    r'|ghp_[A-Za-z0-9]{20,}'
    r'|gho_[A-Za-z0-9]{20,}'
    r'|AKIA[0-9A-Z]{16})'
)

ROOT = Path(__file__).resolve().parents[1] / 'langflow'


def walk(obj, path=''):
    if isinstance(obj, dict):
        # A template field named api_key must be empty or point at a global variable.
        key_field = obj.get('api_key')
        if (
            isinstance(key_field, dict)
            and isinstance(key_field.get('value'), str)
            and key_field['value'].strip()
            and not key_field.get('load_from_db')
        ):
            yield f'{path}.api_key.value', '<literal api_key value>'
        for k, v in obj.items():
            yield from walk(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        if PATTERN.search(obj):
            yield path, obj[:120]


def main():
    files = sorted(ROOT.glob('*.json'))
    if not files:
        print('No files in langflow/. OK.')
        return 0
    found_any = False
    for f in files:
        print(f'Checking {f.name}...')
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            hits = list(walk(data))
            if hits:
                found_any = True
                print(f'  WARNING: {len(hits)} secret value(s) found:')
                for path, val in hits[:5]:
                    print(f'    {path}: {val}')
            else:
                print('  OK - clean')
        except Exception as e:
            print(f'  ERROR: {e}')
            return 2
    if found_any:
        print('\nFAIL: secrets found. Do NOT commit.')
        return 1
    print('\nPASS: all files clean. Safe to commit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
