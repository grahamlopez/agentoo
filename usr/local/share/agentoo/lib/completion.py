#!/usr/bin/env python3
"""Read-only completion service; normal commands own their parsers.

Protocol: one tab-separated record per line: command/option/candidate VALUE
DESCRIPTION DISPLAY, a usage line, or files/directories/users/git. Values are
data, never shell code. The current word
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
    'repos': 'Check system and home Git repositories',
    'term-colors': 'Show visual terminal color tests',
    'checkpoint': 'Create, list, inspect, and restore system checkpoints',
    'permissions': 'Check or repair managed ownership and permissions',
    'secrets': 'Install secret files from Proton Pass',
    'cloud-storage': 'Start, stop, and inspect cloud storage clients',
    'display': 'Manage display output, backlights, and external monitor controls',
    'screenshot': 'Capture all displays or a selected region',
    'power': 'Show battery and CPU power status',
    'fonts': 'Diagnose, preview, and select installed fonts',
    'desktop': 'Manage wallpaper and desktop appearance',
    'help': 'Show help for a command',
}

# Checkpoint is the deliberate sh exception. These completion declarations mirror
# its standalone help; parity tests check the small duplicate syntax surface.
ROOT_USAGE = 'agentoo <command> [options]'
CHECKPOINT_USAGE = {
    'create': 'agentoo checkpoint create LABEL [options]',
    'list': 'agentoo checkpoint list [options]',
    'inspect': 'agentoo checkpoint inspect NAME [options]',
    'restore': 'agentoo checkpoint restore NAME --device DEVICE [options]',
}


class CompletionHelpFormatter(argparse.HelpFormatter):
    def _format_usage(self, usage, actions, groups, prefix=None):
        return super()._format_usage(usage, actions, groups, prefix or 'Usage: ')


class CompletionParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('formatter_class', CompletionHelpFormatter)
        super().__init__(*args, **kwargs)


def python_parser(name):
    from importlib.machinery import SourceFileLoader
    path = HERE.parents[2] / 'bin' / ('agentoo-' + name)
    spec = importlib.util.spec_from_loader('agentoo_' + name, SourceFileLoader('agentoo_' + name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_parser()
    return parser


def parser_for(name):
    if name != 'checkpoint':
        return python_parser(name)
    parser = CompletionParser(prog='agentoo checkpoint',
        usage='agentoo checkpoint {create|list|inspect|restore} [options]')
    sub = parser.add_subparsers(dest='operation', required=True, prog=parser.prog)
    for operation, description in {
        'create': 'Capture system, home, and EFI',
        'list': 'List checkpoints and storage usage',
        'inspect': 'Show metadata and verify saved components',
        'restore': 'Restore from recovery media; preserve home by default',
    }.items():
        child = sub.add_parser(operation, help=description)
        child.usage = CHECKPOINT_USAGE[operation]
        if operation != 'list':
            child.add_argument('name', metavar='LABEL' if operation == 'create' else 'NAME',
                               help='Checkpoint label or name')
        if operation != 'create':
            child.add_argument('--device', help='Btrfs device').completion = 'files'
        child.add_argument('--no-input', action='store_true', help='Never prompt; use sudo -n')
        if operation in ('create', 'restore'):
            child.add_argument('--dry-run', action='store_true', help='Validate and plan using read-only inspection')
            if operation == 'create':
                child.add_argument('--yes', action='store_true', help='Authorize capture without prompting')
            else:
                child.add_argument('--confirm', metavar='NAME', help='Authorize exact restore name')
        child.add_argument('--efi-mount', metavar='PATH', help='EFI mountpoint').completion = 'directories'
        if operation in ('create', 'restore'):
            for component in ('system', 'home', 'efi'):
                group = child.add_mutually_exclusive_group()
                group.add_argument('--' + component, action='store_true', help='Include ' + component)
                group.add_argument('--no-' + component, action='store_true', help='Exclude ' + component)
        if operation == 'create':
            group = child.add_mutually_exclusive_group()
            group.add_argument('--clean-package-caches', action='store_true', help='Delete package caches before capture (default with system)')
            group.add_argument('--no-clean-package-caches', action='store_true', help='Keep package caches when capturing system')
    return parser


def emit(kind, value='', description='', display=''):
    def clean(text):
        return str(text or '').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    print('\t'.join(map(clean, (kind, value, description, display))))


def emit_usage(parser):
    # argparse may wrap usage over several physical lines. Keep its full syntax
    # in one logical line, using the same parser as help without parsing or running.
    usage = ' '.join(parser.format_usage().split())
    emit('usage', usage)


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
    if kind in ('files', 'directories', 'users'):
        emit(kind)
    elif kind == 'external_outputs':
        from display_external import connected_outputs
        for path in connected_outputs():
            emit('candidate', path.name)
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
        emit_usage(CompletionParser(prog='agentoo', usage=ROOT_USAGE))
        for name, description in COMMANDS.items():
            emit('command', name, description)
        if not previous:
            emit('option', '--help', 'Show help')
            emit('option', '-h', 'Show help')
            emit('option', '--version', 'Show repository revision')
        return
    if previous[0] == 'help':
        previous = previous[1:]
    name, *tokens = previous
    if name == 'git':
        emit_usage(python_parser('git'))
        if not tokens:
            emit('command', 'setup-hooks', 'Enable permission hooks')
            emit('command', 'enable-write', 'Switch origin to SSH')
        if tokens and tokens[0] in ('setup-hooks', 'enable-write'):
            parser = python_parser('git')._subparsers._group_actions[0].choices[tokens[0]]
            emit_usage(parser)
            for action in parser._actions:
                for option in action.option_strings:
                    emit('option', option, action.help)
        else:
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
    emit_usage(parser)
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
    # Invoked only by agentoo __complete; import/parsing never runs operations.
    mode, current, *words = sys.argv[1:]
    if mode != 'complete':
        raise SystemExit('usage: completion.py complete CURRENT [WORDS...]')
    complete(int(current), words)


if __name__ == '__main__':
    main()
