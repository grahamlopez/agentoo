"""Transparency CLI validation, inherited values, and live queries."""
import argparse
import json
import math
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
from desktop.common import authored_hypr_paths, hyprctl

GROUPS = ('all', 'kitty', 'browser')
STATES = ('focused', 'unfocused')


def percentage(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90') from None
    if not math.isfinite(number) or not 0 <= number <= 90:
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90')
    return number


def state_path():
    from desktop.state import state_path as shared_path
    return shared_path()


def read_state(path):
    from desktop.state import section
    return section('transparency', path)


def effective(data, group, focus):
    return data.get(group, {}).get(focus, data.get('all', {}).get(focus))


def adjusted(data, group, focused=None, unfocused=None):
    data = {key: dict(values) for key, values in data.items()}
    for focus, value in zip(STATES, (focused, unfocused)):
        if value is None:
            continue
        data.setdefault(group, {})[focus] = value
        if group == 'all':
            for child in ('kitty', 'browser'):
                data.get(child, {}).pop(focus, None)
    return {key: values for key, values in data.items() if values}


def conflicts():
    # Conservative inspection, not a Lua evaluator. Never modify authored files.
    # Includes anywhere beneath these roots are covered; opaque/dynamic includes
    # outside them require manual inspection (documented).
    found = []
    for path in authored_hypr_paths():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = re.split(r'--|#', line, maxsplit=1)[0]
            if re.search(r'\b(opacity|opaque|force_rgbx)\s*[= ]', line):
                found.append(f'{path}:{number}')
    return found


def require_integration(recover=False):
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        raise RuntimeError('A running Hyprland session is required to change transparency')
    if recover:
        # A full reset must also recover from malformed saved state or authored
        # rules added since the last successful load.
        hyprctl('version')
        return
    result = hyprctl('eval', 'assert(agentoo_transparency_loaded, "Agentoo transparency integration is not loaded")')
    if result != 'ok':
        raise RuntimeError('Load the Agentoo Hyprland configuration first: ' + result)
    errors = hyprctl('configerrors')
    if errors:
        raise RuntimeError('Fix Hyprland configuration errors before changing transparency: ' + errors)


def kitty_defaults():
    # Kitty owns its include/geninclude/host/command-line parsing. This starts no
    # window and needs neither remote-control access nor a display connection.
    code = ('import json; from kitty.cli import default_config_paths; '
            'from kitty.config import load_config; '
            'o=load_config(*default_config_paths(())); '
            'print(json.dumps([o.background_opacity, o.dynamic_background_opacity, list(o.watcher)]))')
    try:
        result = subprocess.run(['kitty', '+runpy', code], text=True, capture_output=True, timeout=10)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def show(data, selected):
    defaults = {}
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        for focus, option in zip(STATES, ('active', 'inactive')):
            try:
                value = json.loads(hyprctl('-j', 'getoption', f'decoration:{option}_opacity'))['float']
                defaults[focus] = (1 - float(value)) * 100
            except (RuntimeError, ValueError, KeyError, TypeError):
                pass
    kitty = kitty_defaults()
    print(f'{"WINDOW":<10} {"FOCUSED":<32} UNFOCUSED')
    for group in GROUPS if selected == 'all' else (selected,):
        cells = []
        for focus in STATES:
            value = effective(data, group, focus)
            source = 'override' if focus in data.get(group, {}) else 'inherited: all'
            if value is None:
                value = (1 - kitty[0]) * 100 if group == 'kitty' and kitty else defaults.get(focus)
                source = 'configured default'
            cells.append(f'{value:g}% ({source})' if value is not None else source)
        print(f'{group:<10} {cells[0]:<32} {cells[1]}')
    print('Kitty: background only. Other windows: whole window.')
    for location in conflicts():
        print(f'agentoo desktop: warning: transparency rule may conflict: {location}', file=sys.stderr)
