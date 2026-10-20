#!/usr/bin/env python3
"""Shared shell-command argument parsers and read-only completion service.

Protocol: one tab-separated record per line: command/option/candidate VALUE
DESCRIPTION DISPLAY, or
files/directories/users/git. Values are data, never shell code. The current word
is one-based among arguments after `agentoo`; later words are ignored.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

# Importing a parser for Tab completion must not create __pycache__ files.
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
COMMANDS = {
    'git': 'Run Git against the Agentoo system repository',
    'checkpoint': 'Create, list, inspect, and restore system checkpoints',
    'permissions': 'Check or repair managed ownership and permissions',
    'secrets': 'Install secret files from Proton Pass',
    'backlight': 'Adjust display brightness',
    'screenshot': 'Capture all displays or a selected region',
    'power': 'Show battery and CPU power status',
    'fonts': 'Diagnose, preview, and select installed fonts',
    'help': 'Show help for a command',
}


def python_parser(name):
    spec = importlib.util.spec_from_file_location('agentoo_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_parser()


def parser_for(name):
    if name in ('fonts', 'power'):
        return python_parser(name)
    parser = argparse.ArgumentParser(prog='agentoo ' + name)
    if name == 'permissions':
        operation = parser.add_argument('operation', choices=['check', 'fix'])
        operation.completion = 'commands'
        operation.completion_descriptions = {
            'check': 'Report ownership and permission mismatches',
            'fix': 'Restore declared ownership and permissions',
        }
        parser.add_argument('--root', help='Mounted target root').completion = 'directories'
    elif name == 'backlight':
        parser.add_argument('direction', choices=['up', 'down'])
        parser.add_argument('controller', nargs='?').completion = 'controllers'
    elif name == 'screenshot':
        parser.add_argument('capture', choices=['full', 'region'])
    elif name in ('checkpoint', 'secrets'):
        sub = parser.add_subparsers(dest='operation', required=True)
        operations = ('create', 'list', 'inspect', 'restore') if name == 'checkpoint' else ('install',)
        for operation in operations:
            descriptions = {
                'create': 'Capture system, home, and EFI',
                'list': 'List checkpoints and storage usage',
                'inspect': 'Show metadata and verify saved components',
                'restore': 'Restore from recovery media; preserve home by default',
                'install': 'Install selected categories from a secret profile',
            }
            child = sub.add_parser(operation, help=descriptions[operation])
            if name == 'secrets':
                child.add_argument('--profile', required=True).completion = 'files'
                child.add_argument('--user', required=True).completion = 'users'
                child.add_argument('category', nargs='+').completion = 'categories'
                continue
            if operation != 'list':
                child.add_argument('name', help='Checkpoint label or name')
            child.add_argument('--device', help='Btrfs device').completion = 'files'
            child.add_argument('--efi-mount', help='EFI mountpoint').completion = 'directories'
            if operation in ('create', 'restore'):
                for component in ('system', 'home', 'efi'):
                    group = child.add_mutually_exclusive_group()
                    group.add_argument('--' + component, action='store_true', help='Include ' + component)
                    group.add_argument('--no-' + component, action='store_true', help='Exclude ' + component)
            if operation == 'create':
                group = child.add_mutually_exclusive_group()
                group.add_argument('--clean-distfiles', action='store_true')
                group.add_argument('--no-clean-distfiles', action='store_true')
    return parser


def emit(kind, value='', description='', display=''):
    def clean(text):
        return str(text or '').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    print('\t'.join(map(clean, (kind, value, description, display))))


def values_for(action, supplied):
    if action.choices is not None:
        subcommands = isinstance(action, argparse._SubParsersAction)
        descriptions = ({child.dest: child.help for child in action._get_subactions()}
                        if subcommands else getattr(action, 'completion_descriptions', {}))
        kind = 'command' if subcommands or getattr(action, 'completion', None) == 'commands' else 'candidate'
        for value in action.choices:
            emit(kind, value, descriptions.get(value, ''))
        return
    kind = getattr(action, 'completion', None)
    if kind is None:
        kind = {'font': 'fonts', 'output': 'files'}.get(action.dest)
    if kind in ('files', 'directories', 'users'):
        emit(kind)
    elif kind == 'controllers':
        for path in Path('/sys/class/backlight').glob('*'):
            emit('candidate', path.name)
    elif kind == 'categories':
        emit('candidate', 'all', 'Every profile category')
        try:
            profile = Path(supplied.get('--profile', ''))
            if not profile.is_file():
                return
            for line in profile.read_text().splitlines():
                fields = line.split()
                if fields and not fields[0].startswith('#'):
                    emit('candidate', fields[0])
        except OSError:
            pass
    elif kind == 'fonts':
        try:
            result = subprocess.run(['fc-list', '--format=%{family}\n'], capture_output=True,
                                    text=True, timeout=2, check=True)
            for family in sorted(set(result.stdout.splitlines())):
                emit('candidate', family)
        except (OSError, subprocess.SubprocessError):
            pass


def complete(current, words):
    previous = words[:current - 1]
    if not previous or previous == ['help']:
        for name, description in COMMANDS.items():
            emit('command', name, description)
        if not previous:
            emit('option', '--help', 'Show help')
            emit('option', '-h', 'Show help')
        return
    name, *tokens = previous
    if name == 'git':
        if not tokens:
            emit('command', 'setup-hooks', 'Enable permission hooks')
            emit('command', 'enable-write', 'Switch origin to SSH')
        if not tokens or tokens[0] not in ('setup-hooks', 'enable-write'):
            emit('git')
        return
    if name not in COMMANDS or name == 'help':
        return
    parser = parser_for(name)
    supplied = {}
    seen = set()
    position = 0
    pending = None
    options_enabled = True
    for token in tokens:
        if pending is not None:
            supplied[pending.option_strings[0]] = token
            pending = None
            continue
        if token == '--' and options_enabled:
            options_enabled = False
            continue
        option, equals, value = token.partition('=')
        action = parser._option_string_actions.get(option) if options_enabled else None
        if action is not None:
            seen.add(action)
            if action.nargs != 0:
                if equals:
                    supplied[action.option_strings[0]] = value
                else:
                    pending = action
            continue
        positional = [a for a in parser._actions if not a.option_strings]
        if position >= len(positional):
            continue
        action = positional[position]
        if isinstance(action, argparse._SubParsersAction):
            if token not in action.choices:
                return
            parser = action.choices[token]
            position = 0
            seen = set()
        elif action.nargs not in ('*', '+'):
            position += 1
    if pending is not None:
        values_for(pending, supplied)
        return
    current_word = words[current - 1] if current <= len(words) else ''
    option, equals, _ = current_word.partition('=')
    if options_enabled and equals and option in parser._option_string_actions:
        emit('prefix', option + '=')
        values_for(parser._option_string_actions[option], supplied)
        return
    excluded = set(seen)
    for group in parser._mutually_exclusive_groups:
        if seen.intersection(group._group_actions):
            excluded.update(group._group_actions)
    if options_enabled:
        for action in parser._actions:
            if action not in excluded and action.help != argparse.SUPPRESS:
                for option in action.option_strings:
                    display = option
                    if action.nargs != 0:
                        metavar = action.metavar or action.dest.upper()
                        if isinstance(metavar, tuple):
                            metavar = ' '.join(metavar)
                        display += ' ' + str(metavar)
                    emit('option', option, action.help, display)
    if not current_word.startswith('-') or not options_enabled:
        positional = [a for a in parser._actions if not a.option_strings]
        if position < len(positional):
            values_for(positional[position], supplied)


def main():
    mode, *args = sys.argv[1:]
    if mode == 'complete':
        complete(int(args[0]), args[1:])
    elif mode == 'validate':
        name, *args = args
        # The front end already removes the secrets install verb.
        if not any(arg in ('-h', '--help') for arg in args):
            parser_for(name).parse_args(['install', *args] if name == 'secrets' else args)
    elif mode == 'commands':
        for name, description in COMMANDS.items():
            print(f'  {name:<12} {description}')


if __name__ == '__main__':
    main()
