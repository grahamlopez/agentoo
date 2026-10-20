"""Checkpoint contracts using temporary directories and mocked filesystem tools."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / 'boot/agentoo/checkpoint.sh'


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.run = self.root / 'run'
        self.run.mkdir()
        self.fixture = self.root / 'fixture'
        self.store = self.fixture / 'gentoo-checkpoints'
        self.store.mkdir(parents=True)
        (self.fixture / '@').mkdir()
        (self.fixture / '@home').mkdir()
        for cache in ('distfiles', 'binpkgs', 'binhost'):
            directory = self.fixture / '@/var/cache' / cache
            directory.mkdir(parents=True)
            (directory / 'keep-during-dry-run').write_text('cached file')
        self.log = self.root / 'calls'
        tool = self.bin / 'tool'
        tool.write_text('''#!/usr/bin/env python3
import json,os,sys,shutil
from pathlib import Path
name=Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write(json.dumps([name,*args])+'\\n')
if name=='id': print(0 if os.environ.get('ROOT_USER','1')=='1' else 1000)
elif name=='sudo': sys.exit(37)
elif name=='pgrep': sys.exit(1)
elif name=='portageq': print('/var/cache/distfiles' if args[-1]=='DISTDIR' else '/var/cache/binpkgs')
elif name=='stat': print('1:1')
elif name=='df': print('Filesystem 1024-blocks Used Available Capacity Mounted on\\n/dev/mock 10000000 0 9000000 0% /')
elif name=='mount': shutil.copytree(os.environ['FIXTURE'],args[-1],dirs_exist_ok=True)
elif name=='umount': pass
elif name=='findmnt':
    field=args[args.index('-o')+1]
    target=args[-1]
    if field=='TARGET': print(target)
    elif field=='FSTYPE': print('btrfs')
    elif field=='FSROOT': print('/@home' if target=='/home' else '/@')
    elif field=='UUID': print(os.environ.get('ROOT_UUID','fixture-uuid') if target=='/' else 'fixture-uuid')
    elif field=='UUID,FSROOT,TARGET': print('other-uuid / /')
    elif field=='OPTIONS': print('rw')
elif name=='btrfs':
    if args[:2]==['subvolume','show']: print('UUID: snapshot-uuid')
    elif args[:2]==['property','get']: print('ro=true')
    elif args[:2]==['filesystem','du']:
        if os.environ.get('BAD_SIZES'): sys.exit(1)
        print('Total Exclusive Set shared Filename\\n123 45 67 path')
    elif args[:2]==['subvolume','list']: pass
    else: sys.exit('unexpected mutating btrfs: '+repr(args))
else: sys.exit('unexpected tool '+name)
''')
        tool.chmod(0o755)
        for name in ('id', 'sudo', 'pgrep', 'portageq', 'stat', 'df', 'mount', 'umount', 'findmnt', 'btrfs'):
            (self.bin / name).symlink_to(tool)
        self.script = self.root / 'checkpoint.sh'
        self.script.write_text(SCRIPT.read_text().replace('/run/agentoo-checkpoint', str(self.run / 'agentoo-checkpoint')))
        self.env = dict(os.environ, PATH=f'{self.bin}:' + os.environ['PATH'], CALLS=str(self.log), FIXTURE=str(self.fixture))

    def invoke(self, *args, **env):
        return subprocess.run(['sh', str(self.script), *args], env=dict(self.env, **env),
                              text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def checkpoint(self, name='saved'):
        cp = self.store / name
        cp.mkdir()
        (cp / 'COMPLETE').write_text(name + '\n', errors='surrogateescape')
        (cp / 'manifest').write_text(f'format=2\nname={name}\nroot_uuid=fixture-uuid\nesp_uuid=none\nsystem=1\nhome=0\nefi=0\nsystem_uuid=snapshot-uuid\n', errors='surrogateescape')
        (cp / 'system').mkdir()
        return cp

    def test_help_precedes_tools_and_invalid_values(self):
        result = self.invoke('restore', '--device', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls())
        self.assertIn('restore NAME', result.stdout)

    def test_validation_precedes_privileges(self):
        for args in [('restore', 'saved', '--confirm=other', '--device=/mock'),
                     ('create', 'label', '--no-input'), ('create', '--', '--help')]:
            result = self.invoke(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.calls())

    def test_no_input_sudo_is_noninteractive(self):
        result = self.invoke('restore', '--device=/mock', '--no-input', '--confirm=saved', 'saved', ROOT_USER='0')
        self.assertEqual(result.returncode, 37)
        self.assertEqual(self.calls()[-1][:3], ['sudo', '-n', '--'])

    def test_system_capture_defaults_to_cleanup_but_dry_run_preserves_files(self):
        result = self.invoke('create', '--system', '--dry-run', '--no-input', '--efi-mount=/unused', 'label')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertIn('DELETE distfiles and binary packages', result.stderr)
        self.assertTrue(any(call[0] == 'portageq' for call in self.calls()))
        for cache in ('distfiles', 'binpkgs', 'binhost'):
            self.assertTrue((self.fixture / '@/var/cache' / cache / 'keep-during-dry-run').exists())
        mount = next(call for call in self.calls() if call[0]=='mount')
        self.assertIn('subvolid=5,ro,rescue=nologreplay', mount)
        self.assertFalse(any(call[1:3] in [['subvolume','snapshot'], ['subvolume','delete']] for call in self.calls()))

    def test_explicit_preservation_overrides_system_cleanup_default(self):
        result = self.invoke('create', 'label', '--system', '--dry-run', '--no-input', '--no-clean-package-caches')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('keep distfiles and binary packages', result.stderr)
        self.assertFalse(any(call[0] == 'portageq' for call in self.calls()))

    def test_legacy_cache_spellings_rejected_before_privileges(self):
        for flag in ('--clean-distfiles', '--no-clean-distfiles'):
            result = self.invoke('create', 'label', '--dry-run', flag)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unknown option: ' + flag, result.stderr)
            self.assertFalse(self.calls())

    def test_home_only_capture_preserves_caches_without_cleanup_tools(self):
        result = self.invoke('create', 'label', '--home', '--dry-run', '--no-input')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('keep distfiles and binary packages', result.stderr)
        self.assertFalse(any(call[0] == 'portageq' for call in self.calls()))

    def test_human_list_preserves_unavailable_size_warning_and_success(self):
        self.checkpoint()
        result = self.invoke('list', '--device=/mock')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('TOTAL', result.stdout)
        self.assertIn('123', result.stdout)
        self.assertIn('saved', result.stdout)
        self.assertIn('--human-readable', next(c for c in self.calls() if c[1:3] == ['filesystem', 'du']))
        result = self.invoke('list', '--device=/mock', BAD_SIZES='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('?', result.stdout)
        self.assertIn('saved', result.stdout)
        self.assertIn('Warning: sizes unavailable for saved', result.stderr)

    def test_removed_json_flag_rejected_before_tools(self):
        for args in [('list', '--json'), ('inspect', 'saved', '--json'),
                     ('create', 'label', '--json'),
                     ('restore', 'saved', '--device=/mock', '--json')]:
            result = self.invoke(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unknown option: --json', result.stderr)
            self.assertFalse(self.calls())

    def test_inspect_manifest_emitted_only_after_verification(self):
        cp = self.checkpoint()
        manifest = (cp / 'manifest').read_text()
        result = self.invoke('inspect', '--device', '/mock', 'saved')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, manifest)
        self.assertIn('Recorded components verified; target unchanged.', result.stderr)
        (cp / 'COMPLETE').unlink()
        result = self.invoke('inspect', '--device', '/mock', 'saved')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_restore_dry_run_never_snapshots_or_deletes(self):
        self.checkpoint()
        result = self.invoke('restore', '--system', '--dry-run', '--no-input', '--device=/mock', '--', 'saved', ROOT_UUID='other-uuid')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DISCARD current state', result.stderr)
        self.assertIn('subvolid=5,ro,rescue=nologreplay', next(c for c in self.calls() if c[0]=='mount'))
        self.assertFalse(any(c[1:3] in [['subvolume','snapshot'], ['subvolume','delete']] for c in self.calls()))


if __name__ == '__main__':
    unittest.main()
