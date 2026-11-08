"""Exercise native profile reporting across Python, Lua and shell consumers."""
import importlib.util
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
LIB = SHARE / 'lib'
ROOT = SHARE.parents[3]
sys.path.insert(0, str(LIB))
import kernel_host
from host_selection import read_host

spec = importlib.util.spec_from_file_location('kitty_host_config', LIB / 'kitty/host_config.py')
kitty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kitty)

VALID = ('agentoo:hosts/test-host_2\n', '  agentoo:hosts/test-host_2  \n')
INVALID = ('', '(unset)\n', 'default/linux/amd64/23.0/desktop/systemd\n',
           'other:hosts/test-host_2\n', 'agentoo:hosts/../test\n',
           'agentoo:hosts/test\nextra\n', 'agentoo:hosts/_test\n')


class HostSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = self.root / 'report'
        self.report.write_text(VALID[0])
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        eselect = self.bin / 'eselect'
        eselect.write_text('#!/bin/sh\n'
            '[ "$*" = "--brief --colour=no profile show" ] || exit 99\n'
            'cat "$PROFILE_REPORT"\nexit "${PROFILE_EXIT:-0}"\n')
        eselect.chmod(0o755)
        env = patch.dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                         PROFILE_REPORT=str(self.report), PROFILE_EXIT='0',
                         XDG_CONFIG_HOME=str(self.root))
        env.start()
        self.addCleanup(env.stop)
        self.hosts = self.root / 'hosts'
        self.hosts.mkdir()
        (self.hosts / 'test-host_2.conf').write_text('font_size 10\n')
        (self.hosts / 'test-host_2.lua').write_text('-- test host\n')

    def test_python_consumers_share_native_reporting_and_reject_non_agentoo_profiles(self):
        for contents in (*VALID, *INVALID):
            self.report.write_text(contents)
            for read in (read_host, kernel_host.selected_host,
                         lambda: kitty.host_config(self.hosts)):
                with self.subTest(contents=contents, consumer=read):
                    if contents in VALID:
                        result = read()
                        self.assertIn(result, ('test-host_2', 'font_size 10\n'))
                    else:
                        with self.assertRaisesRegex(ValueError, 'select an Agentoo host profile'):
                            read()

    def test_failed_eselect_is_not_an_empty_hardware_selection(self):
        with patch.dict(os.environ, PROFILE_EXIT='1'):
            with self.assertRaisesRegex(RuntimeError, 'eselect profile show failed'):
                read_host()
            result = subprocess.run([sys.executable, str(LIB / 'host_selection.py')],
                                    capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('eselect profile show failed', result.stderr)

    def test_missing_fragments_and_explicit_kernel_target(self):
        self.report.write_text('agentoo:hosts/missing\n')
        self.assertEqual(kitty.host_config(self.hosts), '')
        with patch.object(kernel_host, 'HOSTS', self.hosts):
            with self.assertRaisesRegex(RuntimeError, 'no kernel profile'):
                kernel_host.read_profile()
        self.report.write_text('(unset)\n')
        self.assertEqual(kernel_host.selected_host('test-host_2'), 'test-host_2')

    def test_dracut_uses_selected_profile_and_stops_on_query_failure(self):
        source = (ROOT / 'etc/dracut.conf.d/startop.conf').read_text().replace(
            '/usr/local/share/agentoo/lib/host_selection.py', str(LIB / 'host_selection.py'))
        fragment = self.root / 'dracut.conf'
        fragment.write_text(source)
        for profile, drivers, status in (('agentoo:hosts/startop', ' i915 ', 0),
                                          ('agentoo:hosts/flattop', '', 0), ('(unset)', '', 1)):
            self.report.write_text(profile + '\n')
            result = subprocess.run(['bash', '-c', 'source "$1" || exit $?; printf "%s" "${force_drivers:-}"',
                                     'test', str(fragment)], capture_output=True, text=True)
            with self.subTest(profile=profile):
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout, drivers)

    @unittest.skipUnless(shutil.which('lua'), 'Lua interpreter required')
    def test_native_lua_reader_uses_the_same_adapter(self):
        source = (ROOT / 'etc/xdg/hypr/hyprland.lua').read_text().replace(
            '/usr/local/share/agentoo/lib/host_selection.py', str(LIB / 'host_selection.py')).replace(
            '/etc/xdg/hypr/hosts/', str(self.hosts) + '/')
        config = self.root / 'hyprland.lua'
        config.write_text(source)
        harness = self.root / 'load.lua'
        harness.write_text('hl={animation=function() end}; require=function(path) print(path) end; '
                           'dofile(' + json.dumps(str(config)) + ')')
        for contents in (*VALID, *INVALID):
            self.report.write_text(contents)
            result = subprocess.run(['lua', str(harness)], capture_output=True, text=True, timeout=10)
            with self.subTest(contents=contents):
                self.assertEqual(result.returncode == 0, contents in VALID, result.stderr)
                if contents in VALID:
                    self.assertIn(str(self.hosts / 'test-host_2.lua'), result.stdout)
                else:
                    self.assertIn('could not determine the selected Agentoo host profile', result.stderr)


if __name__ == '__main__':
    unittest.main()
