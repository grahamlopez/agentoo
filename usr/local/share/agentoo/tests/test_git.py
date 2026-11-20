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
