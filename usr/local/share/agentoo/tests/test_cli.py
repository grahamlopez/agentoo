"""Exercise dispatch without sudo authorization or touching system state."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo'
COMMANDS = Path(__file__).resolve().parents[1] / 'commands'


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = self.root / 'agentoo'
        self.entry.write_text(ENTRY.read_text().replace(
            '/usr/local/share/agentoo/commands', str(COMMANDS)).replace(
            '/boot/agentoo/checkpoint.sh', str(
                ENTRY.parents[3] / 'boot/agentoo/checkpoint.sh')))
        self.sudo = self.root / 'sudo'
        self.sudo.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 37\n')
        self.sudo.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:{os.environ["PATH"]}')

    def run_cli(self, *args):
        return subprocess.run(['bash', str(self.entry), *args], env=self.env,
                              text=True, capture_output=True)

    def test_help_never_requests_sudo(self):
        for args in [[], ['help'], ['help', 'git'], ['checkpoint', '--help'],
                     ['checkpoint', 'restore', '--help'], ['permissions', 'fix', '--help'],
                     ['permissions', 'check', '--help'], ['help', 'permissions'],
                     ['secrets', 'install', '--help'], ['help', 'power'],
                     ['help', 'backlight'], ['help', 'screenshot']]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('requesting sudo', result.stderr)
                self.assertIn('usage:', result.stdout.lower())

    def test_git_arguments_run_without_sudo(self):
        commands = self.root / 'commands'
        commands.mkdir()
        repository = self.root / 'repository.git'
        repository.mkdir()
        (repository / 'HEAD').write_text('ref: refs/heads/main\n')
        (commands / 'git').write_text((COMMANDS / 'git').read_text().replace(
            '/var/lib/agentoo/repository.git', str(repository)))
        (commands / 'require-root').write_text((COMMANDS / 'require-root').read_text())
        # Root-run tests exercise wrapper forwarding without desktop IPC or
        # permission repair on the test machine.
        (commands / 'git-transaction.py').write_text(
            'import os, sys\nos.execvp(sys.argv[1], sys.argv[1:])\n')
        self.entry.write_text(self.entry.read_text().replace(str(COMMANDS), str(commands)))
        fake_git = self.root / 'git'
        fake_git.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        fake_git.chmod(0o755)
        result = self.run_cli('git', 'commit', '-m', 'two words; $HOME')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-3:],
                         ['commit', '-m', 'two words; $HOME'])
        self.assertNotIn('requesting sudo', result.stderr)

    def test_operation_requests_sudo_with_exact_arguments(self):
        fake_id = self.root / 'id'
        fake_id.write_text('#!/bin/sh\necho 1000\n')
        fake_id.chmod(0o755)
        result = self.run_cli('git', 'enable-write')
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ['--', 'bash', str(COMMANDS / 'git'), 'enable-write'])

    def test_check_does_not_accept_fix_override(self):
        result = subprocess.run(
            ['python3', str(COMMANDS / 'permissions.py'), '--check', '--fix'],
            text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not allowed with argument', result.stderr)

    def test_unknown_command_does_not_escalate(self):
        result = self.run_cli('secrets', 'unknown')
        self.assertEqual(result.returncode, 2)
        self.assertIn('unknown secrets command', result.stderr)
        self.assertNotIn('requesting sudo', result.stderr)
