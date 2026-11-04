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

from desktop_fixtures import appearance_loader

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
        for module in (state, transparency):
            manager = patch.object(module, 'window_rule_conflicts', return_value=[])
            manager.start()
            self.addCleanup(manager.stop)

    def test_independent_states_and_shared_override_precedence(self):
        original = {'all': {'focused': 5, 'unfocused': 10},
                    'kitty': {'focused': 0, 'unfocused': 30}, 'browser': {'unfocused': 0}}
        changed = transparency.adjusted(original, 'all', focused=12)
        self.assertEqual(changed['kitty'], {'unfocused': 30})
        self.assertEqual(changed['browser'], {'unfocused': 0})
        self.assertEqual(transparency.effective(changed, 'kitty', 'focused'), 12)
        self.assertEqual(transparency.effective(changed, 'kitty', 'unfocused'), 30)
        self.assertEqual(original['kitty']['focused'], 0)

    def test_other_is_independent_and_all_clears_its_override(self):
        original = {'all': {'focused': 5}, 'kitty': {'focused': 0},
                    'browser': {'focused': 1}}
        changed = transparency.adjusted(original, 'other', focused=25)
        transparency.validate_data(changed)
        self.assertEqual(transparency.effective(changed, 'other', 'focused'), 25)
        for group in ('kitty', 'browser'):
            self.assertEqual(changed[group], original[group])
        self.assertNotIn('other', transparency.adjusted(changed, 'all', focused=10))

    def test_relative_adjustments_inherit_and_preserve_other_settings(self):
        original = {'all': {'focused': 10, 'unfocused': 20},
                    'browser': {'focused': 15}, 'kitty': {'focused': 0}}
        for group in ('kitty', 'browser', 'other'):
            with patch.object(transparency, 'active_category', return_value=group):
                changed = transparency.relative_adjusted(original, 'up', unfocused=True)
            self.assertEqual(changed[group]['unfocused'], 25)
            self.assertEqual(changed['all'], original['all'])
            self.assertEqual(changed['browser']['focused'], 15)
        self.assertNotIn('unfocused', original['kitty'])

    @unittest.skipUnless(shutil.which('lua'), 'lua is unavailable')
    def test_active_category_uses_shared_patterns(self):
        families = SHARE.parents[3] / 'etc/xdg/hypr/window-classes.lua'
        patterns = subprocess.check_output(
            ['lua', '-'], input=f'local f = dofile({json.dumps(str(families))}); print(f.kitty); print(f.browser)',
            text=True).strip()
        for window_class, expected in (('kitty', 'kitty'), ('agentoo-dropdown', 'kitty'),
                                       ('Firefox', 'browser'), ('prisma-access-browser', 'browser'),
                                       ('custom-app', 'other')):
            with patch.object(transparency, 'hyprctl', return_value=window_class + '\n' + patterns):
                self.assertEqual(transparency.active_category(), expected)

    def test_relative_defaults_limits_and_missing_active_window(self):
        for group in ('kitty', 'browser', 'other'):
            with patch.object(transparency, 'active_category', return_value=group), \
                 patch.object(transparency, 'configured_default', return_value=12) as default:
                self.assertEqual(transparency.relative_adjusted({}, 'down'), {group: {'focused': 7}})
                default.assert_called_once_with(group, 'focused')
                self.assertEqual(transparency.relative_adjusted({group: {'focused': 88}}, 'up')[group]['focused'], 90)
                self.assertEqual(transparency.relative_adjusted({group: {'focused': 2}}, 'down')[group]['focused'], 0)
        with patch.object(transparency, 'hyprctl', return_value='none'):
            with self.assertRaisesRegex(RuntimeError, 'No active window'):
                transparency.relative_adjusted({}, 'up')

    def test_repeated_relative_updates_use_saved_value(self):
        args = argparse.Namespace(command='transparency', action='up', window='all', unfocused=False)
        path = self.directory / 'appearance.json'
        with patch.object(transparency, 'require_integration'), \
             patch.object(transparency, 'active_category', return_value='browser'), \
             patch.object(transparency, 'configured_default', return_value=0), \
             patch.object(effects, 'reload_settings') as reload:
            state.update(args, path)
            state.update(args, path)
        self.assertEqual(json.loads(path.read_text()), {'transparency': {'browser': {'focused': 10}}})
        self.assertEqual(reload.call_count, 2)

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
        for group in ('all', 'kitty', 'browser', 'other'):
            self.assertIn('candidate\t' + group + '\t', result.stdout)
        self.assertFalse(self.directory.exists())

    def test_read_only_display_inheritance_and_default_sources(self):
        data = {'all': {'focused': 5}, 'kitty': {'unfocused': 20}}
        with patch.object(transparency, 'hyprctl', return_value='{"float": 0.9}'), \
             patch.object(transparency, 'kitty_defaults', return_value=[0.8, True, []]), \
             patch.object(state, 'window_rule_conflicts', return_value=[]), redirect_stdout(io.StringIO()) as output:
            transparency.show(data, 'all')
        self.assertIn('5% (inherited: all)', output.getvalue())
        self.assertIn('20% (override)', output.getvalue())
        self.assertIn('10% (configured default)', output.getvalue())
        self.assertFalse(self.directory.exists())

    def test_state_validation(self):
        path = self.root / 'invalid.json'
        for contents in ('[]', '{"all":{"focused":true}}', '{"all":{"focused":NaN}}',
                         '{"unknown":{}}', '{"kitty":{"focused":91}}', 'invalid'):
            path.write_text(json.dumps({'transparency': json.loads(contents)}) if contents not in ('invalid', '[]') else contents)
            with self.assertRaises(RuntimeError):
                transparency.read_state(path)

    def args(self, **values):
        return argparse.Namespace(command='transparency', action='set', window='browser', focused=5, unfocused=None, **values)

    def test_reload_failure_restores_exact_saved_record(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        original = '{"transparency": {"browser": {"focused": 12}}}\n'
        path.write_text(original)
        with patch.object(transparency, 'require_integration'), patch.object(state, 'window_rule_conflicts', return_value=[]), \
             patch.object(effects, 'reload_settings', side_effect=[RuntimeError('reload failed'), None]) as call:
            with self.assertRaisesRegex(RuntimeError, 'reload failed'):
                state.update(self.args(), self.directory / 'appearance.json')
        self.assertEqual(path.read_text(), original)
        self.assertEqual(call.call_count, 2)

    def test_successful_save_and_full_reset_recover_corrupt_state(self):
        with patch.object(transparency, 'require_integration'), patch.object(state, 'window_rule_conflicts', return_value=[]), \
             patch.object(effects, 'reload_settings'):
            state.update(self.args(), self.directory / 'appearance.json')
        path = self.directory / 'appearance.json'
        self.assertEqual(json.loads(path.read_text()), {'transparency': {'browser': {'focused': 5}}})
        path.write_text(json.dumps({'transparency': {'bad': True}, 'gaps': {'inner': 4}}))
        args = argparse.Namespace(command='transparency', action='clear', window='all')
        with patch.object(transparency, 'require_integration') as require, \
             patch.object(effects, 'reload_settings'):
            state.update(args, self.directory / 'appearance.json')
        require.assert_called_once_with(recover=True)
        self.assertEqual(json.loads(path.read_text()), {'gaps': {'inner': 4}})

    def test_active_rule_conflict_prevents_any_saved_change(self):
        with patch.object(transparency, 'require_integration'), \
             patch.object(state, 'window_rule_conflicts', return_value=['/outside/rules.lua:2']), \
             patch.object(effects, 'reload_settings') as reload:
            with self.assertRaisesRegex(RuntimeError, 'Conflicting transparency window rules.*') as error:
                state.update(self.args(), self.directory / 'appearance.json')
        self.assertIn('/outside/rules.lua:2', str(error.exception))
        self.assertFalse((self.directory / 'appearance.json').exists())
        reload.assert_not_called()

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
        refreshed = []
        boss = SimpleNamespace(all_windows=[SimpleNamespace(id=1, os_window_id=11, refresh=lambda: refreshed.append(11)),
                                           SimpleNamespace(id=2, os_window_id=11, refresh=lambda: refreshed.append(11)),
                                           SimpleNamespace(id=3, os_window_id=12, refresh=lambda: refreshed.append(12))],
                               call_remote_control=lambda window, args: calls.append((window.os_window_id, args)),
                               load_config_file=lambda: reloads.append(True))
        watcher.read_state = lambda path: json.loads(json.dumps(data))
        with patch.dict(sys.modules, {'kitty.fast_data_types': fast, 'kitty.utils': utils}):
            watcher.refresh(boss)
            self.assertEqual(len(calls), 2)  # One call per OS window, not per split/tab.
            self.assertEqual([item[1][-1] for item in calls], ['0.95', '0.9'])
            self.assertEqual(refreshed, [11, 12])
            calls.clear()
            refreshed.clear()
            watcher.refresh(boss)
            self.assertEqual(calls, [])
            self.assertEqual(refreshed, [])
            # A saved unfocused adjustment must repaint the idle OS window,
            # without needing any focus callback or touching the focused one.
            data['all']['unfocused'] = 20
            watcher.refresh(boss)
            self.assertEqual([item[1][-1] for item in calls], ['0.8'])
            self.assertEqual(refreshed, [12])
            calls.clear()
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
            '/etc/xdg/hypr/appearance.lua', str(appearance_loader(self.root))).replace(
            '/etc/xdg/hypr/window-classes.lua', str(repository / 'etc/xdg/hypr/window-classes.lua')).replace(
            '/etc/xdg/hypr/appearance-rules.lua', str(repository / 'etc/xdg/hypr/appearance-rules.lua')))
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
                'assert m["read_state"](m["state_path"]()) == {"all": {"focused": 30, "unfocused": 50}}; '
                'assert sys.path == original_path; '
                'assert "desktop.state" not in sys.modules; '
                'assert "desktop.effects" not in sys.modules; '
                'assert "desktop.blur" not in sys.modules; '
                'path = m["state_path"](); '
                f'path.write_text({json.dumps({"transparency": {"kitty": {"focused": 0}}})!r}); '
                'assert m["read_state"](path) == {"kitty": {"focused": 0}}; '
                'assert sys.path == original_path; print("Watcher reads OK")')
        result = subprocess.run(['kitty', '+runpy', code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Watcher reads OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
