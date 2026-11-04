"""Active-rule ownership uses native Hyprland parsing, without a live session."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from desktop_fixtures import appearance_loader

SHARE = Path(__file__).resolve().parents[1]
ROOT = SHARE.parents[3]
HYPR = ROOT / 'etc/xdg/hypr'
sys.path.insert(0, str(SHARE / 'lib'))
from desktop import common


class ConflictTransportTests(unittest.TestCase):
    def test_read_only_query_reports_locations_and_rejects_missing_integration(self):
        with patch.object(common, 'hyprctl', return_value='ready\n/outside/rules.lua:4\n/host.lua:9') as ipc:
            self.assertEqual(common.window_rule_conflicts('blur'), ['/outside/rules.lua:4', '/host.lua:9'])
        self.assertEqual(ipc.call_args.args[0], 'repl')
        self.assertIn('"ready\\n" ..', ipc.call_args.args[1])
        self.assertIn('agentoo_window_rule_conflicts("blur")', ipc.call_args.args[1])
        with patch.object(common, 'hyprctl', return_value='ready'):
            self.assertEqual(common.window_rule_conflicts('transparency'), [])
        with patch.object(common, 'hyprctl', return_value='unavailable'):
            with self.assertRaisesRegex(RuntimeError, 'appearance-rules.lua integration'):
                common.window_rule_conflicts('transparency')

    def test_transport_errors_are_not_reported_as_conflicts(self):
        for report in ('unknown request', '', 'error: Lua query failed'):
            with self.subTest(report=report), patch.object(common, 'hyprctl', return_value=report):
                with self.assertRaisesRegex(RuntimeError, 'Cannot query Hyprland appearance window rules'):
                    common.window_rule_conflicts('transparency')


@unittest.skipUnless(shutil.which('Hyprland'), 'Hyprland parser required')
class ActiveRuleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='agentoo-conflict-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.personal = self.root / 'config/hypr'
        self.personal.mkdir(parents=True)
        self.hosts = self.root / 'hosts'
        self.hosts.mkdir()
        self.selector = self.root / 'target-host'
        self.selector.write_text('GENTOO_TARGET_HOST="test"\n')
        self.state = self.root / 'state/agentoo/appearance.json'
        self.state.parent.mkdir(parents=True)
        self.outside = self.root / 'outside.lua'
        self.local = self.personal / 'agentoo-local.lua'
        self.local.write_text('')
        self.host = self.hosts / 'test.lua'
        self.host.write_text('')
        self.env = dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / 'config'),
                        XDG_STATE_HOME=str(self.root / 'state'), HYPRLAND_INSTANCE_SIGNATURE='')
        defaults = self.root / 'defaults.lua'
        defaults.write_text('hl.config({decoration={active_opacity=0.85,blur={enabled=false,size=8,passes=1}}})\n')
        entry = (HYPR / 'hyprland.lua').read_text()
        entry = entry.replace('/etc/agentoo/target-host', str(self.selector)).replace(
            '/etc/xdg/hypr/hosts/', str(self.hosts) + '/')
        for name in ('appearance-rules', 'window-classes'):
            entry = entry.replace(f'/etc/xdg/hypr/{name}.lua', str(HYPR / f'{name}.lua'))
        for name in ('agentoo', 'lid', 'effects'):
            entry = entry.replace(f'/etc/xdg/hypr/{name}.lua', str(defaults))
        for name in ('transparency', 'blur'):
            module = self.root / f'{name}.lua'
            source = (HYPR / f'{name}.lua').read_text().replace(
                '/etc/xdg/hypr/appearance.lua', str(appearance_loader(self.root)))
            for dependency in ('appearance-rules', 'window-classes'):
                source = source.replace(f'/etc/xdg/hypr/{dependency}.lua', str(HYPR / f'{dependency}.lua'))
            module.write_text(source)
            entry = entry.replace(f'/etc/xdg/hypr/{name}.lua', str(module))
        self.entry = entry

    def verify(self, data=None, after=''):
        self.state.write_text(json.dumps(data or {}))
        config = self.root / 'hyprland.lua'
        config.write_text(self.entry + '\n' + after)
        result = subprocess.run(['Hyprland', '--verify-config', '--config', str(config)],
                                env=self.env, capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout + result.stderr

    def test_unused_backups_inactive_branches_and_scalar_defaults_do_not_block(self):
        (self.personal / 'backup.lua').write_text('hl.window_rule({opacity="0.1", no_blur=true})\nerror("unused")\n')
        (self.personal / 'backup.conf').write_text('windowrule = opaque, class:.*\n')
        self.local.write_text('if false then hl.window_rule({opacity="0.2",no_blur=true}) end\n'
                              'hl.config({decoration={active_opacity=0.9,blur={size=4}}})\n')
        code, output = self.verify({'transparency': {'all': {'focused': 5}}, 'blur': {'kitty': {'focused': True}}},
                                   'assert(agentoo_window_rule_conflicts("transparency") == "")\n'
                                   'assert(agentoo_window_rule_conflicts("blur") == "")\n')
        self.assertEqual(code, 0, output)

    def test_personal_and_host_includes_outside_the_tree_block_saved_rules(self):
        for feature, effect, value in (('transparency', 'opacity', '"0.8"'), ('blur', 'no_blur', 'false')):
            for entry_file in (self.local, self.host):
                self.local.write_text('')
                self.host.write_text('')
                entry_file.write_text('require(' + json.dumps(str(self.outside)) + ')\n')
                self.outside.write_text('local key = ' + json.dumps(effect) + '\n'
                                        'hl.window_rule({\n  name="external",match={class="example"},\n  [key]=' + value + '\n})\n')
                data = {feature: {'all': {'focused': 5 if feature == 'transparency' else True}}}
                with self.subTest(feature=feature, entry=entry_file):
                    code, output = self.verify(data)
                    self.assertNotEqual(code, 0)
                    self.assertIn(f'Conflicting {feature} window rules', output)
                    self.assertIn(str(self.outside) + ':2', output)
                    self.assertEqual(json.loads(self.state.read_text()), data)
        # Removing the last managed rule leaves authored policy usable again.
        code, output = self.verify()
        self.assertEqual(code, 0, output)

    def test_native_enable_disable_named_merging_and_runtime_declarations(self):
        self.local.write_text('authored = hl.window_rule({name="authored",match={class="example"},opacity="0.8",no_blur=false})\n'
                              'authored:set_enabled(false)\n')
        code, output = self.verify({'transparency': {'all': {'focused': 5}}, 'blur': {'kitty': {'focused': True}}},
            'assert(agentoo_window_rule_conflicts("transparency") == "")\n'
            'authored:set_enabled(true)\n'
            'assert(agentoo_window_rule_conflicts("transparency") ~= "")\n'
            'assert(agentoo_window_rule_conflicts("blur") ~= "")\n'
            'local same = hl.window_rule({name="authored",enabled=false})\n'
            'assert(same == authored)\n'
            'assert(agentoo_window_rule_conflicts("transparency") == "")\n'
            'assert(agentoo_window_rule_conflicts("blur") == "")\n'
            'local thread = coroutine.create(function() return hl.window_rule({name="tailcall",no_blur=true}) end)\n'
            'local ok, rule = coroutine.resume(thread)\n'
            'assert(ok, rule)\n'
            'assert(rule:is_enabled() and agentoo_window_rule_conflicts("blur") ~= "")\n'
            'rule:set_enabled(false)\n'
            'assert(agentoo_window_rule_conflicts("blur") == "")\n'
            'hl.window_rule({name="runtime",match={class="example"},opaque=false})\n'
            'assert(agentoo_window_rule_conflicts("transparency") ~= "")\n'
            'assert(agentoo_window_rule_conflicts("blur") ~= "")\n')
        self.assertEqual(code, 0, output)


if __name__ == '__main__':
    unittest.main()
