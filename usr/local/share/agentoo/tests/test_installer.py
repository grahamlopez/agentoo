"""Check installer policy and argument validation without target mutations."""
import os
from pathlib import Path
import subprocess
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'installer/gentoo-install.sh'


class InstallerTest(unittest.TestCase):
    def run_installer(self, *args, harness=None, **env):
        command = ['bash', str(INSTALLER), *args]
        script = None
        if harness:
            source = INSTALLER.read_text().removesuffix('main "$@"\n')
            script = source + '\n' + harness
            command = ['bash', '-s', '--', *args]
        return subprocess.run(command, input=script, capture_output=True, text=True,
                              env=dict(os.environ, **env))

    def test_argument_free_help(self):
        result = self.run_installer('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--no-install-binpkgs', result.stdout)
        self.assertIn('installation (default)', result.stdout)
        self.assertIn('--disk DEVICE --target-host NAME', result.stdout)

    def test_target_required_even_with_environment_or_dry_run(self):
        for args in [[], ['--dry-run'], ['--target-host='],
                     ['--target-host', 'unknown']]:
            with self.subTest(args=args):
                result = self.run_installer(*args, TARGET_HOST='generic')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('--target-host', result.stderr)
                self.assertNotIn('==>', result.stdout)

    def test_supported_targets_validate(self):
        # Disk validation still fails; no supported target should be rejected.
        for target in ['generic', 'qemu', 'thinktop', 'startop', 'flattop']:
            result = self.run_installer('--target-host', target, '--dry-run',
                                        '--phase', 'handoff')
            self.assertIn('--disk is required', result.stderr)
            self.assertNotIn('--target-host', result.stderr)

    def test_package_policy_survives_child_reentry(self):
        harness = '''
 system_update_chroot() {
   printf 'package:%s\\n' "${PACKAGE_OPTIONS[@]}"
   printf 'child:%s\\n' "${BINARY_INSTALL_OPTIONS[@]}"
 }
 main "$@"
'''
        for flags, binary in [([], True), (['--no-install-binpkgs'], False),
                              (['--no-install-binpkgs', '--install-binpkgs'], True)]:
            with self.subTest(flags=flags):
                result = self.run_installer('--internal-update-chroot',
                    '--target-host', 'generic', '--no-ram-builds', *flags,
                    harness=harness)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('package:--usepkg=' + ('y' if binary else 'n'), result.stdout)
                self.assertIn('package:--getbinpkg=' + ('y' if binary else 'n'), result.stdout)
                option = '--install-binpkgs' if binary else '--no-install-binpkgs'
                self.assertIn('child:' + option, result.stdout)
                child = [line[6:] for line in result.stdout.splitlines()
                         if line.startswith('child:')]
                resumed = self.run_installer('--internal-update-chroot',
                    '--target-host', 'generic', *child, harness=harness)
                self.assertEqual(resumed.stdout, result.stdout)
                if binary:
                    self.assertIn('package:--binpkg-respect-use=y', result.stdout)
                    self.assertIn('package:--binpkg-changed-deps=y', result.stdout)


if __name__ == '__main__':
    unittest.main()
