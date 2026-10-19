"""Verify deployment ordering and recovery without touching the desktop."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'commands/git-transaction.py'
SPEC = importlib.util.spec_from_file_location('git_transaction', PATH)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class GitTransactionTest(unittest.TestCase):
    def test_wrapper_routes_writes_aliases_and_global_options_through_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            wrapper = directory / 'wrapper'
            wrapper.write_text((PATH.parent / 'git').read_text().replace(
                '(( EUID == 0 ))', '(( 0 == 0 ))').replace(
                '(( EUID != 0 ))', '(( 0 != 0 ))'))
            (directory / 'require-root').write_text('')
            for name, output in [('git', 'direct'), ('python3', 'guard')]:
                executable = directory / name
                executable.write_text(f'#!/bin/sh\nprintf "{output}\\n"\n')
                executable.chmod(0o755)
            for args, expected in [(['status'], 'direct'), (['push'], 'direct'),
                                   (['pull'], 'guard'), (['restore', '.'], 'guard'),
                                   (['custom-alias'], 'guard'),
                                   (['-c', 'color.ui=false', 'pull'], 'guard')]:
                with self.subTest(args=args):
                    result = subprocess.run(['bash', str(wrapper), *args],
                                            env=dict(os.environ, PATH=f'{directory}:/usr/bin:/bin'),
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), expected)

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
