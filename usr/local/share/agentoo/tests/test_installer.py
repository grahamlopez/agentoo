"""Check installer policy and argument validation without target mutations."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'installer/gentoo-install.sh'


class InstallerTest(unittest.TestCase):
    def test_public_download_modes_do_not_depend_on_host_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'download'
            for downloader in ['curl', 'wget']:
                with self.subTest(downloader=downloader):
                    result = self.run_installer(str(destination), downloader, harness='''
umask 077
downloader=$2
command() {
  if [[ $1 == -v && $2 == curl && $downloader == wget ]]; then return 1; fi
  builtin command "$@"
}
run_privileged() { "$@"; }
curl() { printf 'public archive\\n' >"$7"; }
wget() { printf 'public archive\\n' >"${3#--output-document=}"; }
download_file https://example.invalid/archive "$1"
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(destination.read_text(), 'public archive\n')
                    self.assertEqual(destination.stat().st_mode & 0o777, 0o644)
                    destination.unlink()

    def test_internal_phases_reset_inherited_private_umask(self):
        for phase, function in [('portage', 'portage_foundation_chroot'),
                                ('update', 'system_update_chroot'),
                                ('kernel', 'kernel_foundation_chroot'),
                                ('firstboot-offline', 'firstboot_offline')]:
            with tempfile.TemporaryDirectory() as directory, self.subTest(phase=phase):
                flag = ('--internal-firstboot-offline' if phase == 'firstboot-offline'
                        else f'--internal-{phase}-chroot')
                result = self.run_installer(flag, '--disk', '/dev/null', '--target-host', 'generic',
                    '--no-ram-builds', harness=f'''
umask 077
{function}() {{
  kernel_target_data "$CHECK_DIRECTORY/boot-data" 'public boot data'
  mktemp "$CHECK_DIRECTORY/private.XXXXXX"
}}
main "$@"
''', CHECK_DIRECTORY=directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                public = Path(directory) / 'boot-data'
                private = next(Path(directory).glob('private.*'))
                self.assertEqual(public.stat().st_mode & 0o777, 0o644)
                self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_verified_release_manifest_is_readable_after_pinned_signature_check(self):
        with tempfile.TemporaryDirectory() as directory:
            verified = Path(directory) / 'manifest.verified'
            for fingerprint, success in [('WRONG', False),
                                         ('PINNED', True)]:
                with self.subTest(fingerprint=fingerprint):
                    result = self.run_installer(str(verified), fingerprint, harness='''
STAGE_GPG_HOME=unused
run_privileged() { "$@"; }
gpg() {
  local output
  while (($#)); do
    if [[ $1 == --output ]]; then output=$2; shift; fi
    shift
  done
  printf 'authenticated manifest\\n' >"$output"
  chmod 600 "$output"
  printf '[GNUPG:] VALIDSIG subkey date timestamp expiry version reserved algorithm hash class %s\\n' "$signer"
}
signer=$2
[[ $signer != PINNED ]] || signer=$GENTOO_AUTOMATED_RELEASE_FINGERPRINT
verify_pinned_release_signature unused "$1"
''')
                    self.assertEqual(result.returncode == 0, success, result.stderr)
                    self.assertEqual(verified.stat().st_mode & 0o777,
                                     0o644 if success else 0o600)
                    self.assertEqual(verified.read_text(), 'authenticated manifest\n')

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
        for target in ['generic', 'qemu', 'thinktop', 'startop', 'flattop', 'bequiet']:
            result = self.run_installer('--target-host', target, '--dry-run',
                                        '--phase', 'handoff')
            self.assertIn('--disk is required', result.stderr)
            self.assertNotIn('--target-host', result.stderr)

    def test_nvidia_is_deferred_until_kernel_boot_inputs_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atom = 'sys-kernel/gentoo-kernel-bin-6.18.60'
            for name in ['etc/kernel', 'etc/portage/package.use', 'etc/dracut.conf.d',
                         'etc/kernel/install.d', 'var/lib/agentoo/repository.git',
                         f'var/db/pkg/{atom}', 'boot']:
                (root / name).mkdir(parents=True, exist_ok=True)
            for name in ['etc/gentoo-release', 'etc/portage/package.use/kernel',
                         'etc/kernel/install.conf', 'etc/dracut.conf.d/agentoo-dist.conf',
                         'etc/kernel/install.d/04-agentoo-esp.install']:
                (root / name).touch()
            release = root / 'include/config/kernel.release'
            release.parent.mkdir(parents=True)
            release.write_text('6.18.60-gentoo-dist-bin\n')
            (root / f'var/db/pkg/{atom}/CONTENTS').write_text(f'obj {release} hash 0\n')
            # Run both phase bodies against a disposable target, including as non-root.
            source = INSTALLER.read_text().removesuffix('main "$@"\n')
            source = source.replace('(( EUID == 0 )) || die', 'true || die')
            for prefix in ['/etc/', '/var/', '/boot']:
                source = source.replace(prefix, directory + prefix)
            harness = r'''
TARGET_HOST=bequiet
TARGET_MICROCODE=amd
TARGET_CPU_FLAGS='aes sse2'
PACKAGE_OPTIONS=()
require_command() { :; }
selected_target_host() { echo bequiet; }
prepare_install_binpkgs() { :; }
emaint() { :; }
eselect() { :; }
git() { :; }
agentoo() { :; }
pending_config_updates() { :; }
confirm_phase() { :; }
mountpoint() { :; }
findmnt() { if [[ $* == *UUID* ]]; then echo abcd-1234; else echo vfat; fi; }
resolve_target_partitions() { CRYPT_PARTITION=/dev/test; }
blkid() { echo abcd-1234; }
cryptsetup() { echo abcd-1234; }
portageq() {
  case $1 in
    envvar) echo '-O2 -pipe' ;;
    best_version) echo sys-kernel/gentoo-kernel-bin-6.18.60 ;;
  esac
}
install_emerge() {
  local arguments
  printf -v arguments '%s ' "$@"
  if [[ " $arguments" == *' @profile '* ]]; then
    [[ -s $CHECK_ROOT/etc/kernel/cmdline && -s $CHECK_ROOT/etc/kernel/gentoo-dist-esp.uuid ]] || exit 90
  fi
  printf '%s ' "$@" >>"$CHECK_ROOT/transactions"
  printf '\n' >>"$CHECK_ROOT/transactions"
}
verify_distribution_kernel() { echo "$1" >"$CHECK_ROOT/verified"; }
print_physical_kernel_boot_commands() { :; }
system_update_chroot
kernel_foundation_chroot
'''
            result = subprocess.run(['bash', '-s'], input=source + harness,
                                    capture_output=True, text=True,
                                    env=dict(os.environ, CHECK_ROOT=directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            transactions = (root / 'transactions').read_text().splitlines()
            world = [line for line in transactions if '@world' in line]
            kernel = [line for line in transactions if '@profile' in line]
            self.assertEqual(len(world), 2)
            self.assertEqual(len(kernel), 2)
            for line in world:
                self.assertIn('--exclude x11-drivers/nvidia-drivers', line)
            for line in kernel:
                self.assertIn('sys-kernel/gentoo-kernel-bin', line)
                self.assertNotIn('--exclude', line)
            self.assertLess(transactions.index(world[-1]), transactions.index(kernel[0]))
            self.assertEqual((root / 'verified').read_text(), '6.18.60-gentoo-dist-bin\n')

    def test_profile_query_runs_inside_the_requested_destination(self):
        result = self.run_installer('/mnt/target', harness='''
chroot() { printf '%s\\n' "$@"; }
selected_target_host "$1"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['/mnt/target', '/usr/bin/python3',
            '/usr/local/share/agentoo/lib/host_selection.py'])

    def test_native_profile_selection_preserves_wrong_target_guard(self):
        for current, status in [('default/linux/amd64/23.0/desktop/systemd', 0),
                                ('agentoo:hosts/thinktop', 0), ('agentoo:hosts/flattop', 1)]:
            with self.subTest(current=current):
                result = self.run_installer(current, harness='''
TARGET_HOST=thinktop
current=$1
run_privileged() { "$@"; }
chroot() { shift 2; eselect "$@"; }
eselect() {
  case "$1" in
    --brief) printf '  %s\\n' "$current" ;;
    profile) echo selected ;;
    *) return 99 ;;
  esac
}
selected_target_host() { echo thinktop; }
select_target_profile
''')
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual('selected' in result.stdout, status == 0)

    def test_profile_reporting_failure_stops_before_selection(self):
        result = self.run_installer(harness='''
TARGET_HOST=thinktop
run_privileged() { "$@"; }
chroot() { return 1; }
select_target_profile
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot report', result.stderr)

    def test_signed_binhost_uses_native_compatibility_not_profile_path(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'etc/portage/binrepos.conf/gentoo.conf'
            config.parent.mkdir(parents=True)
            for profile, signed, status in [('thinktop', True, 0), ('flattop', True, 1),
                                              ('thinktop', False, 1)]:
                config.write_text('[gentoo]\n'
                    'sync-uri = https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64\n'
                    f'verify-signature = {str(signed).lower()}\nlocation = /var/cache/binhost/gentoo\n')
                with self.subTest(profile=profile, signed=signed):
                    result = self.run_installer(directory, profile, harness='''
TARGET_HOST=thinktop
profile=$2
selected_target_host() { printf '%s\\n' "$profile"; }
chroot() {
  local root=$1
  shift
  case $1 in
    /usr/bin/python3) python3 - "$root$3" ;;
    /usr/bin/getuto) echo trust-initialized ;;
    *) return 99 ;;
  esac
}
prepare_install_binpkgs "$1"
''')
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual('trust-initialized' in result.stdout, status == 0)

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
