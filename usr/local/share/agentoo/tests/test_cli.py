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
                     ['secrets', 'install', '--help']]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('requesting sudo', result.stderr)
                self.assertIn('Usage:', result.stdout)

    @unittest.skipIf(os.geteuid() == 0, 'requires an ordinary user')
    def test_privileged_commands_reenter_with_exact_arguments(self):
        for args in [('git', 'commit', '-m', 'two words; $HOME'),
                     ('checkpoint', 'list'), ('permissions', 'fix'),
                     ('permissions', 'check'),
                     ('permissions', 'check', '--root', '/a b'),
                     ('secrets', 'install', '--profile', '/a b', '--user', 'graham', 'ssh')]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 37)
                self.assertEqual(result.stdout.splitlines(),
                                 ['--', '/usr/local/bin/agentoo', *args])
                self.assertIn('requires root; requesting sudo authorization.', result.stderr)

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
