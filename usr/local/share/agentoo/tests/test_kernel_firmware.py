"""Exercise native savedconfig application with disposable files and fake emerge."""
from contextlib import redirect_stdout
import gzip
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import kernel_firmware as firmware


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('LISTS', 'SAVED', 'VDB', 'FIRMWARE', 'BOOT', 'BACKUPS'):
            path = self.root / name.lower()
            path.mkdir()
            change = patch.object(firmware, name, path)
            change.start()
            self.addCleanup(change.stop)
        selector = self.root / 'target-host'
        selector.write_text('GENTOO_TARGET_HOST="flattop"\n')
        profiles = self.root / 'profiles'
        profiles.mkdir()
        (profiles / 'flattop.config').write_text('CONFIG_EXTRA_FIRMWARE="device.bin regulatory.db"\nCONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"\n')
        config = self.root / 'config.gz'
        config.write_bytes(gzip.compress(b'CONFIG_EXTRA_FIRMWARE="device.bin regulatory.db"\nCONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"\n'))
        microcode = self.root / 'microcode'
        microcode.write_text('0x1234\n')
        for module, name, value in ((firmware.kernel_host, 'SELECTOR', selector),
                                    (firmware.kernel_host, 'HOSTS', profiles),
                                    (firmware, 'KERNEL_CONFIG', config), (firmware, 'MICROCODE', microcode)):
            change = patch.object(module, name, value)
            change.start()
            self.addCleanup(change.stop)
        self.package = dict(cpv='sys-kernel/linux-firmware-20260622-r1', pf='linux-firmware-20260622-r1',
                            p='linux-firmware-20260622', chost='build-triplet', ctarget='target-triplet',
                            use={'savedconfig', 'dist-kernel', 'initramfs'}, installed_use=set(), available=True)
        change = patch.object(firmware, 'portage_state', side_effect=lambda: self.package)
        change.start()
        self.addCleanup(change.stop)
        self.list = firmware.LISTS / 'flattop.list'
        self.list.write_text('# reviewed\ndevice.bin\nalias.bin\n')
        (firmware.FIRMWARE / 'device.bin').write_bytes(b'firmware payload')
        (firmware.FIRMWARE / 'alias.bin').symlink_to('device.bin')
        (firmware.FIRMWARE / 'old.bin').write_bytes(b'old unrelated payload')
        self.write_inventory({'device.bin', 'alias.bin', 'old.bin'})
        self.inputs = [firmware.SAVED / 'sys-kernel' / self.package['pf'],
                       firmware.SAVED / 'sys-kernel' / self.package['p'],
                       firmware.SAVED / 'target-triplet/sys-kernel/linux-firmware',
                       firmware.SAVED / 'sys-kernel/linux-firmware']
        for path in self.inputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# previous\ndevice.bin\nalias.bin\nold.bin\n')
        self.future = firmware.SAVED / 'sys-kernel/linux-firmware-20260701'
        self.future.write_text('future.bin\n')
        self.calls = []
        self.messages = []
        self.merge_entries = {'device.bin', 'alias.bin'}
        self.fail_rebuild = False
        self.confirm = lambda *args: None
        self.args = SimpleNamespace(yes=True, dry_run=False, firmware_operation='apply')

    def write_inventory(self, names):
        directory = firmware.VDB / self.package['cpv']
        directory.mkdir(parents=True, exist_ok=True)
        lines = [('sym /lib/firmware/alias.bin -> device.bin 0' if name == 'alias.bin'
                  else f'obj /lib/firmware/{name} fakehash 0') for name in sorted(names)]
        (directory / 'CONTENTS').write_text('\n'.join(lines) + '\n')

    def run_command(self, command, *, root=False, capture=False):
        command = list(map(str, command))
        self.calls.append((command, root))
        self.assertTrue(root)
        if command[0] == 'mount':
            self.assertEqual(command[1], str(firmware.BOOT))
            return ''
        if command[0] == 'emerge':
            if '--pretend' not in command:
                if self.fail_rebuild:
                    raise RuntimeError('simulated emerge failure')
                path = firmware.SAVED / 'sys-kernel' / self.package['pf']
                path.write_text('# generated native snapshot\n' + '\n'.join(sorted(self.merge_entries)) + '\n')
                self.write_inventory(self.merge_entries)
            return ''
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip() if capture else ''

    def apply(self):
        with patch.object(firmware.shutil, 'which', return_value='/test/tool'):
            firmware.apply(self.args, firmware.inspect(), run=self.run_command, confirm=self.confirm, notice=self.messages.append)

    def test_status_is_read_only_and_reports_policy_precedence_and_embedded_names(self):
        before = {path: path.read_bytes() for path in self.inputs}
        output = io.StringIO()
        with redirect_stdout(output):
            firmware.command(SimpleNamespace(firmware_operation=None), run=lambda *a, **k: self.fail('status ran a command'),
                             confirm=lambda *a: self.fail('status confirmed'), notice=self.messages.append)
        text = output.getvalue()
        for expected in ('Target host: flattop', 'Configured USE: savedconfig', 'Installed package savedconfig: disabled',
                         str(self.inputs[0]), '[first match]', '0 missing, 1 extra', 'microcode: 0x1234',
                         'device.bin [linux-firmware]', 'regulatory.db [not owned by installed linux-firmware]'):
            self.assertIn(expected, text)
        self.assertEqual({path: path.read_bytes() for path in self.inputs}, before)
        self.assertEqual(self.calls, [])

    def test_precedence_matches_revision_version_target_build_and_native_empty_target(self):
        paths = firmware.candidates(self.package)
        self.assertEqual(paths[:3], [firmware.SAVED / triplet / 'sys-kernel' / self.package['pf']
                                    for triplet in ('target-triplet', 'build-triplet', '')])
        self.assertLess(paths.index(self.inputs[1]), paths.index(self.inputs[2]))
        self.package['ctarget'] = ''
        paths = firmware.candidates(self.package)
        self.assertEqual(paths[0], self.inputs[0])
        self.assertEqual(paths[1], firmware.SAVED / 'build-triplet/sys-kernel' / self.package['pf'])
        self.assertEqual(len(paths), len(set(paths)))
        # Once PN exists at the plain path, this native lower-priority input stays untouched.
        lower = firmware.SAVED / 'build-triplet/sys-kernel/linux-firmware'
        lower.parent.mkdir(parents=True)
        lower.write_text('lower.bin\n')
        _, retired = firmware.plan(firmware.inspect())
        self.assertNotIn(lower, [item['path'] for item in retired])

    def test_dry_run_never_confirms_mounts_sudos_or_changes_files(self):
        self.args.dry_run = True
        self.confirm = lambda *args: self.fail('dry run confirmed')
        before = {path: path.read_bytes() for path in self.inputs}
        self.apply()
        self.assertEqual(self.calls, [])
        self.assertEqual({path: path.read_bytes() for path in self.inputs}, before)
        self.assertEqual(list(firmware.BACKUPS.iterdir()), [])
        self.assertTrue(any('Source rebuild:' in message for message in self.messages))

    def test_apply_retires_only_overrides_backs_up_and_rebuilds_from_source(self):
        original = {path: path.read_bytes() for path in self.inputs}
        kernel = firmware.KERNEL_CONFIG.read_bytes()
        self.apply()
        backups = list(firmware.BACKUPS.iterdir())
        self.assertEqual(len(backups), 1)
        backup = backups[0]
        for path in self.inputs[:-1]:
            self.assertEqual((backup / 'retired' / path.relative_to(firmware.SAVED)).read_bytes(), original[path])
        self.assertEqual((backup / 'savedconfig/sys-kernel/linux-firmware').read_bytes(), original[self.inputs[-1]])
        self.assertEqual(self.inputs[-1].read_bytes(), self.list.read_bytes())
        self.assertEqual(self.inputs[-1].stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.future.read_text(), 'future.bin\n')
        self.assertEqual(firmware.KERNEL_CONFIG.read_bytes(), kernel)
        emerge = [call for call, _ in self.calls if call[0] == 'emerge']
        self.assertEqual(len(emerge), 2)
        self.assertIn('--pretend', emerge[0])
        self.assertNotIn('--pretend', emerge[1])
        for flag in ('--ignore-default-opts', '--usepkg=n', '--getbinpkg=n', '=' + self.package['cpv']):
            self.assertIn(flag, emerge[1])
        self.assertFalse(any(flag.startswith(('--usepkgonly', '--getbinpkgonly')) for flag in emerge[1]))
        self.assertLess(next(i for i, (call, _) in enumerate(self.calls) if call[0] == 'mount'),
                        next(i for i, (call, _) in enumerate(self.calls) if call[0] == 'emerge'))
        self.assertTrue(any('Applied 2 paths' in message for message in self.messages))

    def test_repeated_apply_gets_unique_backups_and_retires_new_snapshot(self):
        self.apply()
        self.apply()
        self.assertEqual(len(list(firmware.BACKUPS.iterdir())), 2)

    def test_rebuild_failure_keeps_backups_and_reports_partial_application(self):
        self.fail_rebuild = True
        with self.assertRaisesRegex(RuntimeError, 'simulated emerge failure'):
            self.apply()
        self.assertEqual(len(list(firmware.BACKUPS.iterdir())), 1)
        self.assertEqual(self.inputs[-1].read_bytes(), self.list.read_bytes())
        self.assertTrue(any('No automatic rollback' in message for message in self.messages))

    def test_pretend_failure_leaves_savedconfigs_unchanged(self):
        original = {path: path.read_bytes() for path in self.inputs}
        def failing_pretend(command, **kwargs):
            if str(command[0]) == 'emerge':
                self.assertIn('--pretend', command)
                raise RuntimeError('pretend resolver failure')
            return self.run_command(command, **kwargs)
        with self.assertRaisesRegex(RuntimeError, 'pretend resolver failure'):
            firmware.apply(self.args, firmware.inspect(), run=failing_pretend, confirm=self.confirm, notice=self.messages.append)
        self.assertEqual({path: path.read_bytes() for path in self.inputs}, original)
        self.assertEqual(list(firmware.BACKUPS.iterdir()), [])

    def test_source_command_keeps_ebuilds_enabled_in_native_portage_parser(self):
        try:
            from _emerge.main import parse_opts
        except ImportError:
            self.skipTest('requires Gentoo Portage')
        self.apply()
        command = next(command for command, _ in self.calls if command[0] == 'emerge' and '--pretend' not in command)
        action, options, atoms = parse_opts(command[1:])
        self.assertIsNone(action)
        self.assertEqual(atoms, ['=' + self.package['cpv']])
        self.assertIn('--ignore-default-opts', options)
        self.assertIs(options['--usepkg'], False)
        self.assertIs(options['--getbinpkg'], False)
        # Native depgraph.py gates the source DB on membership, not truthiness.
        self.assertNotIn('--usepkgonly', options)
        self.assertNotIn('--getbinpkgonly', options)

    def test_successful_emerge_with_wrong_snapshot_is_not_reported_as_accepted(self):
        self.merge_entries = {'device.bin'}
        with self.assertRaisesRegex(RuntimeError, 'installed selection needs review'):
            self.apply()
        self.assertFalse(any('Applied 2 paths' in message for message in self.messages))
        self.assertTrue(any('alias.bin' in message for message in self.messages))

    def test_invalid_or_undeployed_policy_never_mutates(self):
        for invalid in ('/absolute.bin\n', '../outside.bin\n', '*.bin\n', 'device.bin\ndevice.bin\n', '# empty\n'):
            self.list.write_text(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.apply()
        self.list.write_text('device.bin\nalias.bin\n')
        self.package['use'].discard('savedconfig')
        with self.assertRaisesRegex(RuntimeError, 'deploy its Portage policy'):
            self.apply()
        self.package['use'].add('savedconfig')
        self.package['available'] = False
        with self.assertRaisesRegex(RuntimeError, 'no source ebuild'):
            self.apply()
        self.package['available'] = True
        self.list.unlink()
        with self.assertRaisesRegex(RuntimeError, 'no reviewed host list'):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_symlink_input_and_changed_host_list_are_rejected_before_mutation(self):
        self.inputs[0].unlink()
        self.inputs[0].symlink_to(self.future)
        with self.assertRaisesRegex(RuntimeError, 'not symlinks/directories'):
            self.apply()
        self.inputs[0].unlink()
        self.confirm = lambda *args: self.list.write_text('changed.bin\n')
        with self.assertRaisesRegex(RuntimeError, 'host list changed'):
            self.apply()
        self.assertEqual(self.calls, [])

    def test_absent_package_profile_and_kernel_config_are_reported_without_sudo(self):
        self.package = None
        self.list.unlink()
        firmware.KERNEL_CONFIG.unlink()
        (firmware.kernel_host.HOSTS / 'flattop.config').unlink()
        output = io.StringIO()
        with redirect_stdout(output):
            firmware.show_status(firmware.inspect())
        self.assertIn('linux-firmware: not installed', output.getvalue())
        self.assertIn('not present; no reviewed selection', output.getvalue())
        self.assertIn('unavailable:', output.getvalue())

    def test_directory_symlinks_are_not_reported_as_broken_firmware(self):
        (firmware.FIRMWARE / 'family').mkdir()
        (firmware.FIRMWARE / 'family-alias').symlink_to('family', target_is_directory=True)
        contents = firmware.VDB / self.package['cpv'] / 'CONTENTS'
        with contents.open('a') as stream:
            stream.write('sym /lib/firmware/family-alias -> family 0\n')
        self.assertNotIn('family-alias', firmware.inventory(self.package)['missing'])

    def test_inaccessible_native_input_is_not_silently_treated_as_absent(self):
        with patch.object(Path, 'lstat', side_effect=PermissionError('input directory unreadable')):
            item = firmware.list_info(self.inputs[0])
        self.assertTrue(item['exists'])
        self.assertIn('unreadable', item['error'])
        state = firmware.inspect()
        state['inputs'][0] = item
        with self.assertRaisesRegex(RuntimeError, 'readable regular files'):
            firmware.plan(state)

    def test_triplet_cannot_escape_native_savedconfig_directory(self):
        self.package['ctarget'] = '../outside'
        with self.assertRaisesRegex(ValueError, 'unsupported Portage triplet'):
            firmware.candidates(self.package)


if __name__ == '__main__':
    unittest.main()
