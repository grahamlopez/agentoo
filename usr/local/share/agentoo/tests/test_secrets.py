"""Secrets tests use fake provider output and disposable files only."""
import contextlib
import io
import json
import os
from pathlib import Path
import pwd
import runpy
import tempfile
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-secrets'
MODULE = runpy.run_path(str(ENTRY))


class SecretsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'profile'
        self.destination = self.root / 'installed'
        self.profile.write_text(f'ssh user {self.destination} field pass://vault/ssh/private key\n'
                                f'github root {self.root}/git-secret github pass://vault/git\n')
        self.user = pwd.getpwuid(os.getuid()).pw_name
        self.args = ['install', '--profile=' + str(self.profile), '--user=' + self.user]
        self.log = self.root / 'calls'
        provider = self.root / 'pass-cli'
        provider.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write(json.dumps({'args': sys.argv[1:], 'proton': {k:v for k,v in os.environ.items() if k.startswith('PROTON_PASS_')}, 'stdin_eof': not sys.stdin.read()}) + '\\n')
if os.environ.get('FAKE_FAIL'):
    print('FAKE_SECRET_MUST_NOT_LEAK', file=sys.stderr)
    sys.exit(1)
if sys.argv[1] == 'item':
    print('fake secret value')
''')
        provider.chmod(0o755)
        self.env = patch.dict(os.environ, PATH=str(self.root) + ':' + os.environ['PATH'],
                              FAKE_LOG=str(self.log), PROTON_PASS_PASSWORD='inherited-fake',
                              PROTON_PASS_PERSONAL_ACCESS_TOKEN='inherited-fake',
                              PROTON_PASS_ENVIRONMENT='inherited-fake')
        self.env.start()
        self.addCleanup(self.env.stop)

    def main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = MODULE['main'](self.args + args)
        return status, out.getvalue(), err.getvalue()

    def test_dry_run_equals_and_interleaved_options_no_effects(self):
        with patch.object(MODULE['os'], 'execvp', side_effect=AssertionError('sudo')):
            status, out, err = self.main(['ssh', '--dry-run', 'github', '--no-input'])
        self.assertEqual(status, 0, err)
        self.assertEqual(out, '')
        self.assertIn(str(self.destination), err)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.destination.exists())

    def test_unknown_category_and_invalid_template_fail_before_effects(self):
        for args in (['ssh', 'unknown', '--yes'], ['ssh', '--no-input']):
            status, out, err = self.main(args)
            self.assertEqual(status, 1)
            self.assertFalse(self.log.exists())
        self.profile.write_text(f'ssh user {self.destination} template /nonexistent-agentoo-template\n')
        self.assertEqual(self.main(['ssh', '--dry-run'])[0], 1)

    def test_removed_session_option_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            self.main(['ssh', '--session-dir', str(self.root)])
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(self.log.exists())

    def test_provider_environment_and_diagnostics(self):
        env = MODULE['proton_environment'](self.root / 'session')
        self.assertEqual({key for key in env if key.startswith('PROTON_PASS_')},
                         {'PROTON_PASS_SESSION_DIR', 'PROTON_PASS_KEY_PROVIDER', 'PROTON_PASS_NO_UPDATE_CHECK'})
        self.assertEqual(env['PROTON_PASS_KEY_PROVIDER'], 'fs')
        self.assertEqual(env['PROTON_PASS_SESSION_DIR'], str(self.root / 'session'))
        with patch.dict(env, FAKE_FAIL='1'):
            with self.assertRaisesRegex(ValueError, 'Proton Pass item failed') as result:
                MODULE['run_proton'](['item', 'view', 'pass://fake'], env)
        self.assertNotIn('FAKE_SECRET_MUST_NOT_LEAK', str(result.exception))
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(calls[0]['stdin_eof'])
        self.assertFalse(self.destination.exists())

    def test_default_session_cleanup_and_interactive_login(self):
        work = self.root / 'work'
        work.mkdir()
        calls = []
        def provider(args, env, **kwargs):
            calls.append((args, kwargs))
            if args[0] == 'item':
                raise ValueError('retrieval failed')
        with patch.object(MODULE['os'], 'geteuid', return_value=0), \
             patch.object(MODULE['tempfile'], 'mkdtemp', return_value=str(work)), \
             patch.object(MODULE['sys'].stdin, 'isatty', return_value=True), \
             patch.dict(MODULE['main'].__globals__, run_proton=provider):
            status, _, _ = self.main(['ssh', '--yes'])
        self.assertEqual(status, 1)
        self.assertEqual([call[0][0] for call in calls], ['login', 'item', 'logout'])
        self.assertTrue(calls[0][1]['interactive'])
        self.assertEqual(calls[-1][1]['timeout'], 10)
        self.assertFalse(work.exists())

    def test_owned_session_success_and_cancellation_cleanup(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                work = self.root / 'work'
                work.mkdir()
                calls, writes = [], []
                def provider(args, env, **kwargs):
                    calls.append((args, env.copy(), kwargs))
                    if args[0] == 'item':
                        if cancelled:
                            raise KeyboardInterrupt()
                        return b'fake secret bytes'
                def install(destination, content, uid, gid):
                    writes.append((destination, content, uid, gid))
                with patch.object(MODULE['os'], 'geteuid', return_value=0), \
                     patch.object(MODULE['tempfile'], 'mkdtemp', return_value=str(work)) as temporary, \
                     patch.object(MODULE['sys'].stdin, 'isatty', return_value=True), \
                     patch.dict(MODULE['main'].__globals__, run_proton=provider, install_file=install):
                    status, out, _ = self.main(['ssh', '--yes'])
                self.assertEqual(status, 130 if cancelled else 0)
                self.assertEqual(out, '')
                temporary.assert_called_once_with(prefix='agentoo-secrets.', dir='/run')
                self.assertEqual([call[0] for call in calls],
                                 [['login', '--interactive'], ['item', 'view', 'pass://vault/ssh/private key'], ['logout']])
                self.assertEqual(calls[0][1]['PROTON_PASS_SESSION_DIR'], str(work / 'session'))
                self.assertTrue(calls[0][2]['interactive'])
                self.assertEqual(calls[-1][2]['timeout'], 10)
                self.assertFalse(work.exists())
                self.assertEqual(len(writes), 0 if cancelled else 1)
                if writes:
                    self.assertEqual(writes[0], (str(self.destination), b'fake secret bytes',
                                                pwd.getpwnam(self.user).pw_uid, pwd.getpwnam(self.user).pw_gid))

    def test_home_and_github_configuration_preserved(self):
        self.profile.write_text('ssh user HOME/.ssh/id_test field pass://vault/ssh/private key\n')
        user, rows = MODULE['read_plan'](self.profile, self.user, ['ssh'])
        self.assertEqual(rows[0][2], str(Path(user.pw_dir) / '.ssh/id_test'))
        calls, writes = [], []
        def provider(args, env, **kwargs):
            return b'username\xff\n' if args[-1].endswith('/username') else b'password\xfe\n'
        def install(destination, content, uid, gid):
            writes.append((destination, content, uid, gid))
        def git(command, **kwargs):
            calls.append(command)
        user = pwd.getpwnam(self.user)
        rows = [('github', 'root', str(self.destination), 'github', 'pass://vault/git')]
        work = self.root / 'work'
        work.mkdir()
        with patch.dict(MODULE['perform'].__globals__, run_proton=provider, install_file=install), \
             patch.object(MODULE['tempfile'], 'mkdtemp', return_value=str(work)), \
             patch.object(MODULE['subprocess'], 'run', git), \
             contextlib.redirect_stderr(io.StringIO()):
            MODULE['perform'](user, rows)
        self.assertEqual(writes[0][1], b'https://username%FF:password%FE@github.com/grahamlopez/agentoo.git\n')
        self.assertEqual(writes[0][2:], (0, 0))
        self.assertEqual(calls[-1][-2:], ['remote.origin.pushurl', 'https://github.com/grahamlopez/agentoo.git'])
        self.assertEqual(calls[0][-2:], ['credential.https://github.com/grahamlopez/agentoo.git.useHttpPath', 'true'])
        self.assertEqual(calls[1][-3:], ['--replace-all', 'credential.https://github.com/grahamlopez/agentoo.git.helper', ''])

    def test_root_only_input_reexecutes_without_prompt_when_requested(self):
        commands = []
        def denied(*args):
            raise PermissionError('private profile')
        def execute(command, arguments):
            commands.append(arguments)
            raise SystemExit(37)
        with patch.dict(MODULE['main'].__globals__, read_plan=denied), \
             patch.object(MODULE['os'], 'geteuid', return_value=1000), \
             patch.object(MODULE['os'], 'execvp', execute):
            with self.assertRaises(SystemExit):
                self.main(['ssh', '--dry-run', '--no-input'])
        self.assertEqual(commands[0][:3], ['sudo', '-n', '--'])
        self.assertEqual(commands[0][-3:], ['ssh', '--dry-run', '--no-input'])

    def test_no_input_install_rejected_before_read_sudo_or_provider(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('must reject noninteractive installation before effects')
        with patch.dict(MODULE['main'].__globals__, read_plan=forbidden, run_proton=forbidden), \
             patch.object(MODULE['os'], 'execvp', forbidden):
            for options in (['ssh', '--no-input'], ['ssh', '--no-input', '--yes']):
                status, _, err = self.main(options)
                self.assertEqual(status, 1)
                self.assertIn('supports only --dry-run', err)
                self.assertNotIn('--session-dir', err)

    def test_nonterminal_install_rejected_before_effects(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('must reject piped installation before effects')
        with patch.object(MODULE['sys'].stdin, 'isatty', return_value=False), \
             patch.dict(MODULE['main'].__globals__, read_plan=forbidden, run_proton=forbidden), \
             patch.object(MODULE['os'], 'execvp', forbidden):
            status, _, err = self.main(['ssh', '--yes'])
        self.assertEqual(status, 1)
        self.assertIn('needs a terminal', err)
        self.assertNotIn('--session-dir', err)
