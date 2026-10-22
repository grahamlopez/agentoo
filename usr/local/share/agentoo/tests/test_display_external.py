"""DDC command selection and validation; never writes real monitor settings."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_desktop_commands import load

DISPLAY = load('display')
EXTERNAL = DISPLAY.display_external


class ExternalDisplay(unittest.TestCase):
    def command(self, *tokens, status=0):
        parser = DISPLAY.build_parser()
        args = parser.parse_args(['external', *tokens])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], status)) as run:
            self.assertEqual(EXTERNAL.run(args, parser), status)
        return run.call_args.args[0]

    def test_read_commands_never_write(self):
        self.assertEqual(self.command('list'), ['ddcutil', 'detect'])
        for name, suffix in [('capabilities', ['capabilities']), ('brightness', ['getvcp', '10']),
                             ('volume', ['getvcp', '62']), ('mute', ['getvcp', '8D']),
                             ('input', ['getvcp', '60']), ('get', ['getvcp', 'E9'])]:
            with self.subTest(name=name):
                tokens = ['E9'] if name == 'get' else []
                self.assertEqual(self.command(name, *tokens, '--bus', '16'), ['ddcutil', '--bus', '16', *suffix])

    def test_write_encoding_and_exit_status(self):
        for tokens, suffix in [
            (['brightness', 'up'], ['10', '+', '5', '--verify']),
            (['brightness', 'down'], ['10', '-', '5', '--verify']),
            (['brightness', '0'], ['10', '0', '--verify']),
            (['volume', '100'], ['62', '100', '--verify']),
            (['mute', 'on'], ['8D', '1', '--verify']),
            (['mute', 'off'], ['8D', '2', '--verify']),
            (['input', '0x19', '--no-verify'], ['60', '25', '--noverify']),
            (['set', '0xe9', '0x21', '--no-verify'], ['E9', '33', '--permit-unknown-feature', '--noverify']),
        ]:
            with self.subTest(tokens=tokens):
                self.assertEqual(self.command(*tokens, '--bus', '16', status=7),
                                 ['ddcutil', '--bus', '16', 'setvcp', *suffix])

    def test_nonstandard_relative_volume_never_writes(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'up', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 0, 'VCP 62 C 178 65380\n', '')) as run:
            with self.assertRaisesRegex(RuntimeError, 'nonstandard volume'):
                EXTERNAL.run(args, None)
            self.assertEqual(run.call_count, 1)
            self.assertNotIn('setvcp', run.call_args.args[0])

    def test_standard_relative_volume(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'down', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0, 'VCP 62 C 30 100\n', ''),
                    subprocess.CompletedProcess([], 0)]) as run:
            self.assertEqual(EXTERNAL.run(args, None), 0)
            self.assertEqual(run.call_args.args[0], ['ddcutil', '--bus', '13', 'setvcp', '62', '-', '5', '--verify'])

    def test_invalid_values_fail_before_ddc(self):
        for tokens in [('brightness', '101'), ('brightness', '-1'), ('volume', 'toggle'),
                       ('mute', 'toggle'), ('get', 'XYZ'), ('get', '--helpful'),
                       ('set', 'E9', '65536'), ('set', 'E9', '-1'),
                       ('set', 'E9', '--bus'), ('input', 'Thunderbolt'),
                       ('capabilities', '--bus', '-1'),
                       ('capabilities', '--bus', '16', '--output', 'card0-DP-4')]:
            with self.subTest(tokens=tokens), patch.object(EXTERNAL.subprocess, 'run') as run, \
                    patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    DISPLAY.build_parser().parse_args(['external', *tokens])
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def output(self, root, name, status='connected', bus=16):
        path = root / name
        path.mkdir()
        (path / 'status').write_text(status)
        target = root / f'i2c-{bus}'
        target.mkdir(exist_ok=True)
        (path / 'ddc').symlink_to(target)
        return path

    def test_auto_selection_excludes_internal_and_disconnected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(EXTERNAL, 'DRM', Path(directory)):
            root = Path(directory)
            self.output(root, 'card0-eDP-1', bus=12)
            self.output(root, 'card0-DP-1', 'disconnected', 13)
            self.output(root, 'card0-DP-4')
            parser = DISPLAY.build_parser()
            args = parser.parse_args(['external', 'brightness', '40'])
            self.assertEqual(EXTERNAL.select_bus(args), 16)
            self.output(root, 'card0-DP-5', bus=17)
            with self.assertRaisesRegex(RuntimeError, 'Multiple external outputs'):
                EXTERNAL.select_bus(args)
            args.output = 'card0-DP-5'
            self.assertEqual(EXTERNAL.select_bus(args), 17)
            args.output = 'card0-eDP-1'
            with self.assertRaisesRegex(RuntimeError, 'No connected external'):
                EXTERNAL.select_bus(args)
            args.bus = 0
            self.assertEqual(EXTERNAL.select_bus(args), 0)

    def test_no_output_and_missing_dependency(self):
        args = DISPLAY.build_parser().parse_args(['external', 'brightness'])
        with patch.object(EXTERNAL, 'connected_outputs', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'No connected external'):
                EXTERNAL.select_bus(args)
        with patch.object(EXTERNAL.shutil, 'which', return_value=None), \
                patch.object(EXTERNAL.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'not installed'):
                EXTERNAL.run(args, None)
            run.assert_not_called()

    def test_help_and_completion_do_not_invoke_ddc(self):
        for tokens in [('external', '--help'), ('external', 'set', '--help')]:
            with patch.object(DISPLAY.sys, 'argv', ['agentoo-display', *tokens]), \
                    patch.object(EXTERNAL.subprocess, 'run') as run, patch('sys.stdout'):
                with self.assertRaises(SystemExit) as error:
                    DISPLAY.main()
                self.assertEqual(error.exception.code, 0)
                run.assert_not_called()
        result = subprocess.run([str(Path(DISPLAY.__file__).parent / 'agentoo'),
                                 '__complete', '3', 'display', 'external', ''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('command\tbrightness\t', result.stdout)
        self.assertIn('command\tcapabilities\t', result.stdout)


if __name__ == '__main__':
    unittest.main()
