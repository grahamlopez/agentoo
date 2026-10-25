"""Check installer policy and argument validation without target mutations."""
import os
from pathlib import Path
import subprocess
import tempfile
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

    def test_offline_masks_use_target_tools_without_host_systemctl(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'etc/agentoo/masked-units.conf'
            policy.parent.mkdir(parents=True)
            policy.write_text('# Offline target policy\nexample.service\nexample.socket\n')
            result = self.run_installer(directory, harness='''
MOUNT_ROOT=$1
systemctl() { echo 'host systemctl must not run' >&2; return 99; }
run_privileged() { "$@"; }
chroot() { printf '%s\\n' "$*"; }
apply_optional_systemd_policy
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            # Global IFS joins the captured argv with newlines.
            self.assertEqual(result.stdout.splitlines(), [
                value for unit in ['example.service', 'example.socket']
                for value in [directory, '/usr/bin/systemctl', '--root=/', 'mask', unit]])

    def test_cpu_detection_accepts_both_output_formats(self):
        for output in ['CPU_FLAGS_X86: aes avx2 sse2',
                       '*/* CPU_FLAGS_X86: aes avx2 sse2']:
            with self.subTest(output=output):
                result = self.run_installer(output, harness='''
detected=$1
cpuid2cpuflags() { printf '%s\\n' "$detected"; }
resolve_cpu_flags
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'aes avx2 sse2\n')

    def test_cpu_detection_rejects_wrong_architecture_and_malformed_flags(self):
        for output in ['CPU_FLAGS_ARM: neon', '*/* CPU_FLAGS_X86: ',
                       '*/* CPU_FLAGS_X86: sse2; echo bad',
                       'CPU_FLAGS_X86: sse2\nextra output']:
            with self.subTest(output=output):
                result = self.run_installer(output, harness='''
detected=$1
cpuid2cpuflags() { printf '%s\\n' "$detected"; }
resolve_cpu_flags
''')
                self.assertNotEqual(result.returncode, 0)

    def test_explicit_cpu_flags_skip_detection(self):
        result = self.run_installer(harness='''
TARGET_CPU_FLAGS='aes sse2'
cpuid2cpuflags() { echo 'must not detect' >&2; return 99; }
resolve_cpu_flags
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'aes sse2\n')

    def test_cpu_detection_command_failure_is_reported(self):
        result = self.run_installer(harness='''
cpuid2cpuflags() { return 1; }
resolve_cpu_flags
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CPU detection failed', result.stderr)

    def test_ram_build_noexec_is_cleared_only_on_target_mount(self):
        result = self.run_installer(harness='''
findmnt() {
  [[ ${*: -1} == /mnt/gentoo/dev/shm ]] || return 99
  case $3 in
    FSTYPE) echo tmpfs ;;
    OPTIONS) echo rw,nosuid,nodev,noexec,relatime ;;
  esac
}
run_privileged() { printf 'operation:%s\\n' "$@"; }
prepare_target_ram_builds /mnt/gentoo
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        operations = [line for line in result.stdout.splitlines()
                      if line.startswith('operation:')]
        self.assertEqual(operations, ['operation:mount', 'operation:-o',
            'operation:remount,bind,exec,nosuid,nodev', 'operation:/mnt/gentoo/dev/shm'])

    def test_ram_build_preparation_skips_executable_mount_and_disabled_modes(self):
        for mode, ram in [('apply', 1), ('apply', 0), ('dry-run', 1)]:
            with self.subTest(mode=mode, ram=ram):
                result = self.run_installer(mode, str(ram), harness='''
MODE=$1 RAM_BUILDS=$2
findmnt() {
  (( RAM_BUILDS )) && [[ $MODE == apply ]] || return 99
  case $3 in FSTYPE) echo tmpfs ;; OPTIONS) echo rw,nosuid,nodev ;; esac
}
run_privileged() { echo 'unexpected remount' >&2; return 99; }
prepare_target_ram_builds /mnt/gentoo
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_target_emerge_prepares_ram_storage_before_package_operation(self):
        result = self.run_installer(harness='''
prepare_target_ram_builds() { printf 'prepare:%s\\n' "$1"; }
chroot() { printf 'chroot:%s\\n' "$@"; }
target_emerge /mnt/gentoo --pretend example/package
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'prepare:/mnt/gentoo', 'chroot:/mnt/gentoo', 'chroot:/usr/bin/env',
            'chroot:PORTAGE_TMPDIR=/dev/shm', 'chroot:/usr/bin/emerge',
            'chroot:--pretend', 'chroot:example/package'])

    def test_identity_initialization_uses_chroot_supported_commands(self):
        result = self.run_installer(harness='''
chroot() { printf 'argument:%s\\n' "$@"; }
initialize_target_identity /mnt/gentoo flattop
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'argument:/mnt/gentoo', 'argument:/usr/bin/systemd-firstboot',
            'argument:--hostname=flattop', 'argument:/mnt/gentoo',
            'argument:/usr/bin/systemd-machine-id-setup'])

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
