"""Native kernel preparation, boot-critical validation and read-only EFI guidance."""
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SHARE = Path(__file__).resolve().parents[1]
ENTRY = SHARE.parents[1] / 'bin/agentoo-kernel'
spec = importlib.util.spec_from_loader('native_kernel_cli', SourceFileLoader('native_kernel_cli', str(ENTRY)))
kernel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kernel)
host = kernel.kernel_host
UUID = '33333333-3333-4333-8333-333333333333'


class NativeKernelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.profile = self.root / 'hosts/test.config'
        self.profile.parent.mkdir()
        self.firmware = self.root / 'firmware'
        self.firmware.mkdir()
        (self.firmware / 'device.bin').write_bytes(b'firmware')
        self.profile.write_text('CONFIG_EXTRA_FIRMWARE="device.bin"\n'
                                f'CONFIG_EXTRA_FIRMWARE_DIR="{self.firmware}"\n')
        self.link = self.root / '20-host.config'
        self.link.symlink_to(self.profile)
        for obj, name, value in ((host, 'HOSTS', self.profile.parent),
                                 (host, 'HOST_LINK', self.link),
                                 (kernel, 'LOCAL_INPUTS', self.root / 'kernel-local'),
                                 (kernel, 'INSTALL_CONF', self.root / 'custom/install.conf'),
                                 (kernel, 'ESP_IDENTITY', self.root / 'esp.uuid'),
                                 (kernel, 'SBCTL_HOOK', self.root / '91-sbctl.install'),
                                 (kernel, 'DIST_CMDLINE', self.root / 'cmdline')):
            change = patch.object(obj, name, value)
            change.start()
            self.addCleanup(change.stop)
        change = patch.object(host, 'read_host', return_value='test')
        change.start()
        self.addCleanup(change.stop)
        self.device = dict(path='/dev/test1', pkname='/dev/test', partn=1, partuuid=UUID,
                           parttype='c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
        self.image = self.root / 'EFI/Gentoo/kernel-6.18.62-gentoo-dist-agentoo.efi'
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b'EFI image')
        self.mount = dict(source='/dev/test1', target=str(self.root), fstype='vfat')

    def inspect_run(self, cmd, **kwargs):
        if cmd[0] == 'findmnt':
            return json.dumps({'filesystems': [self.mount]})
        if cmd[0] == 'lsblk':
            return json.dumps({'blockdevices': [self.device]})
        self.fail(f'unexpected operation: {cmd}')

    def efi(self, *arguments):
        args = kernel.build_parser().parse_args(['gen-efi-cmd', '--image', str(self.image), *arguments])
        with patch.object(kernel, 'run', side_effect=self.inspect_run), redirect_stdout(io.StringIO()) as out:
            kernel.gen_efi_cmd(args)
        return shlex.split(out.getvalue())

    def test_custom_registration_is_create_only_and_preserves_literal_arguments(self):
        arguments = 'quiet test="two words" literal=$HOME;$(touch marker)'
        cmd = self.efi('--args', arguments, '--label', "Thinktop's kernel")
        self.assertEqual(cmd, ['sudo', 'efibootmgr', '--create-only', '--disk', '/dev/test', '--part', '1',
                              '--label', "Thinktop's kernel", '--loader',
                              r'\EFI\Gentoo\kernel-6.18.62-gentoo-dist-agentoo.efi', '--unicode', '--', arguments])
        self.assertNotIn('initrd=', ' '.join(self.efi()))
        with patch.object(host, 'read_host', return_value='startop'):
            self.assertIn('--full-dev-path', self.efi())

    def test_binary_registration_requires_its_own_cmdline_and_initramfs(self):
        self.image = self.image.with_name('kernel-6.18.62-gentoo-dist-bin.efi')
        self.image.write_bytes(b'binary image')
        with self.assertRaisesRegex(RuntimeError, 'initramfs'):
            self.efi()
        archive = self.image.with_name('initramfs-6.18.62-gentoo-dist-bin.img')
        archive.write_bytes(b'archive')
        kernel.DIST_CMDLINE.write_text('root=UUID=test ro\n')
        self.assertEqual(self.efi('--args', 'debug')[-1],
                         r'root=UUID=test ro initrd=\EFI\Gentoo\initramfs-6.18.62-gentoo-dist-bin.img debug')
        kernel.DIST_CMDLINE.write_text('')
        with self.assertRaisesRegex(RuntimeError, 'command line is empty'):
            self.efi()

    def test_registration_rejects_missing_image_wrong_filesystem_or_non_gpt_esp(self):
        self.mount['fstype'] = 'btrfs'
        with self.assertRaisesRegex(RuntimeError, 'mounted FAT'):
            self.efi()
        self.mount['fstype'] = 'vfat'
        self.device['parttype'] = 'not-esp'
        with self.assertRaisesRegex(RuntimeError, 'GPT EFI'):
            self.efi()
        self.image.unlink()
        with self.assertRaisesRegex(RuntimeError, 'image not found'):
            self.efi()

    def test_prepare_records_validated_local_inputs_and_only_activates_native_files(self):
        identity = dict(partuuid=UUID, mapper='cryptroot', keymap='/keymap', transport='nvme')
        writes = []
        def run(cmd, **kwargs):
            if cmd[0] == 'findmnt':
                return 'ABCD-1234'
            writes.append([str(x) for x in cmd])
            if cmd[0] == 'install' and '-D' in cmd:
                Path(cmd[-1]).write_text(Path(cmd[-2]).read_text())
            return ''
        with patch.object(host, 'resolve_identity', return_value=identity), \
                patch.object(kernel, 'inspect_esp', return_value=(self.device, 'unused')), \
                patch.object(kernel, 'run', side_effect=run):
            kernel.prepare(SimpleNamespace(yes=True))
        self.assertIn(f'AGENTOO_INITRAMFS_PARTUUID={UUID}', kernel.LOCAL_INPUTS.read_text())
        self.assertIn('AGENTOO_INITRAMFS_TRANSPORT=nvme', kernel.LOCAL_INPUTS.read_text())
        self.assertEqual(kernel.ESP_IDENTITY.read_text(), 'ABCD-1234\n')
        self.assertTrue(any(cmd[:2] == ['ln', '-sfnT'] and cmd[-1] == str(self.link) for cmd in writes))
        self.assertFalse(any(cmd[0] in ('emerge', 'efibootmgr', 'mount') for cmd in writes))
        self.profile.write_text(self.profile.read_text() + 'CONFIG_MODULES=y\n')
        with self.assertRaisesRegex(RuntimeError, 'module-enabled host'):
            kernel.prepare(SimpleNamespace(yes=True))

    def config(self):
        archive = self.root / 'initramfs.cpio'
        archive.write_bytes(b'archive')
        values = {f'CONFIG_{name}': 'y' for name in (*host.MINIMAL_BUILTINS, 'BLK_DEV_NVME', 'FB_EFI',
                  'EFI_STUB', 'BLK_DEV_INITRD', 'IKCONFIG', 'IKCONFIG_PROC', 'CMDLINE_BOOL')}
        values.update(CONFIG_MODULES='n', CONFIG_CMDLINE_OVERRIDE='n', CONFIG_INITRAMFS_ROOT_UID='0',
                      CONFIG_INITRAMFS_ROOT_GID='0', CONFIG_INITRAMFS_SOURCE=json.dumps(str(archive)))
        path = self.root / '.config'
        path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()) + self.profile.read_text())
        return path

    def test_final_validation_rejects_modules_missing_boot_driver_archive_firmware_or_wrong_host(self):
        path = self.config()
        host.validate_config(path, 'nvme')
        for old, new, message in [('CONFIG_MODULES=n', 'CONFIG_MODULES=y', 'CONFIG_MODULES=n'),
                                  ('CONFIG_BLK_DEV_NVME=y', 'CONFIG_BLK_DEV_NVME=n', 'boot support')]:
            text = path.read_text()
            path.write_text(text.replace(old, new))
            with self.assertRaisesRegex(RuntimeError, message):
                host.validate_config(path, 'nvme')
            path.write_text(text)
        self.link.unlink()
        with self.assertRaisesRegex(RuntimeError, 'selected profile'):
            host.validate_config(path, 'nvme')
        self.link.symlink_to(self.profile)
        (self.root / 'initramfs.cpio').unlink()
        with self.assertRaisesRegex(RuntimeError, 'initramfs is missing'):
            host.validate_config(path, 'nvme')
        (self.root / 'initramfs.cpio').write_bytes(b'archive')
        (self.firmware / 'device.bin').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing embedded firmware'):
            host.validate_config(path, 'nvme')

    def test_storage_identity_rejects_wrong_layout_and_luks_version(self):
        dm = self.root / 'sys/dm-0/dm'
        dm.mkdir(parents=True)
        (dm / 'name').write_text('cryptroot')
        (dm / 'uuid').write_text('CRYPT-LUKS2-test')
        mount = dict(source='/dev/mapper/cryptroot[/@]', fstype='btrfs', fsroot='/@')
        root = dict(kname='dm-0', type='crypt', fstype='btrfs', uuid=UUID,
                    children=[dict(type='part', fstype='crypto_LUKS', uuid=UUID, partuuid=UUID,
                                   children=[dict(type='disk', tran='nvme')])])
        def run(cmd, **kwargs):
            return json.dumps({'filesystems': [mount]} if cmd[0] == 'findmnt' else {'blockdevices': [root]})
        with patch.object(host, 'SYS_BLOCK', self.root / 'sys'):
            self.assertEqual(host.resolve_identity(run)['mapper'], 'cryptroot')
            mount['fsroot'] = '/other'
            with self.assertRaisesRegex(RuntimeError, 'Btrfs @'):
                host.resolve_identity(run)
            mount['fsroot'] = '/@'
            (dm / 'uuid').write_text('CRYPT-LUKS1-test')
            with self.assertRaisesRegex(RuntimeError, 'LUKS2'):
                host.resolve_identity(run)

    def test_removed_lifecycle_commands_are_not_aliases(self):
        for name in ('config', 'build', 'install'):
            result = subprocess.run([sys.executable, str(ENTRY), name], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('invalid choice', result.stderr)

    def test_shared_esp_guard_checks_custom_and_binary_targets_before_copy(self):
        guard = SHARE.parents[3] / 'etc/kernel/install.d/04-agentoo-esp.install'
        # SHARE is usr/local/share/agentoo; its third parent is the repo root.
        expected = self.root / 'expected-esp'
        expected.write_text('ABCD-1234\n')
        script = self.root / 'guard'
        script.write_text(guard.read_text().replace('/etc/kernel/gentoo-dist-esp.uuid', str(expected)))
        tools = self.root / 'bin'
        tools.mkdir()
        (tools / 'mountpoint').write_text('#!/bin/sh\nexit "${MOUNT_EXIT:-0}"\n')
        (tools / 'findmnt').write_text('#!/bin/sh\ncase "$*" in *FSTYPE*) echo vfat ;; *) echo "$ESP_UUID" ;; esac\n')
        for tool in tools.iterdir():
            tool.chmod(0o755)
        for release in ('6.18.62-gentoo-dist-bin', '6.18.62-gentoo-dist-agentoo'):
            for uuid, mounted, status in [('ABCD-1234', '0', 0), ('wrong', '0', 1), ('ABCD-1234', '1', 1)]:
                result = subprocess.run(['bash', str(script), 'add', release], capture_output=True, text=True,
                                        env={**os.environ, 'PATH': f'{tools}:'+os.environ['PATH'],
                                             'ESP_UUID': uuid, 'MOUNT_EXIT': mounted})
                self.assertEqual(result.returncode, status, result.stderr)

    def test_install_guidance_calls_the_cli_and_preserves_portage_elog(self):
        hook = SHARE.parents[3] / 'etc/kernel/install.d/99-agentoo-boot-guidance.install'
        cli = self.root / 'efi-cli'
        calls = self.root / 'calls'
        cli.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > '+shlex.quote(str(calls))+
                       '\nprintf "sudo efibootmgr --create-only\\n"\n')
        cli.chmod(0o755)
        script = self.root / 'guidance'
        text = hook.read_text().replace('/usr/local/bin/agentoo-kernel', str(cli))
        text = text.replace('image=/boot/EFI/Gentoo/', f'image={self.image.parent}/')
        # Offline/host detection is orthogonal to forwarding one EFI implementation.
        text = '\n'.join(line for line in text.splitlines() if '/proc/1/root' not in line)+'\n'
        script.write_text(text)
        logging = self.root / 'logging'
        logging.mkdir()
        result = subprocess.run(['bash', str(script), 'add', '6.18.62-gentoo-dist-agentoo'],
                                capture_output=True, text=True,
                                env={**os.environ, 'T': str(self.root), 'EBUILD_PHASE': 'postinst'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.read_text().strip(), f'gen-efi-cmd --image {self.image}')
        self.assertEqual(result.stdout, 'sudo efibootmgr --create-only\n')
        self.assertIn('LOG sudo efibootmgr --create-only', (logging/'postinst').read_text())


if __name__ == '__main__':
    unittest.main()
