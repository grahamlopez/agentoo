"""Real repository fixtures and terminal escape checks for the small utilities."""
import contextlib
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

BIN = Path(__file__).resolve().parents[3] / 'bin'


def load(name):
    loader = SourceFileLoader('test_agentoo_' + name, str(BIN / ('agentoo-' + name)))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


repos = load('repos')
colors = load('term-colors')


class ReposTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        env = {**os.environ, 'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
               'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
               'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
               'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
            env.pop(key, None)
        self.environment = patch.dict(os.environ, env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def git(self, path, *args):
        return subprocess.run(['git', '-C', str(path), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def repository(self, name='repo'):
        path = self.home / name
        path.mkdir(parents=True)
        self.git(path, 'init', '-b', 'main')
        (path / 'file').write_text('original\n')
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-m', 'initial')
        return path

    def invoke(self, *args, system=None, uid=0):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(repos, 'SYSTEM_GIT', system or self.root / 'absent.git'), \
             patch.object(repos.os, 'geteuid', return_value=uid), \
             patch('sys.argv', ['agentoo-repos', '--json', *args]), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = repos.main()
        return code, json.loads(output.getvalue()), errors.getvalue()

    def test_sudo_declined_or_cancelled_preserves_home_scan(self):
        local = self.repository()
        system = self.root / 'system.git'
        system.mkdir()
        for failure in (subprocess.CompletedProcess([], 1), KeyboardInterrupt()):
            original = subprocess.run
            def authenticate_or_run(command, **kwargs):
                if command[0] == 'sudo':
                    if isinstance(failure, KeyboardInterrupt):
                        raise failure
                    return failure
                return original(command, **kwargs)
            with patch.object(repos.subprocess, 'run', side_effect=authenticate_or_run):
                code, data, _ = self.invoke(system=system, uid=1000)
            self.assertEqual(code, 1)
            self.assertEqual(len(data['repositories']), 2)
            self.assertIsNone(next(r for r in data['repositories'] if r['work_tree'] == str(local))['error'])
            self.assertIn('unavailable', next(r for r in data['repositories'] if r['work_tree'] == '/')['error'])

    def test_sudo_authorization_modes_and_fixed_scope(self):
        with patch.object(repos.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout=b'ok')) as run:
            self.assertIsNone(repos.authorize_system(True))
            self.assertEqual(run.call_args.args[0], ['sudo', '-n', '-v'])
            self.assertIsNone(repos.authorize_system(False))
            self.assertEqual(run.call_args.args[0], ['sudo', '-v'])
            repos.git(repos.SYSTEM_GIT, Path('/'), 'status', privileged=True)
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ['sudo', '-n', '--', 'env'])
            self.assertIn('--git-dir=' + str(repos.SYSTEM_GIT), command)
            self.assertIn('--work-tree=/', command)
            with self.assertRaises(ValueError):
                repos.git(self.root / 'user.git', self.home, 'status', privileged=True)

    def test_sudo_success_only_elevates_system_and_path_skips_sudo(self):
        local = self.repository()
        system = self.root / 'system.git'
        system.mkdir()
        original = repos.status
        calls = []
        def check(metadata, work_tree, tracked_only=False, privileged=False):
            calls.append((metadata, privileged))
            if privileged:
                return {'git_dir': str(metadata), 'work_tree': '/', 'error': None}
            return original(metadata, work_tree, tracked_only)
        with patch.object(repos, 'authorize_system', return_value=None) as auth, patch.object(repos, 'status', side_effect=check):
            code, _, _ = self.invoke('--no-input', system=system, uid=1000)
            self.assertEqual(code, 0)
            auth.assert_called_once_with(True)
            self.assertEqual(calls, [(system, True), (local / '.git', False)])
            auth.reset_mock()
            self.invoke('--path=' + str(local), system=system, uid=1000)
            auth.assert_not_called()

    def test_status_rename_unusual_names_and_untracked(self):
        path = self.repository()
        self.git(path, 'mv', 'file', '? newline\nname')
        (path / '? newline\nname').write_text('original\nchanged\n')
        (path / 'untracked\nfile').touch()
        record = repos.status(path / '.git', path)
        self.assertEqual((record['staged'], record['modified'], record['untracked']), (1, 1, 1))
        self.assertEqual(record['branch'], 'main')
        self.assertIsNone(record['upstream'])

    def test_fetch_preserves_interactive_auth_and_no_input_is_explicit(self):
        path = self.repository()
        reply = subprocess.CompletedProcess([], 0, stdout=b'', stderr=b'')
        with patch.dict(os.environ, {k: v for k, v in os.environ.items()
                                    if k not in ('GIT_TERMINAL_PROMPT', 'GIT_SSH_COMMAND', 'GCM_INTERACTIVE')}, clear=True), \
             patch.object(repos.subprocess, 'run', return_value=reply) as run:
            repos.git(path / '.git', path, 'fetch', timeout=None)
            options = run.call_args.kwargs
            self.assertNotIn('GIT_SSH_COMMAND', options['env'])
            self.assertNotIn('GIT_TERMINAL_PROMPT', options['env'])
            self.assertIsNone(options['stdin'])
            self.assertIsNone(options['stderr'])
            self.assertIsNone(options['timeout'])
            repos.git(path / '.git', path, 'fetch', no_input=True, timeout=60)
            options = run.call_args.kwargs
            self.assertEqual(options['env']['GIT_SSH_COMMAND'], 'ssh -oBatchMode=yes')
            self.assertEqual(options['env']['GIT_TERMINAL_PROMPT'], '0')
            self.assertEqual(options['env']['GIT_ASKPASS'], '/bin/false')
            self.assertEqual(options['env']['SSH_ASKPASS_REQUIRE'], 'never')
            self.assertEqual(options['stdin'], subprocess.DEVNULL)
            self.assertEqual(options['stderr'], subprocess.PIPE)
            self.assertEqual(options['timeout'], 60)
        with patch.dict(os.environ, {'GIT_SSH_COMMAND': 'my-ssh-wrapper'}), \
             patch.object(repos.subprocess, 'run', return_value=reply) as run:
            repos.git(path / '.git', path, 'fetch')
            self.assertEqual(run.call_args.kwargs['env']['GIT_SSH_COMMAND'], 'my-ssh-wrapper')

    def test_fetch_uses_repository_ssh_configuration(self):
        path = self.repository()
        # A fake transport proves Git honors core.sshCommand without networking
        # or requiring the test runner's SSH keys, agent, or terminal.
        transport = self.root / 'ssh-test'
        transport.write_text('#!/bin/sh\necho REPOSITORY_SSH_TRANSPORT >&2\nexit 1\n')
        transport.chmod(0o755)
        self.git(path, 'config', 'core.sshCommand', str(transport))
        self.git(path, 'config', 'ssh.variant', 'ssh')
        self.git(path, 'remote', 'add', 'origin', 'git@example.invalid:repo')
        env = {k: v for k, v in os.environ.items() if k != 'GIT_SSH_COMMAND'}
        result = subprocess.run([str(BIN / 'agentoo-repos'), '--path=' + str(path), '--fetch', '--json'],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('REPOSITORY_SSH_TRANSPORT', result.stderr)
        self.assertIn('see fetch diagnostics above', json.loads(result.stdout)['repositories'][0]['fetch_error'])

    def test_table_alignment_and_nonclean_highlights(self):
        path = self.repository()
        clean = repos.status(path / '.git', path)
        clean.update(upstream='origin/main', ahead=0, behind=0)
        dirty = {**clean, 'work_tree': str(self.home / 'longer repo'),
                 'modified': 2, 'ahead': 1, 'behind': 1, 'fetch_error': 'failed'}
        error = {'work_tree': '/', 'git_dir': str(repos.SYSTEM_GIT), 'error': 'denied'}
        records = [clean, dirty, error]
        plain = repos.format_table(records)
        colored = repos.format_table(records, color=True)
        self.assertEqual(re.sub(r'\x1b\[[0-9;]*m', '', colored), plain)
        self.assertNotIn('\x1b', repos.format_table([clean], color=True))
        self.assertIn('\x1b[33m2 modified', colored)
        self.assertIn('\x1b[31m↑1 ↓1', colored)
        self.assertIn('\x1b[31mfetch failed', colored)
        self.assertIn('system Agentoo (/)', plain)
        lines = plain.splitlines()
        column = lines[0].index('WORKTREE')
        for line, word in zip(lines[1:], ['clean', '2 modified', 'unavailable']):
            self.assertEqual(line.index(word), column)

    def test_worktree_nested_hidden_exclusions_and_deduplication(self):
        path = self.repository('.hidden/repo')
        linked = self.home / 'linked'
        self.git(path, 'worktree', 'add', '-b', 'linked', str(linked))
        self.repository('node_modules/ignored')
        self.repository('skip/ignored')
        errors = []
        found = list(repos.discover([self.home, self.home], ['skip'], errors))
        self.assertFalse(errors)
        self.assertEqual({p[1] for p in found}, {path, linked})
        self.assertEqual(len(found), 2)
        self.assertEqual(repos.status(found[0][0], found[0][1])['modified'], 0)

    def test_default_system_root_worktree_and_explicit_path(self):
        local = self.repository()
        system = self.root / 'system.git'
        self.git(self.root, 'init', '--bare', '-b', 'main', str(system))
        tracked = self.root / 'system-file'
        tracked.write_text('before\n')
        command = ['git', '--git-dir=' + str(system), '--work-tree=/']
        subprocess.run([*command, 'add', str(tracked)], check=True, capture_output=True)
        subprocess.run([*command, 'commit', '-m', 'system'], check=True, capture_output=True)
        tracked.write_text('after\n')
        (self.root / 'untracked').touch()
        code, data, _ = self.invoke(system=system)
        self.assertEqual(code, 0)
        self.assertEqual(len(data['repositories']), 2)
        root_record = next(r for r in data['repositories'] if r['work_tree'] == '/')
        self.assertEqual(root_record['modified'], 1)
        self.assertIsNone(root_record['untracked'])
        code, data, _ = self.invoke('--path=' + str(local), system=system)
        self.assertEqual(code, 0)
        self.assertEqual([r['work_tree'] for r in data['repositories']], [str(local)])

    def test_bare_home_worktree_and_configuration(self):
        bare = self.home / '.dots-git'
        self.git(self.home, 'init', '--bare', '-b', 'main', str(bare))
        subprocess.run(['git', '--git-dir=' + str(bare), 'config', 'core.worktree', str(self.home)], check=True)
        errors = []
        found = list(repos.discover([self.home], [], errors))
        self.assertEqual(found, [(bare, self.home, True)])
        config = self.home / '.config/agentoo/repos.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'repositories': [{'git_dir': str(bare), 'work_tree': str(self.home)}]}))
        code, data, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(len(data['repositories']), 1)
        self.assertTrue(data['repositories'][0]['tracked_only'])

    def test_upstream_fetch_failure_detached_and_conflict(self):
        path = self.repository()
        remote = self.root / 'remote.git'
        self.git(self.root, 'init', '--bare', str(remote))
        self.git(path, 'remote', 'add', 'origin', str(remote))
        self.git(path, 'push', '-u', 'origin', 'main')
        (path / 'ahead').touch()
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-m', 'ahead')
        record = repos.status(path / '.git', path)
        self.assertEqual((record['ahead'], record['behind']), (1, 0))
        peer = self.root / 'peer'
        self.git(self.root, 'clone', '--branch', 'main', str(remote), str(peer))
        (peer / 'incoming').touch()
        self.git(peer, 'add', '.')
        self.git(peer, 'commit', '-m', 'incoming')
        self.git(peer, 'push')
        self.git(path, 'fetch')
        record = repos.status(path / '.git', path)
        self.assertEqual((record['ahead'], record['behind']), (1, 1))
        self.git(path, 'remote', 'set-url', 'origin', str(self.root / 'missing'))
        code, data, stderr = self.invoke('--path=' + str(path), '--fetch')
        self.assertEqual(code, 1)
        self.assertIsNotNone(data['repositories'][0]['fetch_error'])
        self.assertEqual(data['repositories'][0]['ahead'], 1)
        self.assertIn('fetch_error', stderr)
        self.git(path, 'update-ref', '-d', 'refs/remotes/origin/main')
        record = repos.status(path / '.git', path)
        self.assertEqual(record['upstream'], 'origin/main')
        self.assertIsNone(record['ahead'])
        self.git(path, 'checkout', '--detach')
        self.assertEqual(repos.status(path / '.git', path)['branch'], '(detached)')
        self.git(path, 'checkout', '-b', 'other')
        (path / 'file').write_text('other\n')
        self.git(path, 'commit', '-am', 'other')
        self.git(path, 'checkout', 'main')
        (path / 'file').write_text('main\n')
        self.git(path, 'commit', '-am', 'main')
        subprocess.run(['git', '-C', str(path), 'merge', 'other'], capture_output=True)
        self.assertEqual(repos.status(path / '.git', path)['unmerged'], 1)

    def test_errors_are_visible_and_do_not_hide_other_repositories(self):
        path = self.repository()
        code, data, stderr = self.invoke('--path=' + str(path), '--path=' + str(self.root / 'missing'))
        self.assertEqual(code, 1)
        self.assertEqual(len(data['repositories']), 1)
        self.assertTrue(data['errors'])
        self.assertIn('not a directory', stderr)
        with patch.dict(os.environ, {'GIT_DIR': '/nonexistent', 'GIT_WORK_TREE': '/nonexistent'}):
            self.assertEqual(repos.status(path / '.git', path)['branch'], 'main')

    def test_unreadable_metadata_and_invalid_config(self):
        with patch.object(Path, 'open', side_effect=PermissionError):
            with self.assertRaisesRegex(RuntimeError, 'metadata.*permission denied'):
                repos.git(self.root / 'protected.git', Path('/'), 'status')
        config = self.root / 'invalid.json'
        for data in ({'repositories': [{'git_dir': 'relative', 'work_tree': '~'}]},
                     {'exclude': 'not a list'}, {'unknown': []}):
            config.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                repos.load_config(config)


class ColorsTests(unittest.TestCase):
    def test_hex_labels_match_standard_palette_and_truecolor(self):
        for index, rgb in ((16, (0, 0, 0)), (21, (0, 0, 255)),
                           (231, (255, 255, 255)), (232, (8, 8, 8)), (255, (238, 238, 238))):
            self.assertEqual(colors.indexed_rgb(index), rgb)
        self.assertIsNone(colors.indexed_rgb(1))
        output = colors.chart(80)
        self.assertIn('#0000ff', output)
        self.assertIn('#ff8000 → RGB(255, 128, 0)', output)

    def test_all_palette_indices_rgb_endpoints_and_resets(self):
        output = colors.chart(80)
        indices = set(map(int, re.findall(r'\x1b\[0;38;2;(?:0;0;0|255;255;255);48;5;(\d+)m', output)))
        self.assertEqual(indices, set(range(256)))
        for rgb in ('255;0;0', '0;255;0', '0;0;255', '255;255;255', '0;0;0'):
            self.assertIn('\x1b[48;2;' + rgb + 'm', output)
        for line in output.splitlines():
            if '\x1b[' in line:
                self.assertIn(colors.RESET, line)

    def test_chart_rows_fit_normal_and_narrow_terminals(self):
        for width in (9, 20, 40, 80):
            text = re.sub(r'\x1b\[[0-9;]*m', '', colors.chart(width))
            for line in text.splitlines():
                if re.match(r'^\s*\d+(?:/| )', line) or (line and not line.strip()):
                    self.assertLessEqual(len(line), width)

    def test_two_line_swatches_choose_readable_black_or_white(self):
        self.assertEqual(colors.swatch_foreground(16), '255;255;255')
        self.assertEqual(colors.swatch_foreground(21), '255;255;255')
        self.assertEqual(colors.swatch_foreground(226), '0;0;0')
        self.assertEqual(colors.swatch_foreground(231), '0;0;0')
        lines = colors.chart(9).splitlines()
        slot = '\x1b[0;38;2;255;255;255;48;5;21m'
        row = next(i for i, line in enumerate(lines) if line.startswith(slot))
        plain = lambda line: re.sub(r'\x1b\[[0-9;]*m', '', line)
        self.assertEqual(plain(lines[row]).strip(), '21')
        self.assertEqual(plain(lines[row + 1]).strip(), '#0000ff')
        self.assertEqual(len(plain(lines[row + 1])), 9)

    def test_redirect_requires_force_and_help_has_no_escapes(self):
        for args, code in (([], 2), (['--force'], 0), (['--help'], 0)):
            result = subprocess.run([str(BIN / 'agentoo-term-colors'), *args], capture_output=True,
                                    env={**os.environ, 'NO_COLOR': '1'}, text=True)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual('\x1b[' in result.stdout, args == ['--force'])


if __name__ == '__main__':
    unittest.main()
