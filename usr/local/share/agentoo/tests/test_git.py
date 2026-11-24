"""Git configuration changes use disposable repositories, without networking."""
from contextlib import redirect_stderr
from importlib.machinery import SourceFileLoader
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-git'
spec = importlib.util.spec_from_loader('agentoo_git', SourceFileLoader('agentoo_git', str(ENTRY)))
git = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git)

WRAP_SCRIPT = Path(__file__).resolve().parents[1] / 'lib/git_wrap_commit_msg.py'
wrap_spec = importlib.util.spec_from_file_location('git_wrap_commit_msg', WRAP_SCRIPT)
wrap_commit_msg = importlib.util.module_from_spec(wrap_spec)
wrap_spec.loader.exec_module(wrap_commit_msg)


class GitTests(unittest.TestCase):
    def test_enable_write_replaces_https_push_override_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null'):
            root = Path(temporary)
            repository = root / 'repository.git'
            subprocess.run(['git', 'init', '--bare', str(repository)], check=True, capture_output=True)
            command = ['git', f'--git-dir={repository}']
            https = 'https://github.com/grahamlopez/agentoo.git'
            subprocess.run([*command, 'remote', 'add', 'origin', https], check=True)
            subprocess.run([*command, 'config', 'remote.origin.pushurl', https], check=True)
            with patch.object(git, 'SYSTEM_GIT_DIR', repository), \
                 patch.object(git, 'SYSTEM_WORK_TREE', root), \
                 patch.object(git.os, 'geteuid', return_value=0), \
                 patch.object(git.sys, 'argv', ['agentoo-git', 'enable-write']), \
                 redirect_stderr(io.StringIO()):
                for _ in range(2):
                    self.assertEqual(git.main(), 0)
                    for options in ([], ['--push']):
                        result = subprocess.run([*command, 'remote', 'get-url', *options, 'origin'],
                                                check=True, text=True, capture_output=True)
                        self.assertEqual(result.stdout.strip(), git.SSH_REMOTE)

    def _init_repo_with_commit(self, root):
        repository = root / 'repository.git'
        work_tree = root / 'work'
        work_tree.mkdir()
        env = {
            **os.environ,
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_AUTHOR_NAME': 'Test',
            'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 'test@example.invalid',
        }
        subprocess.run(['git', 'init', '--bare', '-b', 'main', str(repository)],
                       check=True, env=env, capture_output=True)
        base = ['git', f'--git-dir={repository}', f'--work-tree={work_tree}']
        subprocess.run([*base, 'config', 'core.bare', 'false'], check=True, env=env)
        subprocess.run([*base, 'config', 'core.worktree', str(work_tree)], check=True, env=env)
        (work_tree / 'file.txt').write_text('hello\n')
        subprocess.run([*base, 'add', 'file.txt'], check=True, env=env)
        subprocess.run([*base, 'commit', '-m', 'Initial commit'], check=True, env=env, capture_output=True)
        return repository, work_tree, env

    def test_non_root_allows_read_only_commands_and_fails_fast_on_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, work_tree, env = self._init_repo_with_commit(root)
            for alias, target in [('l', 'log --oneline'), ('st', 'status'), ('br', 'branch'),
                                  ('sh', 'remote show origin'), ('ci', 'commit'), ('co', 'checkout'),
                                  ('please', 'push --force-with-lease'), ('shell', '!echo hi')]:
                subprocess.run(['git', f'--git-dir={repository}', 'config', f'alias.{alias}', target],
                               check=True, env=env)
            # Simulate a root-owned read-only system repository.
            os.chmod(repository, 0o555)
            try:
                with patch.dict(os.environ, env, clear=True), \
                     patch.object(git, 'SYSTEM_GIT_DIR', repository), \
                     patch.object(git, 'SYSTEM_WORK_TREE', work_tree), \
                     patch.object(git.os, 'geteuid', return_value=1000):
                    for read_args in [
                        ['log', '-1'], ['--no-pager', 'log', '-1'], ['-c', 'color.ui=false', 'show', 'HEAD'],
                        ['status'], ['diff'], ['branch'], ['branch', '-a'], ['branch', '-l', 'main'],
                        ['tag'], ['tag', '-l'], ['remote', '-v'], ['remote', 'get-url', 'origin'],
                        ['config', '--list'], ['config', '--get', 'core.bare'],
                        ['l', '-1'], ['st'], ['br', '-v'], ['sh'],
                        ['commit', '--help'], ['--version'],
                    ]:
                        with self.subTest(read_args=read_args):
                            command = git.git_command(read_args)
                            self.assertEqual(command[0], 'git')
                            self.assertEqual(command[-len(read_args):], read_args)
                    for write_args in [
                        ['pull'], ['fetch'], ['push'], ['commit', '-m', 'x'], ['add', '.'],
                        ['checkout', 'main'], ['switch', 'main'], ['reset', '--hard'], ['restore', '.'],
                        ['branch', 'topic'], ['branch', '-d', 'main'], ['branch', '-vD', 'main'],
                        ['tag', 'v1'], ['config', 'user.name', 'Test'], ['config', '--unset', 'core.bare'],
                        ['remote', 'set-url', 'origin', 'https://example.invalid/repo.git'],
                        ['ci', '-m', 'x'], ['co', 'main'], ['please'], ['shell'], ['unknown-cmd'],
                    ]:
                        with self.subTest(write_args=write_args):
                            with self.assertRaises(RuntimeError) as context:
                                git.git_command(write_args)
                            self.assertIn('sudo agentoo git', str(context.exception))
            finally:
                os.chmod(repository, 0o755)

    def test_unreadable_ref_or_index_reports_sudo_instead_of_broken_branch(self):
        if os.geteuid() == 0:
            self.skipTest('root bypasses mode 0000 permission checks')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, work_tree, env = self._init_repo_with_commit(root)
            ref = repository / 'refs/heads/main'
            index = repository / 'index'
            for restricted in (ref, index):
                with self.subTest(restricted=restricted.name):
                    os.chmod(restricted, 0o000)
                    try:
                        with patch.dict(os.environ, env, clear=True), \
                             patch.object(git, 'SYSTEM_GIT_DIR', repository), \
                             patch.object(git, 'SYSTEM_WORK_TREE', work_tree):
                            with self.assertRaises(RuntimeError) as context:
                                git.git_command(['log', '-1'])
                            message = str(context.exception)
                            self.assertIn(str(restricted), message)
                            self.assertIn('sudo agentoo git', message)
                    finally:
                        os.chmod(restricted, 0o644)

    def test_system_repo_config_hooks_activate_only_for_system_gitdir(self):
        repo_root = Path(__file__).resolve().parents[5]
        system_cfg = repo_root / 'etc/agentoo/gitconfig'
        user_cfg = repo_root / 'etc/agentoo/gitconfig-user'
        user_ignore = repo_root / 'etc/agentoo/gitignore-user'
        global_template = (repo_root / 'etc/gitconfig').read_text()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, work_tree, env = self._init_repo_with_commit(root)
            cfg = root / 'gitconfig'
            cfg.write_text(
                global_template.replace(
                    '/var/lib/agentoo/repository.git', str(repository)
                ).replace(
                    'path = /etc/agentoo/gitconfig\n', f'path = {system_cfg}\n'
                ).replace(
                    '/etc/agentoo/gitconfig-user', str(user_cfg)
                ).replace(
                    '/etc/agentoo/gitignore-user', str(user_ignore)
                )
            )
            env = {**env, 'GIT_CONFIG_GLOBAL': str(cfg)}
            base = ['git', f'--git-dir={repository}', f'--work-tree={work_tree}']
            shared = subprocess.run([*base, 'config', '--get', 'core.sharedRepository'],
                                    check=True, env=env, text=True, capture_output=True).stdout.strip()
            self.assertEqual(shared, '0644')
            sys_excludes = subprocess.run([*base, 'config', '--get', 'core.excludesFile'],
                                          check=True, env=env, text=True, capture_output=True).stdout.strip()
            self.assertEqual(sys_excludes, '/etc/agentoo/gitignore')
            alias_st = subprocess.run([*base, 'config', '--get', 'alias.st'],
                                      check=True, env=env, text=True, capture_output=True).stdout.strip()
            self.assertEqual(alias_st, 'status')
            for event, expected in [
                ('pre-commit', 'agentoo-permissions-check'),
                ('post-checkout', 'agentoo-permissions-fix'),
                ('post-merge', 'agentoo-permissions-fix'),
                ('post-rewrite', 'agentoo-permissions-fix'),
                ('commit-msg', 'wrap-commit-msg'),
            ]:
                with self.subTest(event=event):
                    listed = subprocess.run([*base, 'hook', 'list', event],
                                            check=True, env=env, text=True, capture_output=True).stdout.splitlines()
                    self.assertIn(expected, listed)

            # Repo-local override disables a config hook cleanly.
            subprocess.run([*base, 'config', 'hook.agentoo-permissions-check.enabled', 'false'],
                           check=True, env=env)
            disabled = subprocess.run([*base, 'hook', 'list', 'pre-commit'],
                                      env=env, text=True, capture_output=True)
            self.assertIn('disabled\tagentoo-permissions-check', disabled.stdout.splitlines())

            # Dev clones get wrap-commit-msg, not system-repo permission hooks.
            dev = root / 'dev'
            subprocess.run(['git', 'init', '-q', str(dev)], check=True, env=env)
            dev_pre = subprocess.run(['git', '-C', str(dev), 'hook', 'list', 'pre-commit'],
                                     env=env, text=True, capture_output=True)
            self.assertNotIn('agentoo-permissions-check', dev_pre.stdout)
            dev_msg = subprocess.run(['git', '-C', str(dev), 'hook', 'list', 'commit-msg'],
                                     check=True, env=env, text=True, capture_output=True).stdout.splitlines()
            self.assertIn('wrap-commit-msg', dev_msg)


class WrapCommitMessageTests(unittest.TestCase):
    def test_wraps_body_and_preserves_subject_lists_code_trailers_and_scissors(self):
        long_subject = 'Subject line intentionally left untouched even when it exceeds eighty characters in length'
        long_url = 'https://example.invalid/' + 'a' * 90
        message = (
            f'{long_subject}\n'
            '\n'
            'This is a very long body paragraph written by an agent that goes well past eighty columns without any manual line breaks at all.\n'
            '\n'
            '- A long bullet list item that should wrap cleanly with hanging indentation aligned under the start of the text.\n'
            '  - A nested bullet item that is also quite long and continues onto\n'
            '    a four-space-indented continuation line.\n'
            '\n'
            f'Reference: {long_url}\n'
            '\n'
            '```sh\n'
            'echo "this fenced code line is intentionally longer than eighty characters and must stay intact"\n'
            '```\n'
            '\n'
            '    indented_code_line = "also intentionally longer than eighty characters and must stay intact"\n'
            '\n'
            'Signed-off-by: Very Long Name With Extra Details <very-long-email-address-that-exceeds-eighty-columns@example.invalid>\n'
            '# ------------------------ >8 ------------------------\n'
            '# diff line that is intentionally longer than eighty characters and must stay completely verbatim\n'
        )

        wrapped = wrap_commit_msg.wrap_commit_message(message, width=80)
        lines = wrapped.splitlines()

        self.assertEqual(lines[0], long_subject)
        # Prose paragraph wrapped to <= 80 columns
        self.assertIn(
            'This is a very long body paragraph written by an agent that goes well past\n'
            'eighty columns without any manual line breaks at all.',
            wrapped,
        )
        # Bullet list hanging indent preserved
        self.assertIn(
            '- A long bullet list item that should wrap cleanly with hanging indentation\n'
            '  aligned under the start of the text.',
            wrapped,
        )
        self.assertIn(
            '  - A nested bullet item that is also quite long and continues onto a\n'
            '    four-space-indented continuation line.',
            wrapped,
        )
        # Long URL, fenced code, indented code, trailer, and scissors preserved intact
        self.assertIn(long_url, lines)
        self.assertIn(
            'echo "this fenced code line is intentionally longer than eighty characters and must stay intact"',
            lines,
        )
        self.assertIn(
            '    indented_code_line = "also intentionally longer than eighty characters and must stay intact"',
            lines,
        )
        self.assertIn(
            'Signed-off-by: Very Long Name With Extra Details <very-long-email-address-that-exceeds-eighty-columns@example.invalid>',
            lines,
        )
        self.assertIn(
            '# diff line that is intentionally longer than eighty characters and must stay completely verbatim',
            lines,
        )

    def test_layered_git_hook_wraps_commit_and_can_be_disabled_locally(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            global_cfg = root / 'gitconfig'
            global_cfg.write_text(
                '[hook "wrap-commit-msg"]\n'
                '    event = commit-msg\n'
                f'    command = {WRAP_SCRIPT}\n'
            )
            env = {
                **os.environ,
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_CONFIG_GLOBAL': str(global_cfg),
                'GIT_AUTHOR_NAME': 'Test',
                'GIT_AUTHOR_EMAIL': 'test@example.invalid',
                'GIT_COMMITTER_NAME': 'Test',
                'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            }
            repo = root / 'repo'
            subprocess.run(['git', 'init', str(repo)], check=True, env=env, capture_output=True)
            (repo / 'a.txt').write_text('one\n')
            subprocess.run(['git', '-C', str(repo), 'add', 'a.txt'], check=True, env=env)
            long_body = 'word ' * 25
            subprocess.run(
                ['git', '-C', str(repo), 'commit', '-m', 'First commit', '-m', long_body.strip()],
                check=True, env=env, capture_output=True,
            )
            body = subprocess.run(
                ['git', '-C', str(repo), 'log', '-1', '--format=%b'],
                check=True, env=env, text=True, capture_output=True,
            ).stdout.strip()
            self.assertTrue(all(len(line) <= 80 for line in body.splitlines()), body)
            self.assertGreater(len(body.splitlines()), 1)

            # Repo-local override disables the layered hook cleanly.
            subprocess.run(
                ['git', '-C', str(repo), 'config', 'hook.wrap-commit-msg.enabled', 'false'],
                check=True, env=env,
            )
            (repo / 'a.txt').write_text('two\n')
            subprocess.run(['git', '-C', str(repo), 'add', 'a.txt'], check=True, env=env)
            subprocess.run(
                ['git', '-C', str(repo), 'commit', '-m', 'Second commit', '-m', long_body.strip()],
                check=True, env=env, capture_output=True,
            )
            unwrapped_body = subprocess.run(
                ['git', '-C', str(repo), 'log', '-1', '--format=%b'],
                check=True, env=env, text=True, capture_output=True,
            ).stdout.strip()
            self.assertEqual(unwrapped_body, long_body.strip())

    def test_rejects_overlong_subject_and_exempts_git_generated_subjects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            global_cfg = root / 'gitconfig'
            global_cfg.write_text(
                '[hook "wrap-commit-msg"]\n'
                '    event = commit-msg\n'
                f'    command = {WRAP_SCRIPT}\n'
            )
            env = {
                **os.environ,
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_CONFIG_GLOBAL': str(global_cfg),
                'GIT_AUTHOR_NAME': 'Test',
                'GIT_AUTHOR_EMAIL': 'test@example.invalid',
                'GIT_COMMITTER_NAME': 'Test',
                'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            }
            repo = root / 'repo'
            subprocess.run(['git', 'init', str(repo)], check=True, env=env, capture_output=True)
            (repo / 'a.txt').write_text('one\n')
            subprocess.run(['git', '-C', str(repo), 'add', 'a.txt'], check=True, env=env)

            long_subject = 'x' * 81
            rejected = subprocess.run(
                ['git', '-C', str(repo), 'commit', '-m', long_subject],
                env=env, text=True, capture_output=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('subject line is 81 characters (max 80)', rejected.stderr)

            # Git-generated subjects (Merge / Revert / fixup!) are exempt.
            for exempt in (
                'Merge branch ' + 'a' * 75,
                'Revert "' + 'b' * 78 + '"',
                'fixup! ' + 'c' * 80,
            ):
                self.assertIsNone(wrap_commit_msg.subject_error(exempt, max_width=80))

            # Exactly 80 characters succeeds.
            subprocess.run(
                ['git', '-C', str(repo), 'commit', '-m', 'x' * 80],
                check=True, env=env, capture_output=True,
            )


if __name__ == '__main__':
    unittest.main()
