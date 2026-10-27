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


class KernelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = self.root / 'sources'
        (self.sources / 'scripts').mkdir(parents=True)
        (self.sources / 'Makefile').write_text('VERSION = 6\nPATCHLEVEL = 18\nSUBLEVEL = 57\nEXTRAVERSION = -gentoo\nNAME = Test\n')
        self.start = self.root / 'starting.config'
        self.start.write_text('CONFIG_LOCALVERSION="-old"\nCONFIG_CMDLINE="root=UUID=test ro"\n# CONFIG_MODULES is not set\nCONFIG_INITRAMFS_SOURCE="/missing/old-build.cpio"\n')
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
        self.env = patch.dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', KERNEL_TEST_LOG=str(self.log))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.workspaces = patch.object(kernel, 'WORKSPACES', self.root)
        self.workspaces.start()
        self.addCleanup(self.workspaces.stop)
        self.work = self.root / '6.18.57-test'

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

    def test_config_handoff_preserves_cmdline_and_rejects_reconfiguration(self):
        self.prepare()
        data = kernel.load(self.work, 'test')
        output, _ = kernel.paths(self.work, data)
        values = kernel.read_config(output / '.config')
        self.assertEqual(values['CONFIG_CMDLINE'], '"root=UUID=test ro"')
        self.assertEqual(values['CONFIG_LOCALVERSION'], '"-test"')
        self.assertEqual(values['CONFIG_IKCONFIG_PROC'], 'y')
        self.assertEqual(kernel.version(self.sources), ('6.18.57', ''))
        self.assertTrue(list(self.sources.glob('Makefile.agentoo-*.bak')))
        with self.assertRaisesRegex(RuntimeError, 'empty or absent'):
            kernel.configure(kernel.build_parser().parse_args(['config', '--label', 'test', '--config', str(self.start), '--sources', str(self.sources), '--accept-defaults', '--yes']))

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
        self.assertEqual(len(installs), 4)
        self.assertEqual(sum(any(x.startswith('INSTALL_MOD_PATH=') for x in call) for call in installs), 2)
        self.assertTrue(all('--no-ramdisk-modules' in call for call in calls if call[0] == 'genkernel'))
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_CMDLINE'], '"root=UUID=test ro"')
        (output / '.config').write_text('modified after build')
        with self.assertRaisesRegex(RuntimeError, 'image/config changed'):
            kernel.load(self.work, 'test', completed=True)

    def test_default_build_regenerates_minimal_archive_in_workspace(self):
        self.prepare()
        self.invoke('build', '--label', 'test', '--yes')
        archive = self.work / 'initramfs/6.18.57-test/initramfs.cpio'
        self.assertEqual(archive.read_text(), 'fresh minimal archive')
        archive.write_text('stale')
        self.invoke('build', '--label', 'test', '--no-genkernel', '--yes')
        self.assertEqual(archive.read_text(), 'fresh minimal archive')
        data = kernel.load(self.work, 'test', completed=True)
        output, _ = kernel.paths(self.work, data)
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_INITRAMFS_SOURCE'], json.dumps(str(archive)))
        self.assertFalse(any(call[0] == 'genkernel' for call in self.calls()))
        self.assertEqual(len([call for call in self.calls() if call[0] == 'minimal-initramfs']), 2)

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
        self.assertEqual(len([call for call in self.calls() if call[0] == 'make' and 'modules_install' in call]), 2)
        data = kernel.load(self.work, 'test', completed=True)
        output, gen = kernel.paths(self.work, data)
        self.assertEqual(kernel.read_config(output / '.config')['CONFIG_MODULES'], 'y')
        self.assertEqual((gen / 'output/initramfs-6.18.57-test.cpio').read_text(), 'custom input')

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
