"""Transparency CLI/state contracts and Kitty watcher without desktop effects."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

SHARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARE / 'lib'))
from desktop import transparency
from desktop import effects
from desktop import state


class Transparency(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / 'config'),
                              XDG_STATE_HOME=str(self.root / 'state'), HYPRLAND_INSTANCE_SIGNATURE='test')
        self.env.start()
        self.addCleanup(self.env.stop)
        self.directory = self.root / 'state/agentoo'

    def test_independent_states_and_shared_override_precedence(self):
        original = {'all': {'focused': 5, 'unfocused': 10},
                    'kitty': {'focused': 0, 'unfocused': 30}, 'browser': {'unfocused': 0}}
        changed = transparency.adjusted(original, 'all', focused=12)
        self.assertEqual(changed['kitty'], {'unfocused': 30})
        self.assertEqual(changed['browser'], {'unfocused': 0})
        self.assertEqual(transparency.effective(changed, 'kitty', 'focused'), 12)
        self.assertEqual(transparency.effective(changed, 'kitty', 'unfocused'), 30)
        self.assertEqual(original['kitty']['focused'], 0)

    def test_cli_invalid_arguments_and_help_have_no_effects(self):
        entry = SHARE.parents[1] / 'bin/agentoo'
        for args, status in [(['--focused', '91'], 2), (['--focused', '-1'], 2),
                             (['--focused', 'nan'], 2), (['--unfocused', 'inf'], 2),
                             (['--focus', '5'], 2), (['--reset', '--focused', '4'], 2),
                             (['--focused', 'invalid', '--help'], 0)]:
            result = subprocess.run([str(entry), 'desktop', 'transparency', 'set', *args],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, status, result.stderr)
        self.assertFalse(self.directory.exists())
        result = subprocess.run([str(entry), '__complete', '4', 'desktop', 'transparency', '--window', ''],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for group in ('all', 'kitty', 'browser'):
            self.assertIn('candidate\t' + group + '\t', result.stdout)
        self.assertFalse(self.directory.exists())

    def test_read_only_display_inheritance_and_default_sources(self):
        data = {'all': {'focused': 5}, 'kitty': {'unfocused': 20}}
        with patch.object(transparency, 'hyprctl', return_value='{"float": 0.9}'), \
             patch.object(transparency, 'kitty_defaults', return_value=[0.8, True, []]), \
             patch.object(transparency, 'conflicts', return_value=[]), redirect_stdout(io.StringIO()) as output:
            transparency.show(data, 'all')
        self.assertIn('5% (inherited: all)', output.getvalue())
        self.assertIn('20% (override)', output.getvalue())
        self.assertIn('10% (configured default)', output.getvalue())
        self.assertFalse(self.directory.exists())

    def test_state_validation_and_relative_xdg_fallback(self):
        with patch.dict(os.environ, XDG_STATE_HOME='relative'):
            self.assertEqual(transparency.state_path(), self.root / '.local/state/agentoo/appearance.json')
        path = self.root / 'invalid.json'
        for contents in ('[]', '{"all":{"focused":true}}', '{"all":{"focused":NaN}}',
                         '{"other":{}}', '{"kitty":{"focused":91}}', 'invalid'):
            path.write_text(json.dumps({'transparency': json.loads(contents)}) if contents not in ('invalid', '[]') else contents)
            with self.assertRaises(RuntimeError):
                transparency.read_state(path)

    def args(self, **values):
        return argparse.Namespace(command='transparency', action='set', window='browser', focused=5, unfocused=None, **values)

    @staticmethod
    def write(path, value):
        return path.write_bytes(value) if isinstance(value, bytes) else path.write_text(value)

    def test_reload_failure_restores_exact_saved_record(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        original = '{"transparency": {"browser": {"focused": 12}}}\n'
        path.write_text(original)
        with patch.object(transparency, 'require_integration'), patch.object(transparency, 'conflicts', return_value=[]), \
             patch.object(effects, 'reload_settings', side_effect=[RuntimeError('reload failed'), None]) as call:
            with self.assertRaisesRegex(RuntimeError, 'reload failed'):
                state.update(self.args(), self.directory, self.write)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(call.call_count, 2)

    def test_successful_save_and_full_reset_recover_corrupt_state(self):
        with patch.object(transparency, 'require_integration'), patch.object(transparency, 'conflicts', return_value=[]), \
             patch.object(effects, 'reload_settings'):
            state.update(self.args(), self.directory, lambda path, text: path.write_text(text))
        path = self.directory / 'appearance.json'
        self.assertEqual(json.loads(path.read_text()), {'transparency': {'browser': {'focused': 5}}})
        path.write_text(json.dumps({'transparency': {'bad': True}, 'gaps': {'inner': 4}}))
        args = argparse.Namespace(command='transparency', action='clear', window='all')
        with patch.object(transparency, 'require_integration') as require, \
             patch.object(effects, 'reload_settings'):
            state.update(args, self.directory, lambda path, text: path.write_text(text))
        require.assert_called_once_with(recover=True)
        self.assertEqual(json.loads(path.read_text()), {'gaps': {'inner': 4}})

    def test_authored_rule_conflict_prevents_any_saved_change(self):
        folder = self.root / 'config/hypr'
        folder.mkdir(parents=True)
        rule = folder / 'agentoo-local.lua'
        rule.write_text('-- opacity = "comment"\nhl.window_rule({opacity = "0.8"})\n')
        self.assertEqual(transparency.conflicts(), [str(rule) + ':2'])
        with patch.object(transparency, 'require_integration'):
            with self.assertRaisesRegex(RuntimeError, 'Conflicting transparency rules'):
                state.update(self.args(), self.directory, lambda path, text: path.write_text(text))
        self.assertFalse(self.directory.exists())

    def test_kitty_background_only_focus_live_changes_and_reset(self):
        spec = importlib.util.spec_from_file_location('agentoo_kitty_transparency', SHARE / 'lib/kitty/transparency.py')
        watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watcher)
        data = {'all': {'focused': 5, 'unfocused': 10}}
        options = SimpleNamespace(background_opacity=0.7, dynamic_background_opacity=True)
        fast = ModuleType('kitty.fast_data_types')
        fast.get_options = lambda: options
        fast.current_focused_os_window_id = lambda: 11
        utils = ModuleType('kitty.utils')
        utils.log_error = lambda message: self.fail(message)
        calls = []
        reloads = []
        boss = SimpleNamespace(all_windows=[SimpleNamespace(id=1, os_window_id=11),
                                           SimpleNamespace(id=2, os_window_id=11),
                                           SimpleNamespace(id=3, os_window_id=12)],
                               call_remote_control=lambda window, args: calls.append((window.os_window_id, args)),
                               load_config_file=lambda: reloads.append(True))
        watcher._state['read_state'] = lambda path: json.loads(json.dumps(data))
        with patch.dict(sys.modules, {'kitty.fast_data_types': fast, 'kitty.utils': utils}):
            watcher.refresh(boss)
            self.assertEqual(len(calls), 2)  # One call per OS window, not per split/tab.
            self.assertEqual([item[1][-1] for item in calls], ['0.95', '0.9'])
            calls.clear()
            watcher.refresh(boss)
            self.assertEqual(calls, [])
            data.clear()
            watcher.refresh(boss)
            self.assertEqual([item[1][-1] for item in calls], ['0.7', '0.7'])
            self.assertEqual(reloads, [True])
            calls.clear()
            watcher.refresh(boss)
            self.assertEqual(calls, [])

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser is required')
    def test_native_hyprland_parser_accepts_saved_focus_rules(self):
        self.directory.mkdir(parents=True)
        (self.directory / 'appearance.json').write_text(json.dumps({'transparency': {
            'all': {'focused': 5, 'unfocused': 10}, 'kitty': {'unfocused': 90},
            'browser': {'focused': 0.000001}}}))
        repository = SHARE.parents[3]
        module = self.root / 'transparency.lua'
        module.write_text((repository / 'etc/xdg/hypr/transparency.lua').read_text().replace(
            '/usr/local/share/agentoo/lib/desktop/transparency.py', str(SHARE / 'lib/desktop/transparency.py')).replace(
            '/etc/xdg/hypr/window-classes.lua', str(repository / 'etc/xdg/hypr/window-classes.lua')))
        config = self.root / 'hyprland.lua'
        config.write_text('dofile(' + json.dumps(str(module)) + ')\n')
        result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('kitty'), 'Kitty runtime is required')
    def test_watcher_reads_combined_state_in_native_kitty_without_cli_search_path(self):
        self.directory.mkdir(parents=True)
        (self.directory / 'appearance.json').write_text(json.dumps({'transparency': {'all': {'focused': 30, 'unfocused': 50}}}))
        code = ('import runpy, sys; '
                'original_path = list(sys.path); '
                f'm = runpy.run_path({str(SHARE / "lib/kitty/transparency.py")!r}, run_name="agentoo_watcher_check"); '
                'assert callable(m["on_load"]); '
                'assert m["read_preferences"]() == {"all": {"focused": 30, "unfocused": 50}}; '
                'assert sys.path == original_path; print("Watcher reads OK")')
        result = subprocess.run(['kitty', '+runpy', code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Watcher reads OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
