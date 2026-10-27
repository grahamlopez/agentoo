"""Exercise the kernel handoff with disposable sources and fake build tools.

No kernel compilation, system module installation, ESP or firmware writes occur.
"""
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-kernel'
spec = importlib.util.spec_from_loader('kernel', SourceFileLoader('kernel', str(ENTRY)))
kernel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kernel)
TEST_ROOT_UUID = '11111111-1111-4111-8111-111111111111'
TEST_LUKS_UUID = '22222222-2222-4222-8222-222222222222'
TEST_PARTUUID = '33333333-3333-4333-8333-333333333333'
TEST_CMDLINE = f'root=UUID={TEST_ROOT_UUID} rootfstype=btrfs rootflags=subvol=@ crypt_root=UUID={TEST_LUKS_UUID} rd.luks.uuid=luks-{TEST_LUKS_UUID} rd.luks.name={TEST_LUKS_UUID}=cryptroot ro'


class KernelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = self.root / 'sources'
        (self.sources / 'scripts').mkdir(parents=True)
        (self.sources / 'Makefile').write_text('VERSION = 6\nPATCHLEVEL = 18\nSUBLEVEL = 57\nEXTRAVERSION = -gentoo\nNAME = Test\n')
        self.start = self.root / 'starting.config'
        stale_cmdline = TEST_CMDLINE.replace(TEST_ROOT_UUID, TEST_PARTUUID).replace(TEST_LUKS_UUID, TEST_PARTUUID)
        self.start.write_text('CONFIG_LOCALVERSION="-old"\nCONFIG_CMDLINE=' + json.dumps(stale_cmdline) +
                             '\n# CONFIG_MODULES is not set\nCONFIG_INITRAMFS_SOURCE="/missing/old-build.cpio"\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.tool('make', '''
import json, os, pathlib, re, sys
a = sys.argv[1:]
with open(os.environ['KERNEL_TEST_LOG'], 'a') as f: f.write(json.dumps(['make', *a]) + '\\n')
out = pathlib.Path(next(x[2:] for x in a if x.startswith('O=')))
config = (out / '.config').read_text()
label = re.search(r'^CONFIG_LOCALVERSION="(.*)"$', config, re.M)[1]
release = '6.18.57' + label
if 'kernelrelease' in a: print(release)
elif 'modules_install' in a:
    prefix = pathlib.Path(next(x.split('=', 1)[1] for x in a if x.startswith('INSTALL_MOD_PATH=')))
    modules = prefix / 'lib/modules' / release
    modules.mkdir(parents=True, exist_ok=True)
    (modules / 'modules.builtin').write_text('built-in metadata')
    (modules / 'modules.builtin.modinfo').write_text('built-in modinfo')
    # Real modules_install preserves private modes of generated metadata.
    (modules / 'modules.builtin').chmod(0o600)
    (modules / 'modules.builtin.modinfo').chmod(0o600)
    (modules / 'build').symlink_to(out)
    (modules / 'source').symlink_to(pathlib.Path(a[a.index('-C') + 1]))
    if 'CONFIG_MODULES=y' in config:
        (modules / 'modules.order').write_text('kernel/drivers/example.ko')
        (modules / 'kernel/drivers').mkdir(parents=True)
        (modules / 'kernel/drivers/example.ko').write_text('compiled module')
elif any(x.startswith('-j') for x in a):
    (out / 'arch/x86/boot').mkdir(parents=True, exist_ok=True)
    (out / 'arch/x86/boot/bzImage').write_text(config)
    (out / 'include/config').mkdir(parents=True, exist_ok=True)
    (out / 'include/config/kernel.release').write_text(release + '\\n')
''')
        self.tool('genkernel', '''
import json, os, pathlib, sys
a = sys.argv[1:]
with open(os.environ['KERNEL_TEST_LOG'], 'a') as f: f.write(json.dumps(['genkernel', *a]) + '\\n')
out = pathlib.Path(next(x.split('=', 1)[1] for x in a if x.startswith('--bootdir=')))
name = next(x.split('=', 1)[1] for x in a if x.startswith('--initramfs-filename='))
(out / name).write_text('fresh archive')
''')
        self.tool('sudo', '''
import json, os, sys
a = sys.argv[1:]
with open(os.environ['KERNEL_TEST_LOG'], 'a') as f: f.write(json.dumps(['sudo', *a]) + '\\n')
if a == ['-n', '-v']: sys.exit(0)
if a[0] == '-n': a = a[1:]
if a[0] == '--': a = a[1:]
os.execvp(a[0], a)
''')
        self.tool('depmod', '''
import json, os, pathlib, sys
with open(os.environ['KERNEL_TEST_LOG'], 'a') as f: f.write(json.dumps(['depmod', *sys.argv[1:]]) + '\\n')
if os.environ.get('FAIL_DEPMOD'): sys.exit(1)
(pathlib.Path(os.environ['TEST_MODULES_ROOT']) / sys.argv[-1] / 'modules.builtin.bin').write_text('index')
''')
        modules_root = patch.object(kernel, 'MODULES_ROOT', self.root / 'system-modules')
        modules_root.start()
        self.addCleanup(modules_root.stop)
        self.tool('minimal-initramfs', '''
import json, os, pathlib, sys
with open(os.environ['KERNEL_TEST_LOG'], 'a') as f: f.write(json.dumps(['minimal-initramfs', *sys.argv[1:]]) + '\\n')
work = pathlib.Path(sys.argv[sys.argv.index('--work') + 1])
work.mkdir(parents=True, exist_ok=False)
(work / 'initramfs.cpio').write_text('fresh minimal archive')
''')
        builder = patch.object(kernel, 'INITRAMFS_BUILDER', self.bin / 'minimal-initramfs')
        builder.start()
        self.addCleanup(builder.stop)
        config_tool = self.sources / 'scripts/config'
        config_tool.write_text('''#!/usr/bin/env python3
import pathlib, re, sys
a = sys.argv[1:]
p = pathlib.Path(a[1]); text = p.read_text(); a = a[2:]
while a:
    op, name = a[:2]; a = a[2:]; key = 'CONFIG_' + name
    text = re.sub(r'^(?:' + key + r'=.*|# ' + key + r' is not set)\\n?', '', text, flags=re.M)
    if op == '--set-str': value = '"' + a.pop(0) + '"'
    else: value = 'y' if op == '--enable' else 'n'
    text += key + '=' + value + '\\n'
p.write_text(text)
''')
        config_tool.chmod(0o755)
        self.env = patch.dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', KERNEL_TEST_LOG=str(self.log),
                              TEST_MODULES_ROOT=str(kernel.MODULES_ROOT))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.workspaces = patch.object(kernel, 'WORKSPACES', self.root)
        self.workspaces.start()
        self.addCleanup(self.workspaces.stop)
        self.work = self.root / '6.18.57-test'
        hosts = self.root / 'hosts'
        hosts.mkdir()
        (hosts / 'testhost.config').write_text('CONFIG_EXTRA_FIRMWARE=""\nCONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"\n')
        selector = self.root / 'target-host'
        selector.write_text('GENTOO_TARGET_HOST="testhost"\n')
        cmdline = self.root / 'cmdline'
        cmdline.write_text(TEST_CMDLINE + '\n')
        sysblock = self.root / 'sysblock'
        dm = sysblock / 'dm-0/dm'
        dm.mkdir(parents=True)
        (dm / 'name').write_text('cryptroot\n')
        (dm / 'uuid').write_text('CRYPT-LUKS2-test\n')
        for name, value in dict(HOSTS=hosts, SELECTOR=selector, CMDLINE=cmdline, SYS_BLOCK=sysblock).items():
            change = patch.object(kernel.kernel_host, name, value)
            change.start()
            self.addCleanup(change.stop)
        self.tool('findmnt', f'print({json.dumps({"filesystems": [{"source": "/dev/mapper/cryptroot[/@]", "fstype": "btrfs", "fsroot": "/@"}]})!r})')
        self.tool('lsblk', f'print({json.dumps({"blockdevices": [{"path": "/dev/mapper/cryptroot", "kname": "/dev/dm-0", "type": "crypt", "fstype": "btrfs", "uuid": TEST_ROOT_UUID, "children": [{"type": "part", "fstype": "crypto_LUKS", "uuid": TEST_LUKS_UUID, "partuuid": TEST_PARTUUID}]}]})!r})')

    def tool(self, name, text):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\n' + text)
        path.chmod(0o755)

    def invoke(self, *arguments):
        stdout = io.StringIO()
        with tempfile.TemporaryFile(mode='w+') as stderr:
            with patch.object(kernel.sys, 'argv', [str(ENTRY), *arguments]), redirect_stdout(stdout), redirect_stderr(stderr):
                result = kernel.main()
            stderr.seek(0)
            errors = stderr.read()
        self.assertEqual(result, 0, errors)
        return stdout.getvalue(), errors

    def prepare(self):
        self.invoke('config', '--label', 'test', '--config', str(self.start), '--sources', str(self.sources), '--accept-defaults', '--yes')

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_sudo_waits_for_readiness_before_authenticating(self):
        tty_in, tty_out = io.StringIO('\n'), io.StringIO()

        def call(command, **kwargs):
            if command == ['sudo', '-n', '-v']:
                return SimpleNamespace(returncode=1)
            self.assertEqual(command, ['sudo', '-v'])
            self.assertEqual(tty_in.tell(), 1)
            self.assertIn('Press Enter when ready', tty_out.getvalue())
            return SimpleNamespace(returncode=0)

        with patch('builtins.open', side_effect=[tty_in, tty_out]), \
                patch.object(kernel.subprocess, 'run', side_effect=call):
            kernel.authorize_sudo()

    def test_cached_sudo_runs_privileged_command_without_prompting(self):
        with patch.object(kernel.os, 'geteuid', return_value=1000), \
                patch('builtins.open', side_effect=AssertionError('unexpected readiness prompt')), \
                patch.object(kernel.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='ok')) as run:
            self.assertEqual(kernel.run(['example'], capture=True, root=True), 'ok')
        self.assertEqual(run.call_args_list[-1].args[0], ['sudo', '-n', '--', 'example'])

    def test_config_handoff_specializes_cmdline_and_rejects_reconfiguration(self):
        self.prepare()
        data = kernel.load(self.work, 'test')
        output, _ = kernel.paths(self.work, data)
        values = kernel.read_config(output / '.config')
        self.assertEqual(values['CONFIG_CMDLINE'], json.dumps(TEST_CMDLINE))
        self.assertEqual(values['CONFIG_INITRAMFS_SOURCE'], json.dumps(str(self.work / 'empty-initramfs')))
        self.assertEqual(list((self.work / 'empty-initramfs').iterdir()), [])
        self.assertEqual(data['identity']['partuuid'], TEST_PARTUUID)
        self.assertEqual(data['host'], 'testhost')
        self.assertEqual(values['CONFIG_LOCALVERSION'], '"-test"')
        self.assertEqual(values['CONFIG_IKCONFIG_PROC'], 'y')
        self.assertEqual(kernel.version(self.sources), ('6.18.57', ''))
        self.assertTrue(list(self.sources.glob('Makefile.agentoo-*.bak')))
        with self.assertRaisesRegex(RuntimeError, 'empty or absent'):
            kernel.configure(kernel.build_parser().parse_args(['config', '--label', 'test', '--config', str(self.start), '--sources', str(self.sources), '--accept-defaults', '--yes']))

    def test_diff_long_values_use_separate_lines_and_other_changes_remain_visible(self):
        before = {'CONFIG_CMDLINE': '"root=old ro"', 'CONFIG_EXTRA_FIRMWARE': '"old.bin common.bin"',
                  'CONFIG_MODULES': 'n', 'CONFIG_REMOVED': 'n'}
        after = {'CONFIG_CMDLINE': '"root=new ro"', 'CONFIG_EXTRA_FIRMWARE': '"new.bin common.bin"',
                 'CONFIG_MODULES': 'y'}
        errors = io.StringIO()
        with redirect_stderr(errors):
            kernel.show_diff(before, after)
        self.assertIn('CONFIG_CMDLINE:\n    before: "root=old ro"\n    after:  "root=new ro"', errors.getvalue())
        self.assertIn('CONFIG_EXTRA_FIRMWARE:\n    before: "old.bin common.bin"\n    after:  "new.bin common.bin"', errors.getvalue())
        self.assertIn('CONFIG_MODULES: n -> y', errors.getvalue())
        self.assertIn('CONFIG_REMOVED: n -> <absent>', errors.getvalue())

    def test_build_keeps_initramfs_policy_during_both_resolution_passes(self):
        with self.start.open('a') as stream:
            stream.write('CONFIG_INITRAMFS_COMPRESSION_NONE=y\nCONFIG_INITRAMFS_ROOT_UID=0\n'
                         'CONFIG_INITRAMFS_ROOT_GID=0\n# CONFIG_ACPI_TABLE_OVERRIDE_VIA_BUILTIN_INITRD is not set\n')
        original_make = kernel.make
        resolutions = []
        def resolving_make(work, data, *arguments, **kwargs):
            result = original_make(work, data, *arguments, **kwargs)
            if 'olddefconfig' in arguments:
                output, _ = kernel.paths(work, data)
                values = kernel.read_config(output / '.config')
                self.assertNotEqual(values['CONFIG_INITRAMFS_SOURCE'], '""')
                self.assertEqual(values['CONFIG_INITRAMFS_COMPRESSION_NONE'], 'y')
                self.assertEqual(values['CONFIG_INITRAMFS_ROOT_UID'], '0')
                self.assertEqual(values['CONFIG_INITRAMFS_ROOT_GID'], '0')
                self.assertEqual(values['CONFIG_ACPI_TABLE_OVERRIDE_VIA_BUILTIN_INITRD'], 'n')
                resolutions.append(values['CONFIG_INITRAMFS_SOURCE'])
            return result
        with patch.object(kernel, 'make', side_effect=resolving_make):
            self.prepare()
            self.invoke('build', '--label', 'test', '--yes')
        self.assertEqual(len(resolutions), 3)
        self.assertEqual(resolutions[0], resolutions[1])
        self.assertNotEqual(resolutions[1], resolutions[2])

    def test_placeholder_rejects_leftover_files_and_symlinks(self):
        directory = kernel.empty_initramfs(self.root)
        (directory / 'stale-file').touch()
        with self.assertRaisesRegex(RuntimeError, 'must remain empty'):
            kernel.empty_initramfs(self.root)
        other = self.root / 'other'
        other.mkdir()
        (other / 'empty-initramfs').symlink_to(directory, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'real empty directory'):
            kernel.empty_initramfs(other)

    def test_bad_host_and_mismatched_boot_identity_fail_before_source_changes(self):
        for suffix in (['--host', '../thinktop'], ['--host', 'missing']):
            args = kernel.build_parser().parse_args(['config', '--label', 'test', '--config', str(self.start),
                                                    '--sources', str(self.sources), '--accept-defaults', '--yes', *suffix])
            with self.assertRaises((ValueError, RuntimeError)):
                kernel.configure(args)
        original = kernel.kernel_host.CMDLINE.read_text()
        for before, after in ((TEST_ROOT_UUID, TEST_PARTUUID), (TEST_LUKS_UUID, TEST_PARTUUID),
                              ('=cryptroot', '=wrong'), ('subvol=@', 'subvol=@other')):
            kernel.kernel_host.CMDLINE.write_text(original.replace(before, after))
            with self.assertRaises(RuntimeError):
                kernel.kernel_host.resolve_identity(kernel.run)
        self.assertEqual(kernel.version(self.sources), ('6.18.57', '-gentoo'))
        self.assertFalse(self.work.exists())

    def test_profile_overrides_are_frozen_and_enforced_during_build(self):
        profile = kernel.kernel_host.HOSTS / 'alternate.config'
        profile.write_text('CONFIG_EXTRA_FIRMWARE=""\nCONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"\nCONFIG_MODULES=y\n')
        self.invoke('config', '--label', 'test', '--host', 'alternate', '--config', str(self.start),
                    '--sources', str(self.sources), '--accept-defaults', '--yes')
        data = kernel.load(self.work, 'test')
        profile.unlink()
        self.assertEqual(data['host'], 'alternate')
        output, _ = kernel.paths(self.work, data)
        # Editing the candidate cannot silently defeat a reviewed host requirement.
        (output / '.config').write_text((output / '.config').read_text().replace('CONFIG_MODULES=y', 'CONFIG_MODULES=n'))
        with self.assertRaisesRegex(RuntimeError, 'host settings changed'):
            kernel.check_config(self.work, data)

    def test_profile_rejects_generated_settings_and_shell_syntax(self):
        profile = kernel.kernel_host.HOSTS / 'invalid.config'
        base = 'CONFIG_EXTRA_FIRMWARE="example.bin"\nCONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"\n'
        for addition in ('CONFIG_CMDLINE="root=wrong"\n', 'CONFIG_LOCALVERSION="-wrong"\n',
                         'CONFIG_INITRAMFS_SOURCE="/old/archive"\n', 'source /tmp/host\n',
                         'CONFIG_MODULES=$(command)\n', 'CONFIG_EXTRA_FIRMWARE="other.bin"\n'):
            profile.write_text(base + addition)
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                kernel.kernel_host.read_profile('invalid')

    def test_identity_rejects_duplicate_uuid_luks1_and_unsupported_unlock_policy(self):
        original = kernel.kernel_host.CMDLINE.read_text()
        for suffix in (f' root=UUID={TEST_ROOT_UUID}', ' rd.luks.options=tpm2-device=auto',
                       ' root_trim=no', ' resume=UUID=' + TEST_ROOT_UUID):
            kernel.kernel_host.CMDLINE.write_text(original + suffix)
            with self.subTest(suffix=suffix), self.assertRaises(RuntimeError):
                kernel.kernel_host.resolve_identity(kernel.run)
        kernel.kernel_host.CMDLINE.write_text(original)
        (kernel.kernel_host.SYS_BLOCK / 'dm-0/dm/uuid').write_text('CRYPT-LUKS1-test')
        with self.assertRaisesRegex(RuntimeError, 'requires LUKS2'):
            kernel.kernel_host.resolve_identity(kernel.run)

    def test_kconfig_lost_host_setting_rejects_configuration(self):
        original_make = kernel.make
        def resolving_make(work, data, *arguments, **kwargs):
            result = original_make(work, data, *arguments, **kwargs)
            if 'olddefconfig' in arguments:
                output, _ = kernel.paths(work, data)
                config = output / '.config'
                config.write_text(config.read_text().replace('CONFIG_CMDLINE_OVERRIDE=y', 'CONFIG_CMDLINE_OVERRIDE=n'))
            return result
        with patch.object(kernel, 'make', side_effect=resolving_make):
            with self.assertRaisesRegex(AssertionError, 'did not survive Kconfig'):
                self.prepare()
        self.assertFalse((self.work / kernel.METADATA).exists())

    def test_dracut_local_input_keeps_genkernel_compatibility(self):
        local = TEST_CMDLINE.replace(f'crypt_root=UUID={TEST_LUKS_UUID} ', '')
        kernel.kernel_host.CMDLINE.write_text(local)
        baseline = TEST_CMDLINE.replace(f'rd.luks.uuid=luks-{TEST_LUKS_UUID} rd.luks.name={TEST_LUKS_UUID}=cryptroot ', '')
        self.start.write_text('CONFIG_LOCALVERSION="-old"\nCONFIG_CMDLINE=' + json.dumps(baseline) +
                             '\n# CONFIG_MODULES is not set\n')
        self.prepare()
        data = kernel.load(self.work, 'test')
        self.assertEqual(data['identity']['local_cmdline'], local)
        self.assertEqual(data['identity']['cmdline'], baseline)
        self.assertNotIn('rd.luks.', data['identity']['cmdline'])
        self.assertEqual(kernel.kernel_host.CMDLINE.read_text(), local)
        self.invoke('build', '--label', 'test', '--genkernel', '--yes')
        self.invoke('build', '--label', 'test', '--yes')

    def test_shared_cmdline_retains_policy_and_replaces_only_storage_inputs(self):
        shared = ENTRY.parent.parent / 'share/agentoo/docs/kernel-shared-v04-config'
        baseline = json.loads(kernel.read_config(shared)['CONFIG_CMDLINE'])
        identity = kernel.kernel_host.resolve_identity(kernel.run)
        generated = kernel.kernel_host.specialize_cmdline(baseline, identity)
        replacements = {'root': 'UUID=' + TEST_ROOT_UUID, 'crypt_root': 'UUID=' + TEST_LUKS_UUID}
        self.assertNotIn('rd.luks.', generated)
        tokens = generated.split()
        for key, value in replacements.items():
            self.assertEqual([token for token in tokens if token.startswith(key + '=')], [key + '=' + value])
        for token in baseline.split():
            if not token.startswith(('root=', 'crypt_root=')):
                self.assertIn(token, tokens)
        self.assertNotIn('a0d8c112-b1fd-4a55-8515-d5eb8f13b76d', generated)
        self.assertNotIn('aace61a6-83ee-4825-b1e2-71d6fd3995ea', generated)
        self.start.write_text('CONFIG_LOCALVERSION="-old"\nCONFIG_CMDLINE=' + json.dumps(baseline) +
                             '\n# CONFIG_MODULES is not set\n')
        self.prepare()
        data = kernel.load(self.work, 'test')
        output, _ = kernel.paths(self.work, data)
        self.assertEqual(json.loads(kernel.read_config(output / '.config')['CONFIG_CMDLINE']), generated)
        self.assertEqual(data['identity']['cmdline'], generated)

    def test_cmdline_policy_quotes_and_missing_storage_arguments(self):
        identity = kernel.kernel_host.resolve_identity(kernel.run)
        generated = kernel.kernel_host.specialize_cmdline('root=UUID=old ro dyndbg="file example.c +p" console=tty0', identity)
        self.assertIn('dyndbg="file example.c +p" console=tty0', generated)
        self.assertIn('crypt_root=UUID=' + TEST_LUKS_UUID, generated)
        self.assertNotIn('rd.luks.', generated)
        for unsupported in ('root_trim=no', 'resume=UUID=old', 'rd.luks.key=/old/key'):
            with self.subTest(unsupported=unsupported), self.assertRaisesRegex(RuntimeError, 'unsupported initramfs policy'):
                kernel.kernel_host.specialize_cmdline('root=UUID=old ' + unsupported, identity)

    def test_cmdline_does_not_import_local_policy_and_keeps_explicit_dracut_style(self):
        identity = kernel.kernel_host.resolve_identity(kernel.run)
        identity['cmdline'] += ' console=ttyS0 loglevel=1'
        generated = kernel.kernel_host.specialize_cmdline('', identity)
        self.assertIn('crypt_root=UUID=' + TEST_LUKS_UUID, generated)
        self.assertIn('ro', generated.split())
        self.assertNotIn('rd.luks.', generated)
        self.assertNotIn('console=', generated)
        self.assertNotIn('loglevel=', generated)
        dracut_baseline = 'ro rd.luks.uuid=luks-old rd.luks.name=old=oldmapper'
        generated = kernel.kernel_host.specialize_cmdline(dracut_baseline, identity)
        self.assertNotIn('crypt_root=', generated)
        self.assertIn('rd.luks.uuid=luks-' + TEST_LUKS_UUID, generated)
        self.assertIn('rd.luks.name=' + TEST_LUKS_UUID + '=cryptroot', generated)

    def test_missing_firmware_and_legacy_workspace_fail_clearly(self):
        self.prepare()
        data = kernel.load(self.work, 'test')
        output, _ = kernel.paths(self.work, data)
        with (output / '.config').open('a') as stream:
            stream.write('CONFIG_EXTRA_FIRMWARE="missing-host-firmware.bin"\n')
        with self.assertRaisesRegex(RuntimeError, 'embedded firmware inputs missing'):
            kernel.validate_inputs(self.work, data)
        del data['identity']
        kernel.save(self.work, data)
        with self.assertRaisesRegex(RuntimeError, 'predates host specialization'):
            kernel.load(self.work, 'test')

    def test_build_runs_module_install_without_modules_and_regenerates_initramfs(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--genkernel', '--yes', '-j', '2')
        data = kernel.load(self.work, 'test', completed=True)
        output, gen = kernel.paths(self.work, data)
        archive = gen / 'output/initramfs-6.18.57-test.cpio'
        archive.write_text('stale archive')
        self.invoke('build', '--label', 'test', '--genkernel', '--yes')
        self.assertEqual(archive.read_text(), 'fresh archive')
        calls = self.calls()
        self.assertFalse(any('genkernel' in call for call in calls if call[0] == 'sudo'))
        installs = [call for call in calls if call[0] == 'make' and 'modules_install' in call]
        self.assertEqual(len(installs), 2)
        self.assertEqual(sum(any(x.startswith('INSTALL_MOD_PATH=') for x in call) for call in installs), 2)
        self.assertTrue(all('--no-ramdisk-modules' in call for call in calls if call[0] == 'genkernel'))
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_CMDLINE'], json.dumps(TEST_CMDLINE))
        (output / '.config').write_text('modified after build')
        with self.assertRaisesRegex(RuntimeError, 'image/config changed'):
            kernel.load(self.work, 'test', completed=True)

    def test_default_build_regenerates_minimal_archive_in_workspace(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--yes')
        archive = self.work / 'initramfs/6.18.57-test/initramfs.cpio'
        self.assertEqual(archive.read_text(), 'fresh minimal archive')
        data = kernel.load(self.work, 'test', completed=True)
        (kernel.staged_modules(self.work, data) / 'stale.ko').write_text('obsolete')
        archive.write_text('stale')
        self.invoke('build', '--label', 'test', '--no-genkernel', '--yes')
        self.assertEqual(archive.read_text(), 'fresh minimal archive')
        data = kernel.load(self.work, 'test', completed=True)
        output, _ = kernel.paths(self.work, data)
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_INITRAMFS_SOURCE'], json.dumps(str(archive)))
        self.assertFalse(any(call[0] == 'genkernel' for call in self.calls()))
        self.assertFalse((kernel.staged_modules(self.work, data) / 'stale.ko').exists())
        self.assertEqual(len([call for call in self.calls() if call[0] == 'minimal-initramfs']), 2)
        call = next(call for call in self.calls() if call[0] == 'minimal-initramfs')
        self.assertEqual(call[call.index('--partuuid') + 1], TEST_PARTUUID)
        self.assertEqual(call[call.index('--mapper') + 1], 'cryptroot')

    def test_minimal_builder_rejects_module_kernel_before_compilation(self):
        self.start.write_text(self.start.read_text().replace('# CONFIG_MODULES is not set', 'CONFIG_MODULES=y'))
        self.prepare()
        args = kernel.build_parser().parse_args(['build', '--label', 'test', '--yes'])
        with self.assertRaisesRegex(RuntimeError, 'built-in drivers'):
            kernel.build(args)
        self.assertFalse(any('modules_install' in call for call in self.calls()))

    def test_custom_archive_implies_no_genkernel_and_module_config_is_retained(self):
        self.start.write_text(self.start.read_text().replace('# CONFIG_MODULES is not set', 'CONFIG_MODULES=y'))
        self.prepare()
        archive = self.root / 'custom.cpio'
        archive.write_text('custom input')
        self.invoke('build', '--label', 'test', '--initramfs', str(archive), '--yes')
        self.assertFalse(any(call[0] in ('genkernel', 'minimal-initramfs') for call in self.calls()))
        self.assertEqual(len([call for call in self.calls() if call[0] == 'make' and 'modules_install' in call]), 1)
        data = kernel.load(self.work, 'test', completed=True)
        output, gen = kernel.paths(self.work, data)
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_MODULES'], 'y')
        self.assertEqual((gen / 'output/initramfs-6.18.57-test.cpio').read_text(), 'custom input')

    def test_module_build_stays_unprivileged_and_install_uses_staged_tree(self):
        self.start.write_text(self.start.read_text().replace('# CONFIG_MODULES is not set', 'CONFIG_MODULES=y'))
        self.prepare()
        start = len(self.calls())
        self.invoke('build', '--label', 'test', '--genkernel', '--yes')
        self.assertFalse(any(call[0] == 'sudo' for call in self.calls()[start:]))
        self.assertFalse(kernel.MODULES_ROOT.exists())
        genkernel_calls = [call for call in self.calls()[start:] if call[0] == 'genkernel']
        self.assertEqual(len(genkernel_calls), 1)
        self.assertIn('--ramdisk-modules', genkernel_calls[0])
        data = kernel.load(self.work, 'test', completed=True)
        modules = kernel.staged_modules(self.work, data)
        self.assertEqual((modules / 'kernel/drivers/example.ko').read_text(), 'compiled module')
        self.assertIn('--kernel-modules-prefix=' + str(modules.parents[2]), genkernel_calls[0])
        # Installation uses the completed artifacts, not make or the sources.
        import shutil
        shutil.rmtree(self.sources)
        start = len(self.calls())
        destination = self.root / 'esp/EFI/Gentoo'
        device = dict(pkname='/dev/test', partn=1, partuuid='test')
        with patch.object(kernel, 'esp_details', return_value=(device, 'loader')):
            self.invoke('install', '--label', 'test', '--dest', str(destination), '--yes')
        installed = kernel.MODULES_ROOT / data['release']
        self.assertEqual((installed / 'kernel/drivers/example.ko').read_text(), 'compiled module')
        self.assertEqual((installed / 'modules.builtin').read_bytes(), (modules / 'modules.builtin').read_bytes())
        self.assertEqual(os.readlink(installed / 'build'), os.readlink(modules / 'build'))
        calls = self.calls()[start:]
        self.assertFalse(any(call[0] == 'make' for call in calls))
        self.assertIn(['depmod', '-a', data['release']], calls)
        self.assertLess(next(i for i, call in enumerate(calls) if call[0] == 'depmod'),
                        next(i for i, call in enumerate(calls) if call[0] == 'sudo' and 'mv' in call))

    def test_module_permissions_with_restrictive_umask(self):
        self.start.write_text(self.start.read_text().replace('# CONFIG_MODULES is not set', 'CONFIG_MODULES=y'))
        self.prepare()
        previous = os.umask(0o077)
        try:
            self.invoke('build', '--label', 'test', '--genkernel', '--yes')
            data = kernel.load(self.work, 'test', completed=True)
            modules = kernel.staged_modules(self.work, data)
            for path in [modules, *modules.rglob('*')]:
                if not path.is_symlink():
                    self.assertEqual(path.stat().st_mode & 0o777,
                                     0o755 if path.is_dir() else 0o644, str(path))
            destination = self.root / 'esp/EFI/Gentoo'
            device = dict(pkname='/dev/test', partn=1, partuuid='test')
            with patch.object(kernel, 'esp_details', return_value=(device, 'loader')):
                self.invoke('install', '--label', 'test', '--dest', str(destination), '--yes')
            installed = kernel.MODULES_ROOT / data['release']
            for name in ('modules.builtin', 'modules.builtin.modinfo', 'modules.builtin.bin',
                         'kernel/drivers/example.ko'):
                self.assertEqual((installed / name).stat().st_mode & 0o777, 0o644, name)
        finally:
            os.umask(previous)

    def test_install_rejects_changed_or_missing_staged_modules(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--yes')
        data = kernel.load(self.work, 'test', completed=True)
        modules = kernel.staged_modules(self.work, data)
        (modules / 'modules.builtin').write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'staged modules changed'):
            kernel.load(self.work, 'test', completed=True)
        (modules / 'modules.builtin').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing modules.builtin'):
            kernel.load(self.work, 'test', completed=True)

    def test_depmod_failure_leaves_efi_image_unchanged(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--yes')
        destination = self.root / 'esp/EFI/Gentoo'
        destination.mkdir(parents=True)
        image = destination / 'kernel-6.18.57-test.efi'
        image.write_text('working image')
        args = kernel.build_parser().parse_args(['install', '--label', 'test', '--dest', str(destination), '--yes'])
        device = dict(pkname='/dev/test', partn=1, partuuid='test')
        with patch.object(kernel, 'esp_details', return_value=(device, 'loader')), \
                patch.dict(os.environ, FAIL_DEPMOD='1'), tempfile.TemporaryFile(mode='w+') as errors, redirect_stderr(errors):
            with self.assertRaisesRegex(RuntimeError, 'depmod.*exited 1'):
                kernel.install(args)
        self.assertEqual(image.read_text(), 'working image')
        self.assertFalse(list(destination.glob('*.bak')))

    def test_install_backs_up_existing_image_and_prints_registration(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--yes')
        destination = self.root / 'esp/EFI/Gentoo'
        destination.mkdir(parents=True)
        image = destination / 'kernel-6.18.57-test.efi'
        image.write_text('known previous image')
        device = dict(pkname='/dev/test', partn=1, partuuid='test')
        with patch.object(kernel, 'esp_details', return_value=(device, r'\EFI\Gentoo\kernel-6.18.57-test.efi')):
            stdout, stderr = self.invoke('install', '--label', 'test', '--dest', str(destination), '--yes')
        self.assertEqual(next(destination.glob('*.bak')).read_text(), 'known previous image')
        self.assertIn('CONFIG_LOCALVERSION="-test"', image.read_text())
        self.assertIn('efibootmgr', stdout)
        self.assertIn('Backup:', stderr)

    def test_discovery_refuses_ambiguous_workspaces_and_changed_sources(self):
        self.prepare()
        other = self.root / '6.18.58-test'
        import shutil
        shutil.copytree(self.work, other)
        args = kernel.build_parser().parse_args(['build', '--label', 'test'])
        with self.assertRaisesRegex(RuntimeError, 'found 2'):
            kernel.select_workspace(args)
        (self.sources / 'Makefile').write_text('changed source')
        with self.assertRaisesRegex(RuntimeError, 'source Makefile changed'):
            kernel.load(self.work, 'test')

    def test_firmware_registration_preserves_other_entry_order(self):
        before = 'BootOrder: 0003,0001\nBoot0001* Windows\nBoot0003* Prior kernel\n'
        after = before.replace('BootOrder: 0003,0001', 'BootOrder: 0004,0003,0001') + 'Boot0004* New kernel\n'
        with patch.object(kernel, 'run', side_effect=[before, '', after, '', after]) as run, redirect_stdout(io.StringIO()):
            kernel.register_entry(['efibootmgr', '--create'], dict(partn=1, partuuid='uuid'), r'\EFI\Gentoo\new.efi')
        self.assertEqual(run.call_args_list[1].args[0], ['efibootmgr', '--create'])
        self.assertEqual(run.call_args_list[1].kwargs['umask'], 0o022)
        self.assertEqual(run.call_args_list[-2].args[0], ['efibootmgr', '--bootorder', '0004,0003,0001'])
        existing = before + 'Boot0004* New kernel\tHD(1,GPT,uuid,0x800,0x200000)/\\EFI\\Gentoo\\new.efi\n'
        with patch.object(kernel, 'run', side_effect=[existing, '', existing]) as run, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            kernel.register_entry(['efibootmgr', '--create'], dict(partn=1, partuuid='uuid'), r'\EFI\Gentoo\new.efi')
        self.assertFalse(any('--create' in call.args[0] for call in run.call_args_list))


if __name__ == '__main__':
    unittest.main()
