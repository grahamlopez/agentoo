"""Test the real installed udev rules with private /dev and /run.

The sandbox cannot open host block devices. A test-only rule supplies filesystem
probe properties; the full disposable-container smoke test uses actual blkid.
No uevents are emitted and no host udev database or devices are changed.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1] / 'initramfs'


class BuilderArgumentsTest(unittest.TestCase):
    def test_check_mode_validates_inputs_without_building_or_creating_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            work = root / 'output'
            keymap = root / 'keymap'
            keymap.touch()
            command = [sys.executable, str(HERE / 'build'), '--check', '--work', str(work),
                       '--partuuid', '33333333-3333-4333-8333-333333333333',
                       '--busybox-source', str(source), '--keymap', str(keymap)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('source tree missing Makefile', result.stderr)
            self.assertFalse(work.exists())
            (source / 'Makefile').touch()
            tools = root / 'bin'
            tools.mkdir()
            for name in ('make', 'cc', 'cpio', 'loadkeys', 'strip', 'cryptsetup', 'ldd'):
                tool = tools / name
                # Only ldd should execute during preflight; compilers/builders must not run.
                tool.write_text('#!/bin/sh\nexit ' + ('0' if name == 'ldd' else '99') + '\n')
                tool.chmod(0o755)
            result = subprocess.run(command, capture_output=True, text=True, env={**os.environ, 'PATH': str(tools)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(work.exists())
            keymap.unlink()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('console keymap missing', result.stderr)
            self.assertFalse(work.exists())

    def test_requires_explicit_partition_and_rejects_invalid_mapping_before_building(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / 'output'
            base = [sys.executable, str(HERE / 'build'), '--work', str(work)]
            for arguments, message in (([], '--partuuid'),
                                       (['--partuuid', 'not-a-uuid'], 'invalid GPT PARTUUID'),
                                       (['--partuuid', '33333333-3333-4333-8333-333333333333',
                                         '--mapper', '../bad'], 'invalid root mapping name')):
                with self.subTest(arguments=arguments):
                    result = subprocess.run([*base, *arguments], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)
                    self.assertFalse(work.exists())


class HandoffTest(unittest.TestCase):
    def test_coldplug_accepts_only_prepared_mapping(self):
        if not all(shutil.which(tool) for tool in ('unshare', 'udevadm', 'mount')):
            self.skipTest('requires unshare, mount and udevadm')
        mapping = next((block for block in Path('/sys/class/block').glob('dm-*')
                        if (block / 'dm/uuid').read_text().startswith('CRYPT-LUKS2-')), None)
        if mapping is None:
            self.skipTest('requires readable LUKS2 mapping sysfs attributes')
        probe = subprocess.run(['unshare', '--user', '--map-root-user', '--mount', 'true'],
                               capture_output=True)
        if probe.returncode:
            self.skipTest('requires user and mount namespaces')
        name = (mapping / 'dm/name').read_text().strip()
        with tempfile.TemporaryDirectory() as temporary:
            script = r'''
set -eu
mount --make-rprivate /
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /dev
mkdir -p /run/udev/rules.d
# Test fixture only: block-device probing is unavailable in the sandbox.
printf '%s\n' 'SUBSYSTEM=="block", ENV{ID_FS_USAGE}="filesystem", ENV{ID_FS_UUID}="handoff-test", ENV{ID_FS_UUID_ENC}="handoff-test"' > /run/udev/rules.d/12-agentoo-test-probe.rules
udevadm test --action=add "$3" > "$4/before" 2>&1
. "$1"
prepare_udev_handoff "$2"
udevadm verify /run/udev/rules.d/09-agentoo-initramfs-root.rules
udevadm test --action=add "$3" > "$4/after" 2>&1
# A different mapping UUID must not be accepted by the generated rule.
sed -i 's/ATTR{dm\/uuid}=="[^"]*"/ATTR{dm\/uuid}=="not-this-mapping"/' /run/udev/rules.d/09-agentoo-initramfs-root.rules
udevadm test --action=add "$3" > "$4/unmatched" 2>&1
'''
            result = subprocess.run([
                'unshare', '--user', '--map-root-user', '--mount', 'sh', '-c', script,
                'handoff-test', str(HERE / 'udev-handoff'), name, str(mapping), temporary,
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            before, after, unmatched = [Path(temporary, file).read_text()
                                         for file in ('before', 'after', 'unmatched')]
            for output in (before, unmatched):
                self.assertIn('  SYSTEMD_READY=0\n', output)
                self.assertIn('  DM_UDEV_DISABLE_DISK_RULES_FLAG=1\n', output)
                self.assertNotIn('/dev/disk/by-uuid/handoff-test', output)
            self.assertIn('  DM_UDEV_PRIMARY_SOURCE_FLAG=1\n', after)
            self.assertIn('/dev/disk/by-uuid/handoff-test', after)
            self.assertIn('  DM_NAME=' + name + '\n', after)
            self.assertNotIn('  SYSTEMD_READY=0\n', after)
            self.assertNotIn('  DM_UDEV_DISABLE_DISK_RULES_FLAG=1\n', after)


if __name__ == '__main__':
    unittest.main()
