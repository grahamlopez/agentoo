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
sys.path.insert(0, str(SHARE))
import desktop_state as state
import desktop_effects as effects
import desktop_blur as blur
import desktop_transparency as transparency

spec = importlib.util.spec_from_loader('state_desktop', importlib.machinery.SourceFileLoader(
    'state_desktop', str(ROOT / 'usr/local/bin/agentoo-desktop')))
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agentoo-state-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'agentoo'
        self.path = self.directory / 'appearance.json'
        self.file = self.root / 'theme.json'
        self.parser = desktop.build_parser()
        for manager in (
            patch.dict(os.environ, XDG_STATE_HOME=str(self.root), HYPRLAND_INSTANCE_SIGNATURE='test'),
            patch.object(effects, 'hyprctl', return_value='ready'),
            patch.object(effects, 'reload_settings'),
            patch.object(blur, 'require_integration'), patch.object(blur, 'check_conflicts'),
            patch.object(blur, 'reload_saved'), patch.object(transparency, 'require_integration'),
            patch.object(transparency, 'conflicts', return_value=[]),
            patch.object(transparency, 'kitty_defaults', return_value=[1, True, [str(SHARE / 'kitty/transparency.py')]]),
        ):
            manager.start()
            self.addCleanup(manager.stop)

    def apply(self, *tokens):
        args = self.parser.parse_args(tokens)
        with contextlib.redirect_stderr(io.StringIO()):
            return state.update(args, self.directory, desktop.atomic_write, self.parser)

    def save_import(self, data):
        self.file.write_text(json.dumps(data))

    def test_top_level_import_merges_all_sections_with_one_write_and_reload(self):
        self.directory.mkdir()
        self.path.write_text(json.dumps({'gaps': {'inner': 4, 'outer': 8}, 'borders': {'width': 2},
                                        'transparency': {'kitty': {'focused': 5}}}))
        self.save_import({'gaps': {'inner': 6}, 'borders': {'focused': '#abcdef'},
                          'transparency': {'kitty': {'unfocused': 10}},
                          'animations': {'windows': 'popin', 'window_size': 80}})
        with patch.object(effects, 'reload_settings') as reload, patch.object(desktop, 'atomic_write', wraps=desktop.atomic_write) as write:
            self.apply('--file', str(self.file))
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
            self.apply('--file', str(self.file))
        reload.assert_called_once_with({'all': {'focused': True}, 'strength': {'size': 3}})
        general.assert_not_called()

    def test_subcommand_reads_only_its_section_and_missing_section_is_an_error(self):
        self.save_import({'borders': {'width': 3}, 'gaps': {'typo': 10}})
        self.apply('borders', '--file', str(self.file))
        self.assertEqual(state.read(self.path), {'borders': {'width': 3}})
        with self.assertRaisesRegex(RuntimeError, 'no corners section'):
            self.apply('corners', '--file', str(self.file))

    def test_validation_happens_before_any_write_or_reload(self):
        for data in ({'gaps': {'inner': 4}, 'borders': {'typo': 2}}, {'wallpaper': 'image.png'},
                     {'animations': {'branches': {}}}, {'blur': {'all': {'focused': 'on'}}},
                     {'shadows': {'opacity': True}}, {'corners': {'radius': []}}):
            self.save_import(data)
            with self.subTest(data=data), patch.object(effects, 'reload_settings') as reload, self.assertRaises(RuntimeError):
                self.apply('--file', str(self.file))
            reload.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_query_selects_only_relevant_section(self):
        self.directory.mkdir()
        self.path.write_text(json.dumps({'borders': {'width': 2}, 'gaps': {'typo': 10}}))
        self.assertEqual(effects.read_state(self.path, selected='borders'), {'borders': {'width': 2}})

    def test_partial_import_preserves_animation_parameters_and_drops_incompatible_ones(self):
        self.save_import({'animations': {'windows': 'popin', 'window_size': 80}})
        self.apply('--file', str(self.file))
        self.save_import({'animations': {'enabled': 'on'}})
        self.apply('--file', str(self.file))
        self.assertEqual(state.read(self.path)['animations'], {'enabled': 'on', 'windows': 'popin', 'window_size': 80})
        self.save_import({'animations': {'windows': 'slide'}})
        self.apply('--file', str(self.file))
        self.assertEqual(state.read(self.path)['animations'], {'enabled': 'on', 'windows': 'slide'})

    def test_failed_apply_restores_all_sections_and_leaves_import_untouched(self):
        self.directory.mkdir()
        original = b'{"gaps": {"inner": 5}, "borders": {"width": 2}}\n'
        self.path.write_bytes(original)
        self.save_import({'gaps': {'outer': 8}, 'borders': {'width': 4}})
        imported = self.file.read_bytes()
        with patch.object(effects, 'reload_settings', side_effect=[RuntimeError('bad reload'), None]), self.assertRaisesRegex(RuntimeError, 'bad reload'):
            self.apply('--file', str(self.file))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.file.read_bytes(), imported)

    def test_file_argument_conflicts_help_and_completion_are_safe(self):
        entry = ROOT / 'usr/local/bin/agentoo'
        env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE='', XDG_STATE_HOME=str(self.root))
        for command in state.SECTIONS:
            for extra in (['--reset'], ['--focused', 'on'] if command == 'blur' else ['--focused', '5'] if command == 'transparency' else ['--enabled', 'on'] if command in ('animations', 'shadows', 'dimming') else ['--width', '2'] if command == 'borders' else ['--radius', '2'] if command == 'corners' else ['--inner', '2']):
                result = subprocess.run([str(entry), 'desktop', command, '--file', str(self.file), *extra], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stderr)
            result = subprocess.run([str(entry), '__complete', '4', 'desktop', command, '--file', ''], env=env, text=True, capture_output=True)
            self.assertIn('files\t', result.stdout)
        result = subprocess.run([str(entry), 'desktop', '--file', '--help'], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--file FILE', result.stdout)
        self.assertFalse(self.directory.exists())

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
    def test_portable_animation_preferences_use_each_desktops_authored_settings(self):
        self.directory.mkdir()
        self.path.write_text(json.dumps({'animations': {'windows': 'popin', 'window_size': 80}}))
        module = self.root / 'effects.lua'
        module.write_text((ROOT / 'etc/xdg/hypr/effects.lua').read_text().replace(
            '/usr/local/share/agentoo/desktop_effects.py', str(SHARE / 'desktop_effects.py')))
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
