import argparse
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

command = Path(__file__).resolve().parents[3] / 'bin/agentoo-fonts'
spec = importlib.util.spec_from_loader('fonts', SourceFileLoader('fonts', str(command)))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class FontsTests(unittest.TestCase):
    def test_eselect_only_reports_enabled_rules(self):
        listing = 'Available fontconfig .conf files (* is enabled):\n  [1] 10-hinting-full.conf\n  [2] 10-hinting-slight.conf *\n  [3] 50-user.conf *\n'
        with patch.object(f.shutil, 'which', return_value='/usr/bin/eselect'), patch.object(f, 'output', return_value=listing):
            names, source = f.fontconfig_rules()
        self.assertEqual(names, ['10-hinting-slight.conf', '50-user.conf'])

    def test_conflict_detection_is_conservative(self):
        self.assertEqual(f.fontconfig_warnings(['10-hinting-slight.conf', '10-yes-antialias.conf']), [])
        self.assertEqual(len(f.fontconfig_warnings(['10-hinting-full.conf', '10-hinting-slight.conf',
                                                 '10-no-antialias.conf', '10-yes-antialias.conf'])), 2)

    def test_selection_preserves_maps_features_and_other_geometry(self):
        old = 'symbol_map U+2800-U+28FF Unifont\nfont_features Example +zero\nmodify_font baseline 2\nmodify_font cell_height 95%\nfont_size 10\nfont_family Old\n'
        new = f.selection_text(old, 'Liberation Mono', 'Regular', 11, {'cell_height': '100%'})
        for line in old.splitlines()[:3]:
            self.assertIn(line, new)
        self.assertNotIn('font_family Old', new)
        self.assertNotIn('font_size 10', new)
        self.assertNotIn('cell_height 95%', new)
        self.assertIn('cell_height 100%', new)
        self.assertIn("font_family family='Liberation Mono' style=Regular", new)

    def test_save_and_revert_preserve_unrelated_configuration_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d) / 'kitty.conf', Path(d) / 'agentoo-fonts.conf'
            config.write_text('include host.conf\n')
            fragment.write_text('font_size 10\n')
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), patch.object(f, 'reload_kitties') as reload, patch('sys.stderr', new_callable=io.StringIO) as out:
                f.save_selection('font_size 11\n', expected='font_size 10\n')
                f.save_selection('font_size 10\n')
            self.assertIn('agentoo fonts set --restore', out.getvalue())
            self.assertEqual(reload.call_count, 2)
            self.assertEqual(fragment.read_text(), 'font_size 10\n')
            self.assertEqual(config.read_text().count('include agentoo-fonts.conf'), 1)
            self.assertIn('include host.conf', config.read_text())

    def test_failed_include_write_restores_fragment(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d) / 'kitty.conf', Path(d) / 'fonts.conf'
            fragment.write_text('original')
            real_write = f.write
            def fail_config(path, text):
                if path == config:
                    raise PermissionError('config is read-only')
                real_write(path, text)
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), patch.object(f, 'write', side_effect=fail_config), self.assertRaises(PermissionError):
                f.save_selection('changed')
            self.assertEqual(fragment.read_text(), 'original')

    def test_concurrent_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d) / 'kitty.conf', Path(d) / 'fonts.conf'
            fragment.write_text('newer edit\n')
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), self.assertRaisesRegex(ValueError, 'changed during preview'):
                f.save_selection('candidate\n', expected='old edit\n')
            self.assertEqual(fragment.read_text(), 'newer edit\n')
            self.assertFalse(config.exists())

    def test_symlink_config_does_not_partially_update_fragment(self):
        with tempfile.TemporaryDirectory() as d:
            target, config, fragment = (Path(d) / name for name in ('target', 'kitty.conf', 'fonts.conf'))
            target.write_text('original')
            config.symlink_to(target)
            fragment.write_text('original fragment')
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), self.assertRaisesRegex(ValueError, 'symlink'):
                f.save_selection('changed')
            self.assertEqual(fragment.read_text(), 'original fragment')

    def test_cancelled_preview_never_saves_or_reloads(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d) / 'kitty.conf', Path(d) / 'fonts.conf'
            fragment.write_text('font_size 10\n')
            a = argparse.Namespace(font=None, style=None, size=None, suite='smoke')
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), patch.object(f, 'kitty_settings', return_value={'paths': []}), patch.object(f, 'run') as run, patch.object(f, 'save_selection') as save, patch('sys.stdout', new_callable=io.StringIO):
                f.preview(a, chooser=True)
                command = run.call_args.args
            save.assert_not_called()
            self.assertIn('allow_remote_control=socket-only', command)
            self.assertEqual(fragment.read_text(), 'font_size 10\n')
            self.assertFalse(config.exists())

    def test_preview_save_passes_original_for_concurrency_check(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d) / 'kitty.conf', Path(d) / 'fonts.conf'
            fragment.write_text('original')
            def child(*cmd, **kwargs):
                state = json.loads(Path(cmd[-1]).read_text())
                Path(state['accepted']).write_text('chosen')
            with patch.object(f, 'kitty_paths', return_value=(config, fragment)), patch.object(f, 'kitty_settings', return_value={'paths': []}), patch.object(f, 'run', side_effect=child), patch.object(f, 'save_selection') as save:
                f.preview(argparse.Namespace(font=None, style=None, size=None, suite='smoke'))
            save.assert_called_once_with('chosen', expected='original')

    def test_missing_font_and_kitty_substitution_are_rejected(self):
        with patch.object(f, 'output', return_value='Liberation Mono\tRegular'), self.assertRaisesRegex(ValueError, 'not installed'):
            f.validate_font('Missing')
        with patch.object(f, 'output', return_value='Requested\tRegular'), patch.object(f, 'kitty_settings', return_value={'faces': {'medium': {'family': 'Substitute'}}}), self.assertRaisesRegex(ValueError, 'substituted'):
            f.validate_font('Requested')

    def test_geometry_preserves_units(self):
        self.assertEqual(f.adjust_geometry('95%', 1), '96%')
        self.assertEqual(f.adjust_geometry('2px', -1), '1px')
        self.assertEqual(f.adjust_geometry('-1', -1), '-2')
        self.assertEqual(f.adjust_geometry('50%', -1), '50%')

    def test_reload_only_signals_current_users_kitty_processes(self):
        class Proc:
            def __init__(self, pid, uid, name):
                self.name, self.uid, self.comm = str(pid), uid, name
            def stat(self):
                return argparse.Namespace(st_uid=self.uid)
            def __truediv__(self, name):
                return self
            def read_text(self):
                return self.comm
            def read_bytes(self):
                return b'kitty\0+runpy\0' if self.name == '14' else b'kitty\0'
        procs = [Proc(10, 1000, 'kitty'), Proc(11, 1000, 'kitty'),
                 Proc(12, 1001, 'kitty'), Proc(13, 1000, 'bash'), Proc(14, 1000, 'kitty')]
        with patch.object(f.Path, 'iterdir', return_value=iter(procs)), patch.object(f.os, 'getuid', return_value=1000), patch.object(f.os, 'kill') as kill, patch('sys.stdout', new_callable=io.StringIO):
            f.reload_kitties()
        self.assertEqual(kill.call_args_list, [((10, signal.SIGUSR1),), ((11, signal.SIGUSR1),)])

    def test_browser_preview_explains_actual_selection_without_preferences(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'preview.html'
            a = argparse.Namespace(suite='nerd', output=str(path), no_open=True)
            for installed, candidate, note in [
                    ('Symbols Nerd Font Mono', None, 'after the generic font'),
                    ('Liberation Mono', None, 'No supported Symbols Nerd Font'),
                    ('Symbols Nerd Font Mono', 'Liberation Mono', 'requested candidate')]:
                with patch.object(f, 'output', return_value=installed), patch.object(f, 'run') as run, patch('sys.stdout', new_callable=io.StringIO):
                    f.browser_test(a, candidate)
                run.assert_not_called()
                self.assertIn(note, path.read_text())
                self.assertNotIn('SELECTION_NOTE', path.read_text())

    def test_problem_text_distinguishes_coverage_and_matching(self):
        faces = [{'family': 'Test', 'ranges': [(0x300, 0x314)]}]
        with patch.object(f, 'query', return_value='candidate'):
            chars = f.problem_characters('\u0314ಠ', faces)
        self.assertEqual(chars[0]['combining'], 230)
        self.assertEqual(chars[0]['covering_families'], ['Test'])
        self.assertEqual(chars[1]['covering_families'], [])
        self.assertEqual(chars[1]['fontconfig_match'], 'candidate')

    def invoke(self, *args):
        with patch.object(f.sys, 'argv', ['agentoo fonts', *args]), patch('sys.stdout', new_callable=io.StringIO) as out:
            f.main()
        return out.getvalue()

    def test_help_is_plain_and_has_consistent_headings(self):
        class TerminalOutput(io.StringIO):
            def isatty(self):
                return True
        for command in [None, 'status', 'test', 'set', 'doctor']:
            argv = ['agentoo fonts'] + ([command] if command else []) + ['--help']
            with patch.object(f.sys, 'argv', argv), patch.dict(f.os.environ, {'FORCE_COLOR': '1', 'PYTHON_COLORS': '1'}), patch('sys.stdout', new_callable=TerminalOutput) as out, self.assertRaises(SystemExit) as error:
                f.main()
            self.assertEqual(error.exception.code, 0)
            help_text = out.getvalue()
            prefix = 'Usage: agentoo fonts' + (' ' + command if command else '')
            self.assertTrue(help_text.startswith(prefix), help_text)
            self.assertNotIn('Usage: Usage:', help_text)
            self.assertNotIn('\x1b', help_text)
            self.assertIn('Options:', help_text)
            if command is None:
                self.assertIn('Commands:\n  status', help_text)

    def test_status_is_the_default_and_accepts_filters(self):
        with patch.object(f, 'status') as status:
            self.invoke()
            status.assert_called_once_with('', False)
            status.reset_mock()
            self.invoke('status', '--filter', 'mono', '--nerd')
            status.assert_called_once_with('mono', True)

    def test_test_routes_terminal_candidate_size_style_and_interactive(self):
        with patch.object(f, 'terminal_test') as terminal, patch.object(f, 'preview') as preview:
            self.invoke('test', 'greek')
            self.assertEqual(terminal.call_args.args[0].suite, 'greek')
            preview.assert_not_called()
            self.invoke('test', 'nerd', '--font', 'Example')
            self.assertEqual(preview.call_args.args[0].font, 'Example')
            self.assertEqual(preview.call_args.args[0].suite, 'nerd')
            self.invoke('test', '--interactive')
            self.assertIsNone(preview.call_args.args[0].font)
            self.invoke('test', '--size', '12')
            self.assertEqual(preview.call_args.args[0].size, 12)
            with patch.object(f, 'kitty_settings', return_value={'faces': {'medium': {'family': 'Current'}}}):
                self.invoke('test', '--style', 'Bold')
            self.assertEqual(preview.call_args.args[0].font, 'Current')

    def test_test_routes_browser_candidate_without_opening_kitty(self):
        with patch.object(f, 'browser_test') as browser, patch.object(f, 'preview') as preview:
            self.invoke('test', 'nerd', '--font', 'Symbols Nerd Font Mono', '--target', 'firefox', '--no-open')
            self.assertEqual(browser.call_args.args[0].suite, 'nerd')
            self.assertTrue(browser.call_args.args[0].no_open)
            self.assertEqual(browser.call_args.args[1], 'Symbols Nerd Font Mono')
            preview.assert_not_called()

    def test_set_restore_is_exact_and_excludes_selection_options(self):
        old = 'font_size 11\nsymbol_map U+2800-U+28FF Unifont\n'
        with patch.object(f, 'save_selection') as save, patch.object(f, 'preview') as preview:
            self.invoke('set', '--restore', old)
            save.assert_called_once_with(old)
            preview.assert_not_called()
            save.reset_mock()
            self.invoke('set', '--restore', '')
            save.assert_called_once_with('')
            for extra in [('--font', 'Example'), ('--size', '12'), ('--style', 'Bold'), ('--suite', 'all')]:
                with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
                    self.invoke('set', '--restore', old, *extra)
                self.assertEqual(error.exception.code, 2)

    def test_removed_commands_and_analysis_render_combination_are_rejected(self):
        for args in [('list',), ('preview',), ('coverage',), ('explain',), ('kitty-config',),
                     ('doctor', '--font', 'Example', '--render')]:
            with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
                self.invoke(*args)
            self.assertEqual(error.exception.code, 2)

    def test_face_analysis_exposes_substitution_and_single_face_gaps(self):
        with patch.object(f, 'output', return_value='Substitute\n/test/font.ttf\n20-7e'):
            result = f.face_analysis('Requested', 'greek')
        self.assertEqual(result['pattern'], 'Requested')
        self.assertEqual(result['family'], 'Substitute')
        self.assertIn('U+1FA7', result['coverage']['greek']['missing'])



if __name__ == '__main__':
    unittest.main()
