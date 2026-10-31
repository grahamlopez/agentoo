#!/usr/bin/env python3
"""Adjust display backlights only; never fall back to keyboard LEDs."""
from argparse import RawDescriptionHelpFormatter
import os
from pathlib import Path


def configure_parser(parser):
    parser.description = __doc__
    parser.formatter_class = RawDescriptionHelpFormatter
    parser.epilog = ('Changes perceived brightness by 5%; never switches the panel off.\n'
                     'With no display backlight, automatic selection succeeds without action.')
    parser.add_argument('direction', choices=('up', 'down'))
    parser.add_argument('controller', nargs='?', help='Required when multiple display backlights exist').completion = 'controllers'
    return parser


def run(args, parser):
    # Select a display controller from sysfs; keyboard LEDs live elsewhere.
    # Without an explicit controller, no backlight means no action, and several
    # require a choice rather than adjusting an arbitrary panel.
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
    # Pass that controller to xbacklight for a 5% perceived-brightness adjustment.
    os.execvp('xbacklight', ['xbacklight', '-ctrl', controller, '-perceived',
                           '-inc' if args.direction == 'up' else '-dec', '5'])
