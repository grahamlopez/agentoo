"""Host consumers share assignment syntax without executing the selector."""
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

VALID = ('GENTOO_TARGET_HOST="test-host_2"\n', '\n\tGENTOO_TARGET_HOST="test-host_2"  \n')
INVALID = ('', 'GENTOO_TARGET_HOST = "test-host_2"', 'GENTOO_TARGET_HOST= "test-host_2"',
           'GENTOO_TARGET_HOST=test-host_2', 'GENTOO_TARGET_HOST="../test"',
           'GENTOO_TARGET_HOST="_test"', 'GENTOO_TARGET_HOST="tést"',
           'GENTOO_TARGET_HOST="test-host_2"\nexit 0\n')


class HostSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.selector = self.root / 'target-host'
        self.hosts = self.root / 'hosts'
        self.hosts.mkdir()
        (self.hosts / 'test-host_2.conf').write_text('font_size 10\n')
        (self.hosts / 'test-host_2.lua').write_text('-- test host\n')

    def test_python_consumers_agree_on_valid_and_malformed_assignments(self):
        with patch.object(kernel_host, 'SELECTOR', self.selector), \
             patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root)):
            for contents in VALID:
                self.selector.write_text(contents)
                with self.subTest(contents=contents):
                    self.assertEqual(read_host(self.selector), 'test-host_2')
                    self.assertEqual(kernel_host.selected_host(), 'test-host_2')
                    self.assertEqual(kitty.host_config(self.selector, self.hosts), 'font_size 10\n')
            for contents in INVALID:
                self.selector.write_text(contents)
                for read in (lambda: read_host(self.selector), kernel_host.selected_host,
                             lambda: kitty.host_config(self.selector, self.hosts)):
                    with self.subTest(contents=contents), self.assertRaises(ValueError):
                        read()

    def test_missing_selector_and_profiles_retain_each_consumers_policy(self):
        with patch.object(kernel_host, 'SELECTOR', self.selector), \
             patch.object(kernel_host, 'HOSTS', self.hosts), \
             patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root)):
            self.assertEqual(kitty.host_config(self.selector, self.hosts), '')
            with self.assertRaises(FileNotFoundError):
                kernel_host.selected_host()
            self.assertEqual(kernel_host.selected_host('test-host_2'), 'test-host_2')
            self.selector.write_text('GENTOO_TARGET_HOST="missing"\n')
            self.assertEqual(kitty.host_config(self.selector, self.hosts), '')
            with self.assertRaisesRegex(RuntimeError, 'no kernel profile'):
                kernel_host.read_profile()

    @unittest.skipUnless(shutil.which('lua'), 'Lua interpreter required')
    def test_native_lua_reader_accepts_the_same_syntax(self):
        source = (ROOT / 'etc/xdg/hypr/hyprland.lua').read_text()
        source = source.replace('/etc/agentoo/target-host', str(self.selector)).replace(
            '/etc/xdg/hypr/hosts/', str(self.hosts) + '/')
        config = self.root / 'hyprland.lua'
        config.write_text(source)
        # Execute the real entry file; intercept external modules so no desktop
        # operations run. Optional host-file lookup and selector parsing stay real.
        harness = self.root / 'load.lua'
        harness.write_text('hl={animation=function() end}; require=function(path) print(path) end; '
                           'dofile(' + json.dumps(str(config)) + ')')
        for contents in (*VALID, *INVALID):
            self.selector.write_text(contents)
            result = subprocess.run(['lua', str(harness)],
                                    env=dict(os.environ, XDG_CONFIG_HOME=str(self.root)),
                                    capture_output=True, text=True, timeout=10)
            with self.subTest(contents=contents):
                self.assertEqual(result.returncode == 0, contents in VALID, result.stderr)
                if contents in VALID:
                    self.assertIn(str(self.hosts / 'test-host_2.lua'), result.stdout)
                else:
                    self.assertIn('expected GENTOO_TARGET_HOST=', result.stderr)


if __name__ == '__main__':
    unittest.main()
