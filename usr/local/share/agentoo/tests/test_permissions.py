"""Run with python3 -m unittest discover -s usr/local/share/agentoo/tests."""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'bin/agentoo-permissions'))


class PermissionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.uid, self.gid = os.getuid(), os.getgid()
        (self.root / 'share').mkdir()
        self.write('etc/agentoo/permissions.conf', self.policy())
        self.git('init', '-q')
        self.git('add', '.')

    def policy(self, extra=''):
        return (f'tree etc/  {self.uid} {self.gid} 0644 0755\n'
                f'tree share/ {self.uid} {self.gid} 0644 0755\n' + extra)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, relative, contents='test', mode=0o644):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contents)
        p.chmod(mode)
        return p

    def entries(self):
        rules = MODULE['load_policy'](self.root)
        return MODULE['managed_entries'](rules, MODULE['tracked_files'](self.root))

    def repair(self):
        output = io.StringIO()
        # Exercise real chmod as an ordinary developer; ownership is unchanged.
        with patch('sys.argv', ['agentoo permissions', 'fix', '--root', str(self.root)]), \
                patch('os.geteuid', return_value=0), patch('os.fchown'), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = MODULE['main']()
        return result, output.getvalue()

    def test_add_delete_move_and_untracked_state(self):
        self.write('share/cards/backlog/card.md')
        self.git('add', '.')
        self.write('share/local-secret', mode=0o600)
        self.write('share/untracked/deep/local', mode=0o600)
        self.write('share/cards/backlog/untracked', mode=0o600)
        entries, problems = self.entries()
        self.assertFalse(problems)
        self.assertIn(('share/cards/backlog', True), entries)
        self.assertNotIn(('share/local-secret', False), entries)
        self.assertNotIn(('share/untracked', True), entries)
        (self.root / 'share/cards/completed').mkdir()
        self.git('mv', 'share/cards/backlog/card.md', 'share/cards/completed/card.md')
        entries, problems = self.entries()
        self.assertFalse(problems)
        self.assertIn(('share/cards/completed/card.md', False), entries)
        self.assertNotIn(('share/cards/backlog', True), entries)
        self.git('rm', '-f', 'share/cards/completed/card.md')
        self.assertFalse(self.entries()[1])
        self.assertEqual(self.repair()[0], 0)
        self.assertEqual((self.root / 'share/local-secret').stat().st_mode & 0o777, 0o600)

    def test_exceptions_and_order_independence(self):
        extra = (f'tree share/hooks/ {self.uid} {self.gid} 0755 0750\n'
                 f'file share/hooks/readme {self.uid} {self.gid} 0600\n'
                 f'dir share/hooks/ {self.uid} {self.gid} 0700\n')
        policy = self.policy(extra)
        self.write('etc/agentoo/permissions.conf', policy)
        self.write('share/hooks/run', mode=0o600)
        self.write('share/hooks/readme')
        self.git('add', '.')
        original = self.entries()
        lines = policy.splitlines()
        random.Random(17).shuffle(lines)
        self.write('etc/agentoo/permissions.conf', '\n'.join(lines))
        self.assertEqual(original, self.entries())
        self.assertEqual(self.repair()[0], 0)
        for path, mode in [('share/hooks', 0o700), ('share/hooks/run', 0o755), ('share/hooks/readme', 0o600)]:
            self.assertEqual((self.root / path).stat().st_mode & 0o777, mode)

    def test_uncovered_path_blocks_all_fixes(self):
        managed = self.write('share/managed', mode=0o600)
        self.write('outside/uncovered')
        self.git('add', '.')
        result, output = self.repair()
        self.assertEqual(result, 1)
        self.assertIn('no permission policy', output)
        self.assertEqual(managed.stat().st_mode & 0o777, 0o600)

    def test_symlinks_and_fifo_block_all_fixes(self):
        managed = self.write('share/managed', mode=0o600)
        target = self.write('share/directory/target')
        self.git('add', '.')
        for scenario in ['leaf', 'parent', 'fifo']:
            with self.subTest(scenario=scenario):
                target.unlink()
                if scenario == 'leaf':
                    target.symlink_to(managed)
                elif scenario == 'parent':
                    target.parent.rmdir()
                    target.parent.symlink_to(self.root / 'etc')
                else:
                    os.mkfifo(target)
                self.assertEqual(self.repair()[0], 1)
                self.assertEqual(managed.stat().st_mode & 0o777, 0o600)
                if scenario == 'parent':
                    target.parent.unlink()
                    target.parent.mkdir()
                else:
                    target.unlink()
                target.write_text('restored')

    def test_invalid_and_duplicate_rules(self):
        for extra in [self.policy().splitlines()[0] + '\n',
                      f'tree ../escape/ {self.uid} {self.gid} 0644 0755\n',
                      f'file /absolute {self.uid} {self.gid} 0644\n',
                      f'file share//bad {self.uid} {self.gid} 0644\n',
                      f'file share/bad {self.uid} {self.gid} 4755\n',
                      f'file share {self.uid} {self.gid} 0644\n']:
            with self.subTest(extra=extra):
                self.write('etc/agentoo/permissions.conf', self.policy(extra))
                with self.assertRaises(ValueError):
                    MODULE['load_policy'](self.root)

    def test_missing_roots_exceptions_and_tracked_files(self):
        self.write('share/tracked')
        self.git('add', '.')
        (self.root / 'share/tracked').unlink()
        self.assertEqual(self.repair()[0], 1)
        self.write('share/tracked')
        self.write('etc/agentoo/permissions.conf', self.policy(
            f'file share/stale {self.uid} {self.gid} 0700\n'))
        self.assertEqual(self.repair()[0], 1)

    def test_sparse_checkout_excludes_exact_and_inherited_files(self):
        self.write('README.md')
        self.write('share/excluded')
        self.write('share/retained')
        self.write('etc/agentoo/permissions.conf', self.policy(
            f'file README.md {self.uid} {self.gid} 0644\n'))
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                 'commit', '-qm', 'fixture')
        self.git('sparse-checkout', 'set', '--no-cone',
                 '/*', '!/README.md', '!/share/excluded')
        self.assertFalse((self.root / 'README.md').exists())
        self.assertFalse((self.root / 'share/excluded').exists())
        entries, problems = self.entries()
        self.assertFalse(problems)
        self.assertNotIn(('README.md', False), entries)
        self.assertNotIn(('share/excluded', False), entries)
        self.assertEqual(self.repair()[0], 0)
        self.assertEqual(self.git('status', '--porcelain'), b'')
        self.git('sparse-checkout', 'disable')
        self.assertTrue((self.root / 'README.md').exists())
        self.assertIn(('README.md', False), self.entries()[0])
        self.assertEqual(self.repair()[0], 0)

    def test_installed_repository_discovery(self):
        repo = self.root / 'var/lib/agentoo/repository.git'
        repo.parent.mkdir(parents=True)
        (self.root / '.git').rename(repo)
        tracked = MODULE['tracked_files'](self.root)
        self.assertIn('etc/agentoo/permissions.conf', tracked)
        self.assertFalse(self.entries()[1])

    def test_check_reports_without_changes(self):
        managed = self.write('share/managed', mode=0o600)
        self.git('add', '.')
        with patch('sys.argv', ['agentoo permissions', 'check', '--root', str(self.root)]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE['main'](), 1)
        self.assertEqual(managed.stat().st_mode & 0o777, 0o600)

    def test_directory_only_rule_and_missing_tree(self):
        self.write('etc/agentoo/permissions.conf', self.policy(
            f'dir private/ {self.uid} {self.gid} 0700\n'))
        local = self.write('private/local-secret', mode=0o600)
        self.assertEqual(self.repair()[0], 0)
        self.assertEqual(local.stat().st_mode & 0o777, 0o600)
        self.assertEqual(local.parent.stat().st_mode & 0o777, 0o700)
        self.write('etc/agentoo/permissions.conf', self.policy(
            f'tree missing/ {self.uid} {self.gid} 0644 0755\n'))
        self.assertEqual(self.repair()[0], 1)

    def test_missing_repository_fails(self):
        self.temp.cleanup()
        self.root.mkdir()
        with self.assertRaises(ValueError):
            MODULE['tracked_files'](self.root)

    def test_json_check_findings_and_exit(self):
        self.write('share/wrong', mode=0o600)
        self.git('add', '.')
        output = io.StringIO()
        with patch('sys.argv', ['agentoo-permissions', 'check', '--root', str(self.root), '--json']), \
                contextlib.redirect_stdout(output):
            result = MODULE['main']()
        self.assertEqual(result, 1)
        report = json.loads(output.getvalue())
        finding = next(item for item in report['mismatches'] if item['path'] == '/share/wrong')
        self.assertEqual(finding['actual']['mode'], '0600')
        self.assertEqual(finding['expected']['mode'], '0644')
        self.assertEqual(report['errors'], [])

    def test_repository_policy_preserves_git_executable_bits(self):
        root = Path(__file__).resolve().parents[5]
        rules = MODULE['load_policy'](root)
        entries = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-s', '-z'])
        for entry in entries.split(b'\0'):
            if not entry:
                continue
            metadata, relative = os.fsdecode(entry).split('\t', 1)
            mode = metadata.split()[0]
            if mode not in ('100644', '100755'):
                continue
            expected = MODULE['resolve_rule'](rules, relative)
            with self.subTest(path=relative):
                self.assertIsNotNone(expected)
                self.assertEqual(bool(int(mode, 8) & 0o111), bool(expected[2] & 0o111),
                                 'permission repair would change the Git executable bit')

    def test_no_input_privilege_request_uses_sudo_noninteractive(self):
        with patch('sys.argv', ['agentoo-permissions', 'fix', '--no-input']), \
                patch('os.execvp', side_effect=SystemExit(37)) as execute, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MODULE['elevate']()
        self.assertEqual(execute.call_args.args[1][:3], ['sudo', '-n', '--'])


if __name__ == '__main__':
    unittest.main()
