"""Mode preference CLI behavior and isolated native GSettings persistence."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-theme'


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.call = self.root / 'call'
        self.settings = self.root / 'gsettings'
        self.settings.write_text('#!/bin/sh\n'
            'printf "%s\\n" "$@" > "$THEME_CALL"\n'
            'printf "%s" "$THEME_REPLY"\n'
            'printf "%s" "$THEME_ERROR" >&2\n'
            'exit "${THEME_EXIT:-0}"\n')
        self.settings.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:{os.environ["PATH"]}',
                        THEME_CALL=str(self.call), THEME_REPLY="'default'\n",
                        THEME_ERROR='', THEME_EXIT='0')

    def run_theme(self, *args, env=None):
        return subprocess.run([str(ENTRY), *args], env=self.env if env is None else env,
                              text=True, capture_output=True)

    def test_query_reports_preference_including_unset(self):
        for native, expected in [('default', 'no-preference'), ('prefer-light', 'light'),
                                 ('prefer-dark', 'dark')]:
            with self.subTest(native=native):
                self.env['THEME_REPLY'] = f"'{native}'\n"
                result = self.run_theme()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected + '\n')
                self.assertEqual(result.stderr, '')
                self.assertEqual(self.call.read_text().splitlines(),
                    ['get', 'org.gnome.desktop.interface', 'color-scheme'])

    def test_set_changes_only_mode_preference(self):
        for mode in ('light', 'dark'):
            with self.subTest(mode=mode):
                result = self.run_theme(mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertIn(mode, result.stderr)
                self.assertEqual(self.call.read_text().splitlines(),
                    ['set', 'org.gnome.desktop.interface', 'color-scheme', 'prefer-' + mode])

    def test_help_and_invalid_arguments_do_not_access_settings(self):
        for args, code in [(('--help',), 0), (('dark', '--help'), 0),
                           (('toggle',), 2), (('light', 'dark'), 2)]:
            with self.subTest(args=args):
                result = self.run_theme(*args)
                self.assertEqual(result.returncode, code)
                self.assertFalse(self.call.exists())

    def test_settings_failures_including_zero_exit_dconf_warning(self):
        for exit_code, message in [('1', 'No such schema'),
                                   ('0', 'dconf-WARNING: failed to commit changes')]:
            with self.subTest(exit_code=exit_code):
                self.env.update(THEME_EXIT=exit_code, THEME_ERROR=message)
                result = self.run_theme('light')
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertIn(message, result.stderr)

    def test_missing_gsettings_and_unexpected_value(self):
        self.env['THEME_REPLY'] = "'unknown'\n"
        result = self.run_theme()
        self.assertEqual(result.returncode, 1)
        self.assertIn('unexpected color-scheme', result.stderr)
        self.settings.unlink()
        self.env['PATH'] = str(self.root)
        result = subprocess.run([shutil.which('python3'), str(ENTRY)], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('gsettings', result.stderr)

    @unittest.skipUnless(shutil.which('gsettings') and shutil.which('glib-compile-schemas'),
                         'native GLib tools are required')
    def test_native_persistence_between_processes(self):
        # Exercise real GSettings without a session bus or the user's settings.
        schemas = self.root / 'schemas'
        schemas.mkdir()
        (schemas / 'interface.gschema.xml').write_text('''<schemalist>
          <enum id="org.gnome.desktop.GDesktopColorScheme">
            <value nick="default" value="0"/>
            <value nick="prefer-dark" value="1"/>
            <value nick="prefer-light" value="2"/>
          </enum>
          <schema id="org.gnome.desktop.interface" path="/org/gnome/desktop/interface/">
            <key name="color-scheme" enum="org.gnome.desktop.GDesktopColorScheme">
              <default>'default'</default>
            </key>
          </schema>
        </schemalist>''')
        subprocess.run(['glib-compile-schemas', '--strict', str(schemas)], check=True,
                       capture_output=True)
        env = dict(os.environ, GSETTINGS_SCHEMA_DIR=str(schemas), GSETTINGS_BACKEND='keyfile',
                   XDG_CONFIG_HOME=str(self.root / 'config'), HOME=str(self.root))
        initial = self.run_theme(env=env)
        self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertEqual(initial.stdout, 'no-preference\n')
        for mode in ('dark', 'light', 'light'):
            with self.subTest(mode=mode):
                change = self.run_theme(mode, env=env)
                self.assertEqual(change.returncode, 0, change.stderr)
                query = self.run_theme(env=env)
                self.assertEqual(query.returncode, 0, query.stderr)
                self.assertEqual(query.stdout, mode + '\n')


if __name__ == '__main__':
    unittest.main()
