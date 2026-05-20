#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.path_resolver import get_root
from utils.validation import validate_blueprint

PROJECT_ROOT = get_root()


def _validate_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get('blueprint'):
            validate_blueprint(data['blueprint'])
            return {'valid': True, 'message': 'Blueprint valid'}

        return {'valid': True, 'message': 'No blueprint to validate'}
    except Exception as err:
        return {'valid': False, 'message': str(err)}


def main():
    print('═' * 60, flush=True)
    print('  VideoReverse — Validator', flush=True)
    print('═' * 60 + '\n', flush=True)

    output_dir = os.path.join(PROJECT_ROOT, 'output_blueprints')
    if not os.path.exists(output_dir):
        print('  No output_blueprints directory found', flush=True)
        print('\n' + '═' * 60, flush=True)
        print('  ✅ No outputs to validate', flush=True)
        print('═' * 60 + '\n', flush=True)
        sys.exit(0)

    json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]

    if not json_files:
        print('  No JSON files found in output_blueprints', flush=True)
        print('\n' + '═' * 60, flush=True)
        print('  ✅ No outputs to validate', flush=True)
        print('═' * 60 + '\n', flush=True)
        sys.exit(0)

    all_valid = True

    for file in json_files:
        filepath = os.path.join(output_dir, file)
        result = _validate_file(filepath)

        icon = '✅' if result['valid'] else '❌'
        print(f'{icon} {file}: {result["message"]}', flush=True)

        if not result['valid']:
            all_valid = False

    print('\n' + '═' * 60, flush=True)
    if all_valid:
        print('  ✅ All outputs valid', flush=True)
    else:
        print('  ❌ Some outputs invalid', flush=True)
    print('═' * 60 + '\n', flush=True)

    sys.exit(0 if all_valid else 1)


if __name__ == '__main__':
    main()
