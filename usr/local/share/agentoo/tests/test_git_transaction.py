"""Verify deployment ordering and recovery without touching the desktop."""
import contextlib
import importlib.util
import io
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'lib/git_transaction.py'
SPEC = importlib.util.spec_from_file_location('git_transaction', PATH)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class GitTransactionTest(unittest.TestCase):
    def test_hooks_use_canonical_permission_operations(self):
        hooks = PATH.parent.parent / 'git-hooks'
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            git = directory / 'git'
            git.write_text('#!/bin/sh\ncase "$2" in\n'
                           '  --show-toplevel) echo /;;\n'
                           '  --absolute-git-dir) echo /var/lib/agentoo/repository.git;;\n'
                           '  *) exit 1;;\nesac\n')
            git.chmod(0o755)
            log = directory / 'arguments'
            agentoo = directory / 'agentoo'
            agentoo.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOOK_TEST_LOG"\n'
                               'exit "${HOOK_TEST_STATUS:-0}"\n')
            agentoo.chmod(0o755)
            env = dict(os.environ, PATH=f'{directory}:' + os.environ['PATH'], HOOK_TEST_LOG=str(log))
            for name in ('pre-commit', 'post-checkout', 'post-merge', 'post-rewrite'):
                for uid in (0, 1000):
                    with self.subTest(hook=name, uid=uid):
                        hook = directory / name
                        # Exercise both root/nonroot branches without privileges.
                        hook.write_text((hooks / name).read_text().replace(
                            '/usr/local/bin/agentoo', str(agentoo)).replace('$EUID == 0', f'{uid} == 0'))
                        result = subprocess.run(['bash', str(hook)], env=env, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        operation = 'fix' if uid == 0 and name != 'pre-commit' else 'check'
                        self.assertEqual(log.read_text().splitlines(), ['permissions', operation])
                result = subprocess.run(['bash', str(hook)], env=dict(env, HOOK_TEST_STATUS='1'),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn('permissions need attention', result.stderr)

    def test_wrapper_routes_writes_aliases_and_global_options_through_guard(self):
        command = PATH.parents[3] / 'bin/agentoo-git'
        spec = importlib.util.spec_from_loader('agentoo_git_wrapper',
                    SourceFileLoader('agentoo_git_wrapper', str(command)))
        wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrapper)
        with patch.object(wrapper.os, 'geteuid', return_value=0):
            for args, guarded in [(['status'], False), (['push'], False),
                                  (['pull'], True), (['restore', '.'], True),
                                  (['custom-alias'], True),
                                  (['-c', 'color.ui=false', 'pull'], True)]:
                with self.subTest(args=args):
                    result = wrapper.git_command(args)
                    self.assertEqual(str(PATH) in result, guarded)
                    self.assertEqual(result[-len(args):], args)

    def run_transaction(self, git_status=0, repair_status=0, previous=False,
                        pause_error=False, interrupt=False, restore_error=False):
        events = []
        def ipc(runtime, signature, *args):
            events.append(('ipc', signature, *args))
            if 'getoption' in args:
                return '{"bool":' + str(previous).lower() + '}'
            if args[0] == 'eval':
                if pause_error and len(events) == 2:
                    raise RuntimeError('pause rejected')
                if restore_error and 'false' in args[1]:
                    raise RuntimeError('restore rejected')
            return 'ok'
        def run(command):
            events.append(('run', *command))
            if command[0] == 'git':
                if interrupt:
                    raise SystemExit(143)
                return subprocess.CompletedProcess(command, git_status)
            return subprocess.CompletedProcess(command, repair_status)
        with patch.object(GUARD, 'instances', return_value=[(Path('/run/user/1000'), 'session')]), \
             patch.object(GUARD, 'ipc', side_effect=ipc), \
             patch.object(GUARD.subprocess, 'run', side_effect=run), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            try:
                result = GUARD.transaction(['git', 'pull'])
            except (RuntimeError, SystemExit) as error:
                result = error
        return result, events, errors.getvalue()

    def test_success_orders_pause_git_repair_reload_restore(self):
        status, events, errors = self.run_transaction()
        self.assertEqual(status, 0)
        self.assertEqual(errors, '')
        self.assertEqual([e[0] for e in events], ['ipc', 'ipc', 'run', 'run', 'ipc', 'ipc'])
        self.assertIn('true', events[1][-1])
        self.assertEqual(events[2], ('run', 'git', 'pull'))
        self.assertEqual(events[3][-2:], ('permissions', 'fix'))
        self.assertEqual(events[4][-1], 'reload')
        self.assertIn('false', events[5][-1])

    def test_git_failure_still_repairs_and_restores(self):
        status, events, _ = self.run_transaction(git_status=7)
        self.assertEqual(status, 7)
        self.assertEqual(events[-2][-1], 'reload')
        self.assertIn('false', events[-1][-1])

    def test_repair_failure_skips_reload_but_restores(self):
        status, events, errors = self.run_transaction(repair_status=1)
        self.assertEqual(status, 1)
        self.assertFalse(any(e[-1] == 'reload' for e in events))
        self.assertIn('false', events[-1][-1])
        self.assertIn('permission repair failed', errors)

    def test_previously_disabled_autoreload_stays_disabled(self):
        status, events, _ = self.run_transaction(previous=True)
        self.assertEqual(status, 0)
        self.assertIn('true', events[-1][-1])

    def test_failed_pause_aborts_before_git_and_attempts_restore(self):
        result, events, _ = self.run_transaction(pause_error=True)
        self.assertIsInstance(result, RuntimeError)
        self.assertFalse(any(e[0] == 'run' for e in events))
        self.assertIn('false', events[-1][-1])

    def test_interrupt_repairs_and_restores(self):
        result, events, _ = self.run_transaction(interrupt=True)
        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 143)
        self.assertEqual(events[-3][-2:], ('permissions', 'fix'))
        self.assertIn('false', events[-1][-1])

    def test_restore_failure_is_visible_and_fails_operation(self):
        status, _, errors = self.run_transaction(restore_error=True)
        self.assertEqual(status, 1)
        self.assertIn('could not restore', errors)

    def test_headless_deployment_still_repairs(self):
        with patch.object(GUARD, 'instances', return_value=[]), \
             patch.object(GUARD.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(GUARD.transaction(['git', 'restore', '.']), 0)
        self.assertEqual(run.call_args_list[-1].args[0][-2:], ['permissions', 'fix'])
