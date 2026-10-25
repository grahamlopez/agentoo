"""Exercise setup helpers with temporary files and stubbed host commands."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
SETUP = (ROOT / 'root/002-agentoo-setup-user.sh').read_text()
VERIFY = (ROOT / 'root/001-firstboot-verify-and-checkpoint.sh').read_text()
AUTOLOGIN = SETUP[SETUP.index('configure_autologin() ('):SETUP.index('validate_identity() {')]
WIFI = VERIFY[VERIFY.index('report_wifi_configuration() {'):VERIFY.index('run_diagnostics() {')]


class FirstbootSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def shell(self, code, *args):
        return subprocess.run(['bash', '-s', '--', *map(str, args)],
                              input='set -euo pipefail\ndie() { echo "$*" >&2; exit 1; }\n' + code,
                              capture_output=True, text=True)

    def autologin(self, account=True):
        return self.shell(AUTOLOGIN + '\ngetent() { return ' + ('0' if account else '1') + '; }\n'
                          'configure_autologin "$1"\n', self.root / 'getty')

    def test_account_required_before_any_autologin_file(self):
        result = self.autologin(account=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'getty').exists())

    def test_autologin_is_native_and_repeatable(self):
        for _ in range(2):
            result = self.autologin()
            self.assertEqual(result.returncode, 0, result.stderr)
        config = self.root / 'getty/autologin.conf'
        self.assertIn('/usr/bin/agetty --autologin graham', config.read_text())
        self.assertIn('${TERM}', config.read_text())
        self.assertEqual(config.stat().st_mode & 0o777, 0o644)
        self.assertEqual(list(config.parent.iterdir()), [config])

    def test_conflicting_or_symlinked_dropin_is_preserved(self):
        directory = self.root / 'getty'
        directory.mkdir()
        target = self.root / 'custom'
        target.write_text('custom configuration\n')
        config = directory / 'autologin.conf'
        for symlink in [False, True]:
            with self.subTest(symlink=symlink):
                if symlink:
                    config.symlink_to(target)
                else:
                    config.write_text(target.read_text())
                result = self.autologin()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(config.read_text(), 'custom configuration\n')
                self.assertEqual(config.is_symlink(), symlink)
                self.assertEqual(list(directory.iterdir()), [config])
                config.unlink()

    def wifi(self, state, present=True):
        configs = self.root / 'configs'
        configs.mkdir()
        (configs / 'wpa_supplicant-wlan0.conf').write_text('private credentials\n')
        net = self.root / 'net'
        net.mkdir()
        if present:
            (net / 'wlan0/phy80211').mkdir(parents=True)
        # The stub returns the selected state, independent of command arguments.
        code = WIFI + '\nwpa_cli() { printf "wpa_state=' + state + '\\n"; }\nreport_wifi_configuration "$1" "$2"\n'
        result = self.shell(code, configs, net)
        self.assertEqual((configs / 'wpa_supplicant-wlan0.conf').read_text(), 'private credentials\n')
        self.assertNotIn('private credentials', result.stdout)
        return result

    def test_missing_interface_has_manual_recovery_guidance(self):
        result = self.wifi('DISCONNECTED', present=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('absent wireless interface: wlan0', result.stdout)
        self.assertIn('NEW_INTERFACE', result.stdout)
        self.assertIn('systemctl disable --now', result.stdout)

    def test_authentication_failure_reports_without_blocking(self):
        result = self.wifi('DISCONNECTED')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DISCONNECTED', result.stdout)
        self.assertIn('journalctl -b -u', result.stdout)
        self.assertIn('wpa_cli -i wlan0 status', result.stdout)

    def test_completed_authentication_needs_no_recovery(self):
        result = self.wifi('COMPLETED')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('COMPLETED', result.stdout)
        self.assertNotIn('journalctl -b -u', result.stdout)


if __name__ == '__main__':
    unittest.main()
