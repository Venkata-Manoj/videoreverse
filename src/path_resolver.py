import os
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def get_root():
    return str(_ROOT)


def get_src_path(filename=''):
    return str(_ROOT / 'src' / filename)


def get_config_path(filename):
    return str(_ROOT / 'config' / filename)


def get_utils_path(filename=''):
    return str(_ROOT / 'utils' / filename)


def get_output_path(filename=''):
    env_path = os.environ.get('VIDEO_REV_OUTPUT_DIR', str(_ROOT / 'output_blueprints'))
    return os.path.join(env_path, filename)


def get_cache_path(filename=''):
    return str(_ROOT / '.cache' / filename)


def resolve_template(template_name):
    template_path = get_config_path(template_name)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f'Template not found: {template_path}')
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_for_env(target):
    if not isinstance(target, str):
        return target
    if '://' in target:
        return target

    is_unc = target.startswith('\\\\')
    if is_unc:
        unc_path = target.replace('\\\\', '/').replace('\\', '/')
        parts = [p for p in unc_path.split('/') if p]
        if len(parts) >= 2:
            return f'/mnt/{parts[0].lower()}/{"/".join(parts[1:])}'

    import re
    is_windows_path = bool(re.match(r'^[a-zA-Z]:[\\/]', target))
    if is_windows_path:
        drive = target[0].lower()
        posix_path = target[2:].replace('\\', '/').lstrip('/')
        return f'/mnt/{drive}/{posix_path}'

    return os.path.abspath(target)
