"""Small shared desktop helpers. Importing these performs no operations."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from host_selection import SELECTOR, read_host
from xdg import xdg_directory

# Keep categories aligned with /etc/xdg/hypr/window-classes.lua.
# 'all' selects every category; it is not itself an application category.
WINDOW_GROUPS = ('all', 'kitty', 'browser', 'other')


def state_path():
    return xdg_directory('XDG_STATE_HOME', '.local/state') / 'agentoo/appearance.json'


def read_json(path):
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError) as error:
        raise RuntimeError(f'Cannot read appearance file {path}: {error}') from error
    if not isinstance(data, dict):
        raise RuntimeError(f'Appearance file {path} must contain a JSON object')
    return data


def read(path=None):
    path = state_path() if path is None else Path(path)
    return read_json(path) if path.exists() else {}


def effective(data, group, focus):
    return data.get(group, {}).get(focus, data.get('all', {}).get(focus))


def file_option(parser, *, required=False):
    parser.add_argument('--file', dest='appearance_file', metavar='FILE',
                        required=required,
                        help='Apply and remember supplied appearance settings from JSON; omitted settings stay unchanged').completion = 'files'


def window_option(parser, *, child=False):
    help_text = 'Window category (default: all). other excludes Kitty and browsers.'
    if child:
        help_text += ' --window may also be supplied before the action.'
    parser.add_argument('--window', choices=WINDOW_GROUPS,
                        default=argparse.SUPPRESS if child else 'all',
                        help=help_text)


def authored_hypr_paths():
    paths = []
    try:
        selected = read_host(SELECTOR)
    except FileNotFoundError:
        pass
    else:
        host = Path('/etc/xdg/hypr/hosts') / (selected + '.lua')
        if host.is_file():
            paths.append(host)
    root = xdg_directory('XDG_CONFIG_HOME', '.config') / 'hypr'
    if root.exists():
        paths.extend(path for path in sorted(root.rglob('*'))
                     if path.suffix in ('.lua', '.conf') and path.is_file())
    return paths


def hyprctl(*arguments, timeout=10):
    try:
        result = subprocess.run(['hyprctl', *arguments], text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'Cannot contact Hyprland: {error}') from error
    if result.returncode:
        raise RuntimeError('Hyprland: ' + (result.stderr or result.stdout).strip())
    return result.stdout.strip()


def atomic_write(path, value):
    """Replace one preference file without exposing a partial write to readers."""
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb' if isinstance(value, bytes) else 'w') as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
