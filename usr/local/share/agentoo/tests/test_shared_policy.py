"""Contracts shared by general commands, desktop commands and completion."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'lib'
sys.path.insert(0, str(LIB))
import completion
from desktop import blur, common, state, transparency, wallpaper
from xdg import xdg_directory


class SharedPolicyTests(unittest.TestCase):
    def test_xdg_directory_values(self):
        for variable, fallback in (('XDG_CONFIG_HOME', '.config'),
                                   ('XDG_CACHE_HOME', '.cache'),
                                   ('XDG_STATE_HOME', '.local/state')):
            for value in (None, '', 'relative', '/absolute'):
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, clear=True):
                    os.environ['HOME'] = '/home/example'
                    if value is not None:
                        os.environ[variable] = value
                    expected = Path('/absolute') if value == '/absolute' else Path('/home/example') / fallback
                    self.assertEqual(xdg_directory(variable, fallback), expected)
                    if variable == 'XDG_STATE_HOME':
                        self.assertEqual(state.state_path(), expected / 'agentoo/appearance.json')
                        self.assertEqual(wallpaper.state_directory(), expected / 'agentoo')

    def test_fonts_config_and_output_cache(self):
        # Use the command loader, retaining the functions' module globals for mocks.
        import runpy
        module = runpy.run_path(str(LIB.parents[2] / 'bin/agentoo-fonts'))
        for value in (None, '', 'relative', 'absolute'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, clear=True):
                home = Path(temporary)
                os.environ['HOME'] = str(home)
                if value is not None:
                    for key in ('XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
                        os.environ[key] = str(home / 'custom') if value == 'absolute' else value
                base = home / 'custom' if value == 'absolute' else home / '.config'
                self.assertEqual(module['config_home'](), base)
                cache = home / 'custom' if value == 'absolute' else home / '.cache'
                with patch.dict(module['browser_test'].__globals__, output=lambda *args: ''), contextlib.redirect_stdout(io.StringIO()):
                    module['browser_test'](SimpleNamespace(suite='smoke', output=None, no_open=True))
                self.assertTrue((cache / 'agentoo/fonts/preview.html').is_file())

    def test_window_choices_and_validation_share_groups(self):
        parser = argparse.ArgumentParser()
        state.window_option(parser)
        action = parser._option_string_actions['--window']
        self.assertIs(action.choices, common.WINDOW_GROUPS)
        self.assertIs(blur.GROUPS, common.WINDOW_GROUPS)
        self.assertIs(transparency.GROUPS, common.WINDOW_GROUPS)
        for validator in (blur.validate_data, transparency.validate_data):
            for group in common.WINDOW_GROUPS:
                self.assertEqual(validator({group: {}}), {group: {}})
            with self.assertRaises(RuntimeError):
                validator({'unknown': {}})

    def test_explicit_font_and_file_completers(self):
        parser = completion.python_parser('fonts')
        children = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices
        for command in ('test', 'set', 'doctor'):
            self.assertEqual(children[command]._option_string_actions['--font'].completion, 'fonts')
        for command in ('test', 'doctor'):
            action = children[command]._option_string_actions['--output']
            with contextlib.redirect_stdout(io.StringIO()) as output:
                completion.values_for(action, {})
            self.assertEqual(output.getvalue(), 'files\t\t\t\n')
        for name in ('font', 'output'):
            action = argparse.ArgumentParser().add_argument('--' + name)
            with contextlib.redirect_stdout(io.StringIO()) as output, patch.object(completion.subprocess, 'run') as run:
                completion.values_for(action, {})
            self.assertEqual(output.getvalue(), '')
            run.assert_not_called()
