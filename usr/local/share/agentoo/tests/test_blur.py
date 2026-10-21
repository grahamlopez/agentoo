"""Blur contracts: no desktop changes; native parser verification when installed."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
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
sys.path.insert(0, str(SHARE))
import desktop_blur as blur
import desktop_effects as effects
import desktop_state as state


class Blur(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agentoo-blur-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'state/agentoo'
        self.env = patch.dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / 'config'),
                              XDG_STATE_HOME=str(self.root / 'state'), HYPRLAND_INSTANCE_SIGNATURE='test')
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cli = SHARE.parents[1] / 'bin/agentoo'

    def args(self, **values):
        return argparse.Namespace(**dict(window='all', focused=None, unfocused=None, size=None,
                                         passes=None, command='blur', action='set') | values)

    @staticmethod
    def write(path, value):
        return path.write_bytes(value) if isinstance(value, bytes) else path.write_text(value)

    @staticmethod
    def report(data=None, **values):
        return {'format': 'agentoo-blur-v2', 'revision': blur.revision(data or {}), 'baseline': 'off',
                'baseline_size': '8', 'baseline_passes': '1', 'option.enabled': 'off',
                'option.size': '8', 'option.passes': '1', 'option.new_optimizations': 'on'} | values

    def test_single_focus_change_never_enables_the_other_or_sets_strength(self):
        self.assertEqual(blur.adjusted({}, self.args(focused='on')), {'all': {'focused': True}})
        self.assertEqual(blur.adjusted({}, self.args(unfocused='on')), {'all': {'unfocused': True}})
        self.assertEqual(blur.adjusted({}, self.args(size=3, passes=1)), {'strength': {'size': 3, 'passes': 1}})

    def test_shared_values_clear_only_corresponding_category_overrides(self):
        original = {'all': {'focused': False, 'unfocused': True},
                    'kitty': {'focused': False, 'unfocused': False},
                    'browser': {'focused': True}, 'strength': {'size': 3}}
        changed = blur.adjusted(original, self.args(focused='on'))
        self.assertEqual(changed, {'all': {'focused': True, 'unfocused': True},
                                  'kitty': {'unfocused': False}, 'strength': {'size': 3}})
        self.assertFalse(original['kitty']['focused'])

    def test_validation_help_and_completion_have_no_effects(self):
        fake = self.root / 'bin'
        fake.mkdir()
        sentinel = self.root / 'unexpected-operation'
        executable = fake / 'hyprctl'
        executable.write_text('#!/bin/sh\ntouch "' + str(sentinel) + '"\nexit 1\n')
        executable.chmod(0o755)
        env = dict(os.environ, PATH=str(fake) + ':' + os.environ['PATH'])
        for args in (['--focused', 'yes'], ['--size', '0'], ['--size', '41'], ['--size', '2.5'],
                     ['--passes', '11'], ['--passes', '-1'], ['--window', 'kitty', '--size', '3'],
                     ['--reset', '--focused', 'off'], ['--diagnose', '--passes', '1'],
                     ['--reset', '--diagnose'], ['--focus', 'on']):
            result = subprocess.run([str(self.cli), 'desktop', 'blur', 'set', *args], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
        for args in (['desktop', 'blur', '--focused', 'bad', '--help'], ['help', 'desktop', 'blur']):
            result = subprocess.run([str(self.cli), *args], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--diagnose', result.stdout)
        for flag, choices in (('--window', ('all', 'kitty', 'browser')), ('--focused', ('on', 'off')),
                              ('--unfocused', ('on', 'off'))):
            result = subprocess.run([str(self.cli), '__complete', '5', 'desktop', 'blur', 'set', flag, ''],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for choice in choices:
                self.assertIn('candidate\t' + choice + '\t', result.stdout)
        result = subprocess.run([str(self.cli), '__complete', '4', 'desktop', 'blur', 'clear', ''],
                                env=env, capture_output=True, text=True)
        self.assertNotIn('option\t--diagnose\t', result.stdout)
        self.assertFalse(sentinel.exists())
        self.assertFalse(self.directory.exists())

    def test_bad_saved_state_and_relative_xdg(self):
        with patch.dict(os.environ, XDG_STATE_HOME='relative'):
            self.assertEqual(blur.state_path(), self.root / '.local/state/agentoo/appearance.json')
        path = self.root / 'invalid.json'
        for contents in ('[]', '{"other":{}}', '{"all":{"focused":"on"}}', '{"kitty":{"focused":1}}',
                         '{"strength":{"passes":true}}', '{"strength":{"size":1.5}}',
                         '{"strength":{"size":0}}', '{"all":{"focus":true}}', 'bad'):
            path.write_text(json.dumps({'blur': json.loads(contents)}) if contents not in ('bad', '[]') else contents)
            with self.assertRaises(RuntimeError):
                blur.read_state(path)
        path.write_bytes(b'\xff')
        with self.assertRaises(RuntimeError):
            blur.read_state(path)

    def test_save_preserves_other_sections(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        path.write_text(json.dumps({'transparency': {'all': {'focused': 15, 'unfocused': 25}}}))
        with patch.object(blur, 'require_integration'), patch.object(blur, 'conflicts', return_value=[]), \
             patch.object(blur, 'reload_saved') as reload:
            state.update(self.args(size=3, passes=1), self.directory, self.write)
            state.update(self.args(window='kitty', focused='on'), self.directory, self.write)
        data = blur.read_state(path)
        self.assertEqual(data, {'strength': {'size': 3, 'passes': 1}, 'kitty': {'focused': True}})
        reload.assert_called_with(data)
        self.assertEqual(json.loads(path.read_text())['transparency'], {'all': {'focused': 15, 'unfocused': 25}})

    def test_strength_update_explains_when_blur_remains_off(self):
        for enabled in ('off', 'on'):
            with self.subTest(enabled=enabled), patch.object(blur, 'require_integration'), \
                 patch.object(blur, 'conflicts', return_value=[]), \
                 patch.object(blur, 'reload_saved', return_value=self.report(**{'option.enabled': enabled})), \
                 redirect_stderr(io.StringIO()) as messages:
                self.assertEqual(state.update(self.args(size=10, passes=3), self.directory, self.write), 0)
            self.assertIn('Blur strength saved.', messages.getvalue())
            if enabled == 'off':
                self.assertIn('Blur remains off', messages.getvalue())
                self.assertIn('--focused on and/or --unfocused on', messages.getvalue())
            else:
                self.assertNotIn('Blur remains off', messages.getvalue())
            self.assertEqual(blur.read_state(self.directory / 'appearance.json'),
                             {'strength': {'size': 10, 'passes': 3}})

    def test_failure_rolls_back_exact_bytes_and_reloads_old_configuration(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        original = b'{"blur": {"all": {"focused": false}}}\n'
        path.write_bytes(original)
        with patch.object(blur, 'require_integration'), patch.object(blur, 'conflicts', return_value=[]), \
             patch.object(blur, 'reload_saved', side_effect=RuntimeError('bad reload')), \
             patch.object(effects, 'reload_settings') as command:
            with self.assertRaisesRegex(RuntimeError, 'bad reload'):
                state.update(self.args(focused='on'), self.directory, self.write)
        self.assertEqual(path.read_bytes(), original)
        command.assert_called_once_with()

    def test_full_reset_recovers_corrupt_state(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        path.write_text(json.dumps({'blur': {'bad': True}, 'gaps': {'inner': 4}}))
        with patch.object(blur, 'require_integration') as require, patch.object(blur, 'reload_saved') as reload:
            state.update(self.args(action='clear'), self.directory, self.write)
        require.assert_called_once_with(recover=True)
        reload.assert_called_once_with({})
        self.assertEqual(json.loads(path.read_text()), {'gaps': {'inner': 4}})

    def test_authored_conflict_blocks_change_but_not_full_reset(self):
        directory = self.root / 'config/hypr'
        directory.mkdir(parents=True)
        source = directory / 'agentoo-local.lua'
        source.write_text('-- no_blur = true\nhl.config({decoration={blur={enabled=false,size=4}}})\n'
                          'hl.window_rule({no_blur=true})\n')
        self.assertEqual(blur.conflicts(), [str(source) + ':3'])
        with patch.object(blur, 'require_integration'):
            with self.assertRaisesRegex(RuntimeError, 'Conflicting blur rules'):
                state.update(self.args(focused='on'), self.directory, self.write)
        self.assertFalse((self.directory / 'appearance.json').exists())
        with patch.object(blur, 'require_integration'), patch.object(blur, 'reload_saved'):
            state.update(self.args(action='clear'), self.directory, self.write)

    def test_strength_only_and_category_reset_use_the_same_conflict_policy_as_config_loading(self):
        with patch.object(blur, 'require_integration'), patch.object(blur, 'reload_saved'), \
             patch.object(blur, 'conflicts', return_value=['authored.lua:2']):
            state.update(self.args(size=3), self.directory, self.write)
            self.assertEqual(blur.read_state(self.directory / 'appearance.json'), {'strength': {'size': 3}})
            with self.assertRaisesRegex(RuntimeError, 'Conflicting blur rules'):
                blur.check_conflicts({'kitty': {'focused': True}})
            blur.check_conflicts({})
            blur.check_conflicts({'strength': {'size': 3}})
            self.write(self.directory / 'appearance.json', json.dumps({'blur': {'kitty': {'focused': True}, 'strength': {'size': 3}}}))
            state.update(self.args(window='kitty', action='clear'), self.directory, self.write)
            self.assertEqual(blur.read_state(self.directory / 'appearance.json'), {'strength': {'size': 3}})

    def test_queries_show_sources_without_creating_state(self):
        data = {'all': {'focused': True}, 'kitty': {'focused': False}, 'strength': {'passes': 2}}
        with patch.object(blur, 'conflicts', return_value=[]), redirect_stdout(io.StringIO()) as output:
            blur.show(data, 'all', self.report(data, **{'option.enabled': 'on'}))
        self.assertIn('off (override)', output.getvalue())
        self.assertIn('on (inherited: all)', output.getvalue())
        self.assertIn('off (configured default)', output.getvalue())
        self.assertIn('Size: 8 (configured default)', output.getvalue())
        self.assertIn('Passes: 2 (override)', output.getvalue())
        self.assertIn('Saved revision loaded in this session: yes', output.getvalue())
        self.assertIn('Current blur engine: on', output.getvalue())
        with patch.object(blur, 'live_report', side_effect=RuntimeError('offline')), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(blur.query(self.directory / 'appearance.json', 'all'), 0)
        self.assertIn('unknown (configured default)', output.getvalue())
        self.assertFalse(self.directory.exists())

    def test_reload_checks_the_loaded_revision(self):
        data = {'all': {'focused': True}}
        with patch.object(blur, 'hyprctl', side_effect=['ok', '', '']), \
             patch.object(blur, 'live_report', side_effect=[self.report(), self.report(data)]), \
             patch.object(blur.time, 'sleep'):
            self.assertEqual(blur.reload_saved(data), self.report(data))
        with patch.object(blur, 'hyprctl', side_effect=['ok', 'invalid rule']), \
             patch.object(blur, 'live_report', return_value=self.report(data)):
            with self.assertRaisesRegex(RuntimeError, 'invalid rule'):
                blur.reload_saved(data)
        with patch.object(blur, 'hyprctl', side_effect=['ok', 'old corrupt state', '']), \
             patch.object(blur, 'live_report', side_effect=[RuntimeError('not yet loaded'), self.report()]), \
             patch.object(blur.time, 'sleep'):
            blur.reload_saved({})

    def test_reload_request_and_verification_share_one_transport_timeout_budget(self):
        data = {'all': {'focused': True}}
        with patch.object(blur.time, 'monotonic', side_effect=[0, 0.25, 0.75, 1.25]), \
             patch.object(blur, 'hyprctl', side_effect=['ok', '']) as command, \
             patch.object(blur, 'live_report', return_value=self.report(data)) as report:
            blur.reload_saved(data)
        self.assertEqual(command.call_args_list[0].kwargs['timeout'], 1.75)
        self.assertEqual(command.call_args_list[1].kwargs['timeout'], 1.25)
        report.assert_called_once_with(timeout=0.75)

    def test_transport_enforces_the_supplied_timeout(self):
        executable = self.root / 'hyprctl'
        executable.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(1)\n')
        executable.chmod(0o755)
        with patch.dict(os.environ, PATH=str(self.root) + ':' + os.environ['PATH']):
            with self.assertRaisesRegex(RuntimeError, 'Cannot contact Hyprland'):
                blur.hyprctl('version', timeout=0.02)

    def test_diagnostics_are_read_only_and_do_not_claim_power_or_client_protocol_measurements(self):
        calls = []
        def command(*arguments, **keywords):
            calls.append(arguments)
            if arguments == ('configerrors',):
                return ''
            if arguments == ('systeminfo',):
                return 'Hyprland 0.56.2\nGPU information: test GPU\nGL ver: 3.2\nBackend: drm'
            if arguments == ('-j', 'clients'):
                return '[{"class":"kitty","mapped":true}]'
            if arguments[0] == 'repl':
                return '\n'.join(key + '\t' + value for key, value in self.report(**{'option.size': '10'}).items())
            self.fail('Unexpected operation: ' + repr(arguments))
        with patch.object(blur, 'hyprctl', side_effect=command), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(blur.diagnose(self.directory / 'appearance.json', 'all'), 0)
        self.assertIn('Hyprland 0.56.2', output.getvalue())
        self.assertIn('no GPU load or power measurement', output.getvalue())
        self.assertIn('Client blur regions and actual rendering are not verified', output.getvalue())
        self.assertIn('size: 10', output.getvalue())
        self.assertEqual(len(calls), 4)
        self.assertFalse(self.directory.exists())

    def test_diagnostics_report_config_errors_even_when_other_sources_succeed(self):
        def command(*arguments, **keywords):
            if arguments[0] == 'repl':
                return '\n'.join(key + '\t' + value for key, value in self.report().items())
            if arguments == ('configerrors',):
                return 'invalid personal window rule'
            if arguments == ('-j', 'clients'):
                return '[{"class":"kitty","mapped":true}]'
            return 'test GPU inventory'

        with patch.object(blur, 'hyprctl', side_effect=command), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(blur.diagnose(self.directory / 'appearance.json', 'all'), 1)
        self.assertIn('invalid personal window rule', output.getvalue())
        self.assertIn('test GPU inventory', output.getvalue())
        self.assertIn('Open window classes:\nkitty', output.getvalue())
        self.assertFalse(self.directory.exists())

    def test_diagnostics_continue_after_corrupt_state_and_fail_on_unavailable_core_options(self):
        self.directory.mkdir(parents=True)
        path = self.directory / 'appearance.json'
        path.write_bytes(b'broken\xff')
        def command(*arguments, **keywords):
            if arguments[0] == 'repl':
                return '\n'.join(key + '\t' + value for key, value in self.report(**{'option.size': 'unavailable'}).items())
            return '[]' if arguments == ('-j', 'clients') else ''
        with patch.object(blur, 'hyprctl', side_effect=command), \
             redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(blur.diagnose(self.directory / 'appearance.json', 'all'), 1)
        self.assertIn('Saved blur preferences: unavailable', output.getvalue())
        self.assertIn('Effective compositor options:', output.getvalue())
        self.assertIn('Cannot read appearance file', errors.getvalue())
        self.assertIn('Incomplete compositor snapshot: option.size', errors.getvalue())
        self.assertEqual(path.read_bytes(), b'broken\xff')
        path.unlink()
        with patch.object(blur, 'hyprctl', side_effect=command), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(blur.diagnose(self.directory / 'appearance.json', 'all'), 1)

    @unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
    def test_native_parser_checks_engine_behavior_and_authored_defaults(self):
        self.directory.mkdir(parents=True)
        source = SHARE.parents[3] / 'etc/xdg/hypr/blur.lua'
        module = self.root / 'blur.lua'
        module.write_text(source.read_text().replace('/usr/local/share/agentoo/desktop_blur.py',
                                                   str(SHARE / 'desktop_blur.py')).replace(
            '/etc/xdg/hypr/window-classes.lua', str(SHARE.parents[3] / 'etc/xdg/hypr/window-classes.lua')))
        for data, baseline, expected_engine in (
            ({}, False, False),
            ({'strength': {'size': 3, 'passes': 1}}, False, False),
            ({'kitty': {'focused': True}}, False, True),
            ({'kitty': {'unfocused': True}}, False, True),
            ({'all': {'focused': False, 'unfocused': False}}, True, False),
            ({}, True, True),
        ):
            with self.subTest(data=data, baseline=baseline):
                (self.directory / 'appearance.json').write_text(json.dumps({'blur': data}))
                config = self.root / 'hyprland.lua'
                config.write_text('hl.config({decoration={active_opacity=0.85,blur={enabled=' + str(baseline).lower()
                                  + ',size=8,passes=1}}})\ndofile(' + json.dumps(str(module)) + ')\n'
                                  + 'assert(hl.get_config("decoration.blur.enabled") == ' + str(expected_engine).lower() + ')\n'
                                  + 'assert(hl.get_config("decoration.active_opacity") > 0.84)\n'
                                  + 'assert(agentoo_blur_report():find("option.enabled\\t' + ('on' if expected_engine else 'off') + '"))\n'
                                  + 'assert(agentoo_blur_report():find("baseline\\t' + ('on' if baseline else 'off') + '"))\n'
                                  + 'assert(hl.get_config("decoration.blur.size") == ' + str(data.get('strength', {}).get('size', 8)) + ')\n'
                                  + 'hl.config({["decoration.blur.size"]=4})\n'
                                  + 'assert(agentoo_blur_report():find("option.size\\t4"))\n'
                                  + 'assert(agentoo_blur_report():find("baseline_size\\t8"))\n')
                result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
