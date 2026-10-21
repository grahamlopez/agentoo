#!/usr/bin/env python3
"""Adjust display backlights only; never fall back to keyboard LEDs."""
import os
from pathlib import Path
from cli import ArgumentParser


def configure_parser(parser):
    parser.description = __doc__
    parser.epilog = ('Changes perceived brightness by 5%; never switches the panel off. '
                     'With no display backlight, automatic selection succeeds without action.')
    parser.add_argument('direction', choices=('up', 'down'))
    parser.add_argument('controller', nargs='?', help='Required when multiple display backlights exist').completion = 'controllers'
    return parser


def build_parser():
    return configure_parser(ArgumentParser(prog='agentoo display backlight'))


def run(args, parser):
    directory = Path('/sys/class/backlight')
    if args.controller is not None:
        if not args.controller or '/' in args.controller or args.controller in ('.', '..'):
            parser.error('invalid backlight controller')
        if not (directory / args.controller).is_dir():
            raise RuntimeError(f'No display backlight: {args.controller}')
        controller = args.controller
    else:
        controllers = sorted(path.name for path in directory.glob('*') if path.is_dir())
        if not controllers:
            return 0
        if len(controllers) > 1:
            raise RuntimeError('Multiple display backlights; select a controller in host bindings')
        controller = controllers[0]
    os.execvp('xbacklight', ['xbacklight', '-ctrl', controller, '-perceived',
                           '-inc' if args.direction == 'up' else '-dec', '5'])


def main():
    parser = build_parser()
    return run(parser.parse_args(), parser)
