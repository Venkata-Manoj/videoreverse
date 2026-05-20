#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.path_resolver import get_root

PROJECT_ROOT = get_root()

LINT_RULES = [
    {'pattern': re.compile(r'TODO(?!:)'), 'message': 'TODO must be followed by colon'},
    {'pattern': re.compile(r'#\s*DEBUG'), 'message': 'Remove debug comments'},
    {'pattern': re.compile(r'import\s+os\s*$'), 'message': None, 'skip': True},
]

EXCLUDED_DIRS = {'__pycache__', '.cache', 'output_blueprints', 'test_results', 'node_modules', '.git'}
EXCLUDED_FILES = {'lint.py'}


def _lint_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []
    for rule in LINT_RULES:
        if rule.get('skip'):
            continue
        for match in rule['pattern'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            issues.append({'file': filepath, 'line': line_num, 'message': rule['message']})

    return issues


def _find_python_files(dir_path):
    files = []
    for entry in os.scandir(dir_path):
        full_path = entry.path
        if entry.is_dir():
            if entry.name not in EXCLUDED_DIRS:
                files.extend(_find_python_files(full_path))
        elif entry.name.endswith('.py') and entry.name not in EXCLUDED_FILES:
            files.append(full_path)
    return files


def main():
    print('═' * 60, flush=True)
    print('  VideoReverse — Linter', flush=True)
    print('═' * 60 + '\n', flush=True)

    py_files = _find_python_files(PROJECT_ROOT)
    total_issues = 0

    for file in py_files:
        relative_path = os.path.relpath(file, PROJECT_ROOT)
        issues = _lint_file(file)

        if issues:
            print(f'\n❌ {relative_path}', flush=True)
            for issue in issues:
                print(f'   Line {issue["line"]}: {issue["message"]}', flush=True)
            total_issues += len(issues)

    print('\n' + '═' * 60, flush=True)
    if total_issues == 0:
        print('  ✅ No issues found', flush=True)
    else:
        print(f'  ❌ {total_issues} issue(s) found', flush=True)
    print('═' * 60 + '\n', flush=True)

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == '__main__':
    main()
