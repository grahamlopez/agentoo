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
            "SHARE = BIN.parent / 'share/agentoo'", f"SHARE = Path({str(COMMANDS.parent)!r})"))
        for name in ('power', 'fonts', 'permissions', 'backlight', 'screenshot', 'git', 'secrets', 'checkpoint', 'desktop'):
            (self.root / ('agentoo-' + name)).symlink_to(ENTRY.with_name('agentoo-' + name))
        checkpoint = self.root / 'agentoo-checkpoint'
        if checkpoint.is_symlink():
            checkpoint.unlink()
        checkpoint.write_text(ENTRY.with_name('agentoo-checkpoint').read_text().replace(
            '/boot/agentoo/checkpoint.sh', str(ENTRY.parents[3] / 'boot/agentoo/checkpoint.sh')))
        checkpoint.chmod(0o755)
        self.sudo = self.root / 'sudo'
        self.sudo.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 37\n')
        self.sudo.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:{os.environ["PATH"]}')

    def run_cli(self, *args):
        return subprocess.run(['python3', str(self.entry), *args], env=self.env,
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
        executable = self.root / 'agentoo-git'
        executable.unlink()
        executable.write_text(ENTRY.with_name('agentoo-git').read_text().replace(
            '/var/lib/agentoo/repository.git', str(repository)).replace(
            "SHARE = Path(__file__).resolve().parent.parent / 'share/agentoo'",
            f"SHARE = Path({str(COMMANDS.parent)!r})").replace(
            "command = [sys.executable, str(SHARE / 'commands/git-transaction.py'), *command]",
            "command = command"))
        executable.chmod(0o755)
        fake_git = self.root / 'git'
        fake_git.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        fake_git.chmod(0o755)
        result = self.run_cli('git', 'commit', '-m', 'two words; $HOME')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-3:],
                         ['commit', '-m', 'two words; $HOME'])
        self.assertNotIn('requesting sudo', result.stderr)

    def test_completion_usage_matches_actual_help(self):
        paths = [(), ('git',), ('permissions',), ('permissions', 'check'),
                 ('permissions', 'fix'), ('backlight',), ('screenshot',),
                 ('secrets',), ('secrets', 'install'), ('checkpoint',),
                 ('checkpoint', 'create'), ('checkpoint', 'list'),
                 ('checkpoint', 'inspect'), ('checkpoint', 'restore'),
                 ('power',), ('fonts',), ('fonts', 'status'),
                 ('fonts', 'test'), ('fonts', 'set'), ('fonts', 'doctor'),
                 ('desktop',), ('desktop', 'transparency'), ('desktop', 'blur'),
                 *(('desktop', effect) for effect in ('corners', 'gaps', 'borders', 'animations', 'shadows', 'dimming')),
                 ('desktop', 'wallpaper'), ('desktop', 'wallpaper', 'set'),
                 ('desktop', 'wallpaper', 'clear'), ('desktop', 'set'), ('desktop', 'clear'),
                 *(('desktop', feature, action) for feature in ('transparency', 'blur', 'corners', 'gaps', 'borders', 'animations', 'shadows', 'dimming') for action in ('set', 'clear'))]
        for path in paths:
            with self.subTest(path=path):
                help_result = self.run_cli(*path, '--help')
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                completion = self.run_cli('__complete', str(len(path) + 1), *path, '')
                self.assertEqual(completion.returncode, 0, completion.stderr)
                usage = next(line.split('\t')[1] for line in completion.stdout.splitlines()
                             if line.startswith('usage\t'))
                # Python help wraps; checkpoint emits one authoritative usage line.
                expected = ' '.join(help_result.stdout.split('\n\n')[0].split())
                self.assertEqual(usage, expected)

    def test_completion_option_metavars_match_help(self):
        for path, display in [(('secrets', 'install'), '--profile FILE'),
                              (('permissions',), '--root PATH'),
                              (('checkpoint', 'restore'), '--efi-mount PATH')]:
            with self.subTest(path=path):
                result = self.run_cli('__complete', str(len(path) + 1), *path, '')
                self.assertEqual(result.returncode, 0, result.stderr)
                labels = [line.split('\t')[3] for line in result.stdout.splitlines()
                          if line.startswith('option\t')]
                self.assertIn(display, labels)

    def test_operation_requests_sudo_with_exact_arguments(self):
        executable = self.root / 'agentoo-git'
        executable.unlink()
        executable.write_text(ENTRY.with_name('agentoo-git').read_text().replace(
            "SHARE = Path(__file__).resolve().parent.parent / 'share/agentoo'",
            f"SHARE = Path({str(COMMANDS.parent)!r})").replace('os.geteuid() != 0', 'True'))
        executable.chmod(0o755)
        result = self.run_cli('git', 'enable-write', '--no-input')
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-2:], ['enable-write', '--no-input'])
        self.assertEqual(result.stdout.splitlines()[:2], ['-n', '--'])

    def test_check_does_not_accept_fix_override(self):
        for flag in ('--check', '--fix'):
            with self.subTest(flag=flag):
                result = self.run_cli('permissions', 'check', flag)
                self.assertEqual(result.returncode, 2)
                self.assertIn('unrecognized arguments: ' + flag, result.stderr)
                self.assertNotIn('requesting sudo', result.stderr)

    def test_unknown_command_does_not_escalate(self):
        result = self.run_cli('secrets', 'unknown')
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)
        self.assertNotIn('requesting sudo', result.stderr)

    def test_completion_never_dispatches_operations(self):
        commands = self.root / 'completion-commands'
        commands.mkdir()
        (commands / 'cli.py').write_text((COMMANDS / 'cli.py').read_text().replace(
            "HERE.parents[2] / 'bin'", f"Path({str(self.root)!r})"))
        marker = self.root / 'operation-ran'
        for name in ('checkpoint', 'secrets', 'permissions', 'git'):
            executable = self.root / ('agentoo-' + name)
            executable.unlink()
            # Completion imports parsers, whereas execution must never happen.
            executable.write_text(
                'import argparse\nfrom pathlib import Path\n'
                'def build_parser():\n'
                '    parser = argparse.ArgumentParser()\n'
                '    sub = parser.add_subparsers()\n'
                '    for name in ("restore", "install", "fix", "enable-write"):\n'
                '        sub.add_parser(name)\n'
                '    return parser\n'
                f'if __name__ == "__main__": Path({str(marker)!r}).touch()\n')
        self.entry.write_text(self.entry.read_text().replace(
            "SHARE / 'commands/cli.py'", repr(str(commands / 'cli.py'))))
        for words in [('checkpoint', 'restore', 'saved', ''),
                      ('secrets', 'install', ''), ('permissions', 'fix', ''),
                      ('git', 'enable-write', '')]:
            with self.subTest(words=words):
                result = self.run_cli('__complete', str(len(words)), *words)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('requesting sudo', result.stderr)
                self.assertFalse(marker.exists())

    def test_power_direct_and_grouped_help_and_validation(self):
        for args in [('--help',), ('show-all', '--help'), ('--unknown',)]:
            with self.subTest(args=args):
                grouped = self.run_cli('power', *args)
                direct = subprocess.run([str(ENTRY.with_name('agentoo-power')), *args],
                                        capture_output=True, text=True)
                self.assertEqual((grouped.returncode, grouped.stdout, grouped.stderr),
                                 (direct.returncode, direct.stdout, direct.stderr))

    def test_nested_help_and_version(self):
        self.assertEqual(self.run_cli('help', 'fonts', 'doctor').returncode, 0)
        version = self.run_cli('--version')
        self.assertEqual(version.returncode, 0)
        self.assertIn('agentoo', version.stdout)

    def test_migrated_command_direct_grouped_equivalence(self):
        for name, args in [('fonts', ('doctor', '--help')), ('fonts', ('set', '--no-input')),
                           ('permissions', ('check', '--help')), ('permissions', ('check', '--fix'))]:
            with self.subTest(name=name, args=args):
                grouped = self.run_cli(name, *args)
                direct = subprocess.run([str(ENTRY.with_name('agentoo-' + name)), *args],
                                        capture_output=True, text=True)
                self.assertEqual((grouped.returncode, grouped.stdout, grouped.stderr),
                                 (direct.returncode, direct.stdout, direct.stderr))

    def test_catalog_discovered_direct_and_grouped_help(self):
        catalog = self.run_cli('__complete', '1', '')
        self.assertEqual(catalog.returncode, 0, catalog.stderr)
        names = [line.split('\t')[1] for line in catalog.stdout.splitlines()
                 if line.startswith('command\t') and line.split('\t')[1] != 'help']
        self.assertTrue(names)
        for name in names:
            with self.subTest(name=name):
                grouped = self.run_cli(name, '--help')
                direct = subprocess.run([str(self.root / ('agentoo-' + name)), '--help'],
                                        capture_output=True, text=True, env=self.env)
                self.assertEqual(grouped.returncode, 0, grouped.stderr)
                self.assertEqual((grouped.returncode, grouped.stdout, grouped.stderr),
                                 (direct.returncode, direct.stdout, direct.stderr))

    def test_root_version_completion_and_typo_suggestion(self):
        result = self.run_cli('__complete', '1', '--v')
        self.assertIn('option\t--version\t', result.stdout)
        result = self.run_cli('powre')
        self.assertEqual(result.returncode, 2)
        self.assertIn("Did you mean 'power'?", result.stderr)
