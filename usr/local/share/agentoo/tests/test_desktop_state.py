"""Combined appearance imports, using disposable files."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SHARE = Path(__file__).resolve().parents[1]
ROOT = SHARE.parents[3]
sys.path.insert(0, str(SHARE / 'lib'))
from desktop import state
from desktop import effects
from desktop import blur
from desktop import transparency

spec = importlib.util.spec_from_loader('state_desktop', importlib.machinery.SourceFileLoader(
    'state_desktop', str(ROOT / 'usr/local/bin/agentoo-desktop')))
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


def native_preferences():
    path = str(SHARE / 'lib/desktop/preferences.lua')
    return ('agentoo_preferences = dofile(' + json.dumps(path) + ')\n'
            'agentoo_desktop_preferences = agentoo_preferences.load(agentoo_preferences.path(), nil, false, true)\n')


class DesktopStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agentoo-state-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'config/hypr'
        self.path = self.directory / 'agentoo-desktop.lua'
        self.file = self.root / 'theme.lua'
        self.parser = desktop.build_parser()
        for manager in (
            patch.dict(os.environ, XDG_STATE_HOME=str(self.root / 'state'), XDG_CONFIG_HOME=str(self.root / 'config'), XDG_RUNTIME_DIR=str(self.root / 'runtime'), HYPRLAND_INSTANCE_SIGNATURE='test'),
            patch.object(effects, 'hyprctl', return_value='ready'),
            patch.object(effects, 'reload_settings'),
            patch.object(blur, 'require_integration'), patch.object(blur, 'check_conflicts'),
            patch.object(blur, 'reload_saved'), patch.object(transparency, 'require_integration'),
            patch.object(transparency, 'conflicts', return_value=[]),
            patch.object(transparency, 'kitty_defaults', return_value=[1, True, [str(SHARE / 'lib/kitty/transparency.py')]]),
        ):
            manager.start()
            self.addCleanup(manager.stop)

    def apply(self, *tokens):
        args = self.parser.parse_args(tokens)
        with contextlib.redirect_stderr(io.StringIO()):
            return state.update(args, self.directory, desktop.atomic_write, self.parser)

    def save_import(self, data):
        self.file.write_text(state.dumps(data))

    def test_top_level_import_merges_all_sections_with_one_write_and_reload(self):
        self.directory.mkdir(parents=True)
        self.path.write_text(state.dumps({'gaps': {'inner': 4, 'outer': 8}, 'borders': {'width': 2},
                                        'transparency': {'kitty': {'focused': 5}}}))
        self.save_import({'gaps': {'inner': 6}, 'borders': {'focused': '#abcdef'},
                          'transparency': {'kitty': {'unfocused': 10}},
                          'animations': {'windows': 'popin', 'window_size': 80}})
        with patch.object(effects, 'reload_settings') as reload, patch.object(desktop, 'atomic_write', wraps=desktop.atomic_write) as write:
            self.apply('set', '--file', str(self.file))
        self.assertEqual(write.call_count, 1)
        self.assertEqual(reload.call_count, 1)
        data = state.read(self.path)
        self.assertEqual(data['gaps'], {'inner': 6, 'outer': 8})
        self.assertEqual(data['borders'], {'width': 2, 'focused': '#abcdef'})
        self.assertEqual(data['transparency'], {'kitty': {'focused': 5, 'unfocused': 10}})
        self.assertEqual(data['animations'], {'windows': 'popin', 'window_size': 80})
        self.assertNotIn('branches', json.dumps(data))

    def test_blur_import_uses_one_reload_for_entire_file(self):
        self.save_import({'blur': {'all': {'focused': True}, 'strength': {'size': 3}}, 'gaps': {'outer': 10}})
        with patch.object(blur, 'reload_saved') as reload, patch.object(effects, 'reload_settings') as general:
            self.apply('set', '--file', str(self.file))
        reload.assert_called_once_with({'all': {'focused': True}, 'strength': {'size': 3}})
        general.assert_not_called()

    def test_subcommand_reads_only_its_section_and_missing_section_is_an_error(self):
        self.save_import({'borders': {'width': 3}, 'gaps': {'typo': 10}})
        self.apply('borders', 'set', '--file', str(self.file))
        self.assertEqual(state.read(self.path), {'borders': {'width': 3}})
        with self.assertRaisesRegex(RuntimeError, 'no corners section'):
            self.apply('corners', 'set', '--file', str(self.file))

    def test_validation_happens_before_any_write_or_reload(self):
        for data in ({'gaps': {'inner': 4}, 'borders': {'typo': 2}}, {'wallpaper': 'image.png'},
                     {'animations': {'branches': {}}}, {'blur': {'all': {'focused': 'on'}}},
                     {'shadows': {'opacity': True}}, {'corners': {'radius': []}}):
            self.save_import(data)
            with self.subTest(data=data), patch.object(effects, 'reload_settings') as reload, self.assertRaises(RuntimeError):
                self.apply('set', '--file', str(self.file))
            reload.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_query_selects_only_relevant_section(self):
        self.directory.mkdir(parents=True)
        self.path.write_text(state.dumps({'borders': {'width': 2}, 'gaps': {'typo': 10}}))
        self.assertEqual(effects.read_state(self.path, selected='borders'), {'borders': {'width': 2}})

    def test_partial_import_preserves_animation_parameters_and_drops_incompatible_ones(self):
        self.save_import({'animations': {'windows': 'popin', 'window_size': 80}})
        self.apply('set', '--file', str(self.file))
        self.save_import({'animations': {'enabled': 'on'}})
        self.apply('set', '--file', str(self.file))
        self.assertEqual(state.read(self.path)['animations'], {'enabled': 'on', 'windows': 'popin', 'window_size': 80})
        self.save_import({'animations': {'windows': 'slide'}})
        self.apply('set', '--file', str(self.file))
        self.assertEqual(state.read(self.path)['animations'], {'enabled': 'on', 'windows': 'slide'})

    def test_failed_apply_restores_all_sections_and_leaves_import_untouched(self):
        self.directory.mkdir(parents=True)
        original = state.dumps({'gaps': {'inner': 5}, 'borders': {'width': 2}}).encode()
        self.path.write_bytes(original)
        self.save_import({'gaps': {'outer': 8}, 'borders': {'width': 4}})
        imported = self.file.read_bytes()
        with patch.object(effects, 'reload_settings', side_effect=[RuntimeError('bad reload'), None]), self.assertRaisesRegex(RuntimeError, 'bad reload'):
            self.apply('set', '--file', str(self.file))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.file.read_bytes(), imported)

    def test_file_argument_conflicts_help_and_completion_are_safe(self):
        entry = ROOT / 'usr/local/bin/agentoo'
        env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE='', XDG_STATE_HOME=str(self.root))
        for command in state.SECTIONS:
            for extra in (['--reset'], ['--focused', 'on'] if command == 'blur' else ['--focused', '5'] if command == 'transparency' else ['--enabled', 'on'] if command in ('animations', 'shadows', 'dimming') else ['--width', '2'] if command == 'borders' else ['--radius', '2'] if command == 'corners' else ['--inner', '2']):
                result = subprocess.run([str(entry), 'desktop', command, 'set', '--file', str(self.file), *extra], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stderr)
            result = subprocess.run([str(entry), '__complete', '5', 'desktop', command, 'set', '--file', ''], env=env, text=True, capture_output=True)
            self.assertIn('files\t', result.stdout)
        result = subprocess.run([str(entry), 'desktop', 'set', '--file', '--help'], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--file FILE', result.stdout)
        self.assertFalse(self.directory.exists())

    def run_desktop(self, *tokens):
        with patch.object(sys, 'argv', ['agentoo-desktop', *tokens]), contextlib.redirect_stderr(io.StringIO()):
            return desktop.main()

    def test_public_set_and_scoped_clear_preserve_other_preferences(self):
        self.run_desktop('gaps', 'set', '--inner', '6', '--outer', '10')
        self.run_desktop('transparency', 'set', '--focused', '5')
        self.run_desktop('transparency', 'set', '--window', 'browser', '--unfocused', '20')
        self.run_desktop('transparency', 'clear', '--window', 'browser')
        self.assertEqual(state.read(self.path), {
            'gaps': {'inner': 6, 'outer': 10}, 'transparency': {'all': {'focused': 5}}})
        self.run_desktop('gaps', 'clear')
        self.assertNotIn('gaps', state.read(self.path))
        self.assertEqual(state.read(self.path)['transparency'], {'all': {'focused': 5}})

    def test_public_top_level_set_and_clear_include_wallpaper_only_when_clearing(self):
        self.directory.mkdir(parents=True)
        wallpaper = self.root / 'state/agentoo/wallpaper'
        wallpaper.parent.mkdir(parents=True)
        wallpaper.write_text('/remembered/image.png\n')
        self.save_import({'gaps': {'inner': 6}, 'blur': {'strength': {'size': 3}}})
        self.run_desktop('set', '--file', str(self.file))
        self.assertEqual(wallpaper.read_text(), '/remembered/image.png\n')
        with patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root / 'runtime')):
            self.assertEqual(self.run_desktop('clear'), 0)
            self.assertEqual(state.read(self.path), {})
            self.assertFalse(wallpaper.exists())
            self.assertEqual(self.run_desktop('clear'), 0)

    def test_failed_aggregate_clear_rolls_back_appearance_and_keeps_wallpaper(self):
        self.directory.mkdir(parents=True)
        original = state.dumps({'gaps': {'inner': 6}})
        self.path.write_text(original)
        wallpaper = self.root / 'state/agentoo/wallpaper'
        wallpaper.parent.mkdir(parents=True)
        wallpaper.write_text('/remembered/image.png\n')
        with patch.object(blur, 'reload_saved', side_effect=RuntimeError('reload failed')):
            with self.assertRaisesRegex(RuntimeError, 'reload failed'):
                self.run_desktop('clear')
        self.assertEqual(self.path.read_text(), original)
        self.assertTrue(wallpaper.exists())

    def test_removed_forms_empty_set_and_invalid_combinations_have_no_effects(self):
        invalid = [('--file', 'agentoo-desktop.lua'), ('wallpaper', 'restore'),
                   ('clear', '--file', 'agentoo-desktop.lua'), ('set',)]
        for feature in state.SECTIONS:
            invalid.extend([(feature, 'set'), (feature, '--reset'),
                            (feature, 'restore'), (feature, 'clear', '--file', 'x')])
        invalid.extend([('transparency', '--focused', '5'),
                        ('blur', '--diagnose', 'clear'),
                        ('blur', '--diagnose', 'set', '--focused', 'on'),
                        ('blur', 'set', '--window', 'kitty', '--size', '3')])
        for tokens in invalid:
            with self.subTest(tokens=tokens), self.assertRaises(SystemExit) as error:
                self.run_desktop(*tokens)
            self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.directory.exists())

    def test_generated_file_is_a_reusable_preset_and_old_json_is_ignored(self):
        old = self.root / 'state/agentoo/appearance.json'
        old.parent.mkdir(parents=True)
        old.write_text('obsolete preferences are deliberately ignored')
        self.assertEqual(state.read(), {})
        self.run_desktop('gaps', 'set', '--inner', '7', '--outer', '11')
        original = state.read(self.path)
        self.file.write_bytes(self.path.read_bytes())
        self.run_desktop('gaps', 'clear')
        self.assertFalse(self.path.exists())
        self.run_desktop('set', '--file', str(self.file))
        self.assertEqual(state.read(self.path), original)
        self.assertEqual(old.read_text(), 'obsolete preferences are deliberately ignored')

    def test_invalid_native_preset_does_not_write_or_reload(self):
        for source in ('return {gaps={inner=true}}', 'return {gaps={inner=os.execute("false")}}',
                       'return (function() return {} end)()', 'return {gaps={inner=4}} trailing'):
            self.file.write_text(source)
            with self.subTest(source=source), patch.object(effects, 'reload_settings') as reload:
                with self.assertRaises(RuntimeError):
                    self.run_desktop('set', '--file', str(self.file))
                reload.assert_not_called()
            self.assertFalse(self.path.exists())

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
    def test_native_desktop_stack_loads_without_helpers_and_clear_recovers_conflicts(self):
        self.directory.mkdir(parents=True)
        modules = self.root / 'modules'
        modules.mkdir()
        for name in ('desktop', 'transparency', 'blur', 'effects', 'window-classes'):
            source = (ROOT / f'etc/xdg/hypr/{name}.lua').read_text()
            source = source.replace('/etc/xdg/hypr/', str(modules) + '/')
            source = source.replace('/usr/local/share/agentoo/lib/desktop/preferences.lua',
                                    str(SHARE / 'lib/desktop/preferences.lua'))
            (modules / f'{name}.lua').write_text(source)
        capture = (ROOT / 'etc/xdg/hypr/hyprland.lua').read_text().split('-- Hyprland discovers', 1)[0]
        config = self.root / 'native.lua'
        source = (capture + '\nhl.config({general={gaps_in=4},decoration={rounding=6,blur={enabled=false}}})\n'
                  'hl.window_rule = native_window_rule\nhl.animation = native_animation\n'
                  'io.popen = function() error("Appearance reload must not spawn helpers") end\n'
                  'require(' + json.dumps(str(modules / 'desktop.lua')) + ')\n')
        def verify(tail='', expected=0):
            config.write_text(source + tail)
            result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        data = {'gaps': {'inner': 9}, 'corners': {'radius': 10},
                'borders': {'width': 3}, 'animations': {'enabled': 'off'},
                'shadows': {'enabled': 'off'}, 'dimming': {'enabled': 'off'},
                'transparency': {'browser': {'focused': 5}}, 'blur': {'kitty': {'focused': True}}}
        self.path.write_text(state.dumps(data))
        verify('assert(hl.get_config("general.gaps_in").top == 9)\n'
               'assert(hl.get_config("decoration.rounding") == 10)\n'
               'assert(hl.get_config("decoration.blur.enabled") == true)\n'
               'assert(agentoo_transparency_loaded)\n'
               'assert(agentoo_effects_report)\n'
               'assert(agentoo_blur_report():find(' + json.dumps(blur.revision(data['blur'])) + '))\n')
        self.path.unlink()
        verify('assert(hl.get_config("decoration.rounding") == 6)\n')
        # Capture real authored rules, rather than scanning files during reload.
        source = source.replace('hl.window_rule = native_window_rule',
                                'hl.window_rule({match={class="kitty"},opacity="0.8"})\nhl.window_rule = native_window_rule')
        self.path.write_text(state.dumps({'transparency': {'all': {'focused': 5}}}))
        verify(expected=1)
        self.path.unlink()
        verify()

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
    def test_portable_animation_preferences_use_each_desktops_authored_settings(self):
        self.directory.mkdir(parents=True)
        self.path.write_text(state.dumps({'animations': {'windows': 'popin', 'window_size': 80}}))
        module = self.root / 'effects.lua'
        module.write_text(native_preferences() + (ROOT / 'etc/xdg/hypr/effects.lua').read_text())
        capture = (ROOT / 'etc/xdg/hypr/hyprland.lua').read_text().split('-- Hyprland discovers', 1)[0]
        for speed in (3, 7):
            config = self.root / 'hyprland.lua'
            config.write_text(capture + '\n'
                'hl.curve("custom", {type="bezier", points={{0.2,0.0},{0.8,1.0}}})\n'
                f'hl.animation({{leaf="windows",enabled=true,speed={speed},bezier="custom",style="slide"}})\n'
                'hl.animation({leaf="windowsOut",enabled=false})\n'
                'hl.animation = native_animation\n'
                'local calls={}\nlocal native=hl.animation\n'
                'hl.animation=function(s) calls[s.leaf]=s; return native(s) end\n'
                'dofile(' + json.dumps(str(module)) + ')\n'
                'assert(calls.windowsIn.style == "popin 80%")\n'
                f'assert(calls.windowsIn.speed == {speed})\n'
                'assert(calls.windowsIn.bezier == "custom")\n'
                'assert(calls.windowsOut.enabled == false)\n'
                'assert(calls.workspacesIn == nil)\n')
            result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                    text=True, capture_output=True, env=os.environ, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('branches', self.path.read_text())


if __name__ == '__main__':
    unittest.main()
