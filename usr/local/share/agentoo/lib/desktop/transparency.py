"""Transparency state and CLI operations; imported without effects for completion.

JSON is the only authoritative saved state.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

from desktop.common import (window_rule_conflicts, effective, hyprctl, read,
                            WINDOW_GROUPS as GROUPS)
STATES = ('focused', 'unfocused')


def percentage(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90') from None
    if not math.isfinite(number) or not 0 <= number <= 90:
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90')
    return number


def read_state(path):
    return validate_data(read(path).get('transparency', {}))


def validate_data(data):
    if not isinstance(data, dict) or set(data) - set(GROUPS):
        raise RuntimeError(f'Invalid transparency groups in transparency section')
    for group, values in data.items():
        if not isinstance(values, dict) or set(values) - set(STATES):
            raise RuntimeError(f'Invalid transparency settings for {group} in transparency section')
        for value in values.values():
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 90:
                raise RuntimeError(f'Invalid transparency percentage in transparency section')
    return data


def adjusted(data, group, focused=None, unfocused=None):
    data = {key: dict(values) for key, values in data.items()}
    for focus, value in zip(STATES, (focused, unfocused)):
        if value is None:
            continue
        data.setdefault(group, {})[focus] = value
        if group == 'all':
            for child in GROUPS[1:]:
                data.get(child, {}).pop(focus, None)
    return {key: values for key, values in data.items() if values}


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


def configured_default(group, focus):
    if group == 'kitty':
        kitty = kitty_defaults()
        if not kitty:
            raise RuntimeError('Cannot read Kitty background opacity')
        return (1 - kitty[0]) * 100
    option = 'active' if focus == 'focused' else 'inactive'
    value = json.loads(hyprctl('-j', 'getoption', f'decoration:{option}_opacity'))['float']
    return (1 - float(value)) * 100


def active_category():
    # Read the class and authoritative patterns together; these expressions use
    # the common subset of Python and Hyprland's RE2 regular expressions.
    report = hyprctl('repl', r'''local active = hl.get_active_window()
if not active then return "none" end
local families = require("/etc/xdg/hypr/window-classes.lua")
return active.class .. "\n" .. families.kitty .. "\n" .. families.browser''')
    fields = report.rsplit('\n', 2)
    if len(fields) != 3:
        raise RuntimeError('No active window category to adjust')
    window_class, kitty, browser = fields
    for group, pattern in (('kitty', kitty), ('browser', browser)):
        if re.fullmatch(pattern, window_class):
            return group
    return 'other'


def relative_adjusted(data, direction, unfocused=False):
    group = active_category()
    focus = 'unfocused' if unfocused else 'focused'
    value = effective(data, group, focus)
    if value is None:
        value = configured_default(group, focus)
    value = max(0, min(90, value + (5 if direction == 'up' else -5)))
    return adjusted(data, group, **{focus: value})


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
        for focus in STATES:
            try:
                defaults[focus] = configured_default('all', focus)
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
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        for location in window_rule_conflicts('transparency'):
            print(f'agentoo desktop: warning: transparency rule may conflict: {location}', file=sys.stderr)
