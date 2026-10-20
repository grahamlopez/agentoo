"""Desktop effects contracts; isolated files and native config parsing only."""
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
import desktop_effects as effects

spec = importlib.util.spec_from_loader('effects_desktop', importlib.machinery.SourceFileLoader(
    'effects_desktop', str(ROOT / 'usr/local/bin/agentoo-desktop')))
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class EffectsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agentoo-effects-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'agentoo'
        self.parser = desktop.build_parser()

    def args(self, *tokens):
        return self.parser.parse_args(tokens)

    def run_effect(self, *tokens):
        with contextlib.redirect_stderr(io.StringIO()):
            return effects.run(self.args(*tokens), self.directory, desktop.atomic_write, self.parser)

    def test_help_completion_and_input_validation_need_no_session(self):
        env = dict(os.environ, XDG_STATE_HOME=str(self.root), HYPRLAND_INSTANCE_SIGNATURE='')
        entry = ROOT / 'usr/local/bin/agentoo'
        for command in effects.COMMANDS:
            result = subprocess.run([str(entry), 'desktop', command, '--radius', 'bad', '--help'],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        for flag, choices in (('--windows', effects.WINDOW_STYLES), ('--workspaces', effects.WORKSPACE_STYLES)):
            result = subprocess.run([str(entry), '__complete', '4', 'desktop', 'animations', flag, ''],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for choice in choices:
                self.assertIn('candidate\t' + choice + '\t', result.stdout)
        for tokens in [('corners', '--radius', '21'), ('gaps', '--inner', '-1'),
                       ('borders', '--width', '1.5'), ('shadows', '--opacity', 'nan'),
                       ('borders', '--focused', '#bad'), ('shadows', '--color', '#000000ff'),
                       ('animations', '--duration', '0'), ('animations', '--window-size', '80'),
                       ('animations', '--workspaces', 'fade', '--workspace-distance', '30'),
                       ('corners', '--radius', '3', '--reset')]:
            with self.subTest(tokens=tokens), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                effects.validate(self.args(*tokens), self.parser)
            self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.directory.exists())

    def test_border_gradient_validation_and_independent_updates(self):
        self.assertEqual(effects.gradient('#ABCDEF, #12345680'), '#abcdef,#12345680')
        self.assertEqual(len(effects.gradient(','.join(['#abcdef'] * 10)).split(',')), 10)
        for value in ('', '#abcdef,', ',#abcdef', '#abcdef,,#123456',
                      '#12345g,#abcdef', ','.join(['#abcdef'] * 11)):
            with self.subTest(value=value), self.assertRaises(effects.argparse.ArgumentTypeError):
                effects.gradient(value)
        for value in ('-1', '361', 'nan'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args('borders', '--focused-angle', value)
        with patch.dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE='test'), \
             patch.object(effects, 'hyprctl', return_value='ready'), patch.object(effects, 'reload_settings'):
            self.run_effect('borders', '--focused', '#abcdef,#12345680', '--unfocused', '#654321')
            self.run_effect('borders', '--focused-angle', '45.5')
            self.run_effect('borders', '--unfocused-angle', '0')
            self.assertEqual(effects.read_state(self.directory / 'appearance.json')['borders'], {
                'focused': '#abcdef,#12345680', 'unfocused': '#654321',
                'focused_angle': 45.5, 'unfocused_angle': 0})
            self.run_effect('borders', '--focused', '#000000')
            self.assertEqual(effects.read_state(self.directory / 'appearance.json')['borders']['focused_angle'], 45.5)
            self.run_effect('borders', '--reset')
            self.assertEqual(json.loads((self.directory / 'appearance.json').read_text()), {})

    def test_query_creates_no_state_and_does_not_guess_defaults(self):
        with patch.dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=''), contextlib.redirect_stdout(io.StringIO()) as output:
            self.run_effect('corners')
        self.assertIn('unavailable (configured default)', output.getvalue())
        self.assertFalse(self.directory.exists())

    def test_independent_updates_reset_and_failed_reload(self):
        with patch.dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE='test'), \
             patch.object(effects, 'hyprctl', return_value='ready'), patch.object(effects, 'reload_settings'):
            self.run_effect('corners', '--radius', '8')
            self.run_effect('corners', '--power', '4')
            self.run_effect('shadows', '--size', '12')
            data = effects.read_state(self.directory / 'appearance.json')
            self.assertEqual(data['corners'], {'radius': 8, 'power': 4})
            self.assertEqual(data['shadows'], {'size': 12})
            original = (self.directory / 'appearance.json').read_bytes()
            with patch.object(effects, 'reload_settings', side_effect=[RuntimeError('bad config'), None]), self.assertRaises(RuntimeError):
                self.run_effect('corners', '--radius', '10')
            self.assertEqual((self.directory / 'appearance.json').read_bytes(), original)
            self.run_effect('corners', '--reset')
            self.assertEqual(effects.read_state(self.directory / 'appearance.json'), {'shadows': {'size': 12}})
            self.run_effect('shadows', '--reset')
            self.assertEqual(json.loads((self.directory / 'appearance.json').read_text()), {})

    def test_bad_saved_values_fail_before_transport_and_group_reset_recovers(self):
        self.directory.mkdir()
        path = self.directory / 'appearance.json'
        path.write_text(json.dumps({'corners': {'radius': '3\nmalicious'}, 'gaps': {'outer': 4}}))
        with self.assertRaises(RuntimeError):
            effects.read_state(path)
        self.assertEqual(effects.read_state(path, 'corners'), {'gaps': {'outer': 4}})

    def test_animation_updates_store_only_public_preferences(self):
        updated = effects.animation_update({}, {'windows': 'popin', 'window_size': 80})
        self.assertEqual(updated, {'windows': 'popin', 'window_size': 80})
        self.assertEqual(effects.animation_update(updated, {'duration': 250}),
                         {'windows': 'popin', 'window_size': 80, 'duration': 250})
        self.assertEqual(effects.animation_update(updated, {'windows': 'slide'}), {'windows': 'slide'})

    def test_inherited_native_animation_nodes_are_resolved(self):
        nodes = [{'name': name, 'overridden': False, 'enabled': False, 'speed': 0, 'bezier': '', 'style': ''}
                 for name in effects.PARENTS]
        nodes.append({'name': 'global', 'overridden': True, 'enabled': True, 'speed': 8, 'bezier': 'default', 'style': ''})
        with patch.object(effects, 'hyprctl', return_value=json.dumps([nodes, []])):
            self.assertEqual(effects.live_animations()['windowsIn']['speed'], 8)

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
    def test_native_config_translation_styles_and_reset(self):
        self.directory.mkdir()
        module = self.root / 'effects.lua'
        module.write_text((ROOT / 'etc/xdg/hypr/effects.lua').read_text().replace(
            '/usr/local/share/agentoo/desktop_effects.py', str(SHARE / 'desktop_effects.py')))
        env = dict(os.environ, XDG_STATE_HOME=str(self.root))
        cases = [({}, ''), ({
            'corners': {'radius': 10, 'power': 4}, 'gaps': {'inner': 3, 'outer': 9},
            'borders': {'width': 2, 'focused': '#12345680', 'unfocused': '#abcdef'},
            'shadows': {'enabled': 'on', 'size': 12, 'opacity': 35, 'color': '#000000', 'offset_y': 3},
            'dimming': {'enabled': 'on', 'strength': 15, 'modal': 'off'},
        }, '''assert(hl.get_config("decoration.rounding") == 10)
assert(hl.get_config("decoration.rounding_power") == 4)
assert(hl.get_config("general.gaps_out").top == 9)
assert(hl.get_config("general.col.active_border").colors[1] == "0x80123456")
assert(hl.get_config("decoration.shadow.color").colors[1] == "0x59000000")
assert(hl.get_config("decoration.shadow.offset").x == 7)
assert(hl.get_config("decoration.shadow.offset").y == 3)
assert(hl.get_config("decoration.dim_strength") > 0.149)
assert(hl.get_config("decoration.dim_modal") == false)
assert(hl.get_config("decoration.blur.enabled") == false)
'''), ({'shadows': {'opacity': 50}}, 'assert(hl.get_config("decoration.shadow.color").colors[1] == "0x80123456")'),
                 ({'shadows': {'color': '#abcdef'}}, 'assert(hl.get_config("decoration.shadow.color").colors[1] == "0x40ABCDEF")')]
        cases.extend([
            ({'borders': {'focused': '#112233,#44556680,#778899', 'focused_angle': 45.5,
                          'unfocused': '#abcdef,#fedcba', 'unfocused_angle': 90}},
             'local g=hl.get_config("general.col.active_border")\n'
             'assert(#g.colors == 3 and g.colors[2] == "0x80445566")\n'
             'assert(math.abs(g.angle - 45.5) < 0.01)\n'
             'assert(math.abs(hl.get_config("general.col.inactive_border").angle - 90) < 0.01)\n'),
            ({'borders': {'focused_angle': 0}},
             'local g=hl.get_config("general.col.active_border")\n'
             'assert(#g.colors == 2 and g.colors[2] == "0x80654321")\n'
             'assert(g.angle == 0)\n'),
            ({'borders': {'focused': '#abcdef'}},
             'local g=hl.get_config("general.col.active_border")\n'
             'assert(#g.colors == 1 and math.abs(g.angle - 30) < 0.01)\n'),
            ({'borders': {'focused': ','.join(['#123456'] * 10)}},
             'assert(#hl.get_config("general.col.active_border").colors == 10)\n'),
        ])
        for style in effects.WINDOW_STYLES:
            for extra in (['', ' left'] if style == 'slide' else ['', ' 80%'] if style == 'popin' else ['']):
                cases.append(({'animations': {'windows': style, **({'window_direction': 'left'} if extra == ' left' else {'window_size': 80} if extra else {})}}, ''))
        for style in effects.WORKSPACE_STYLES:
            cases.append(({'animations': {'workspaces': style, **({'workspace_distance': 30} if style.startswith('slide') else {})}}, ''))
        for data, assertions in cases:
            with self.subTest(data=data):
                (self.directory / 'appearance.json').write_text(json.dumps(data))
                config = self.root / 'hyprland.lua'
                config.write_text('hl.config({general={["col.active_border"]={colors={"rgb(123456)","rgba(65432180)"},angle=30}},decoration={blur={enabled=false},shadow={color="rgba(12345640)",offset={7,8}}}})\n'
                                  'dofile(' + json.dumps(str(module)) + ')\n' + assertions + '\n'
                                  'assert(agentoo_effects_report():find("corners.radius"))\n')
                result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                        capture_output=True, text=True, timeout=15, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.directory / 'appearance.json').unlink()
        config.write_text('hl.config({decoration={rounding=6}})\ndofile(' + json.dumps(str(module)) + ')\n'
                          'assert(hl.get_config("decoration.rounding") == 6)\n')
        result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                capture_output=True, text=True, timeout=15, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
