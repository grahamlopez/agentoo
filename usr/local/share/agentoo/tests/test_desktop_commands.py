"""Desktop command contracts without a compositor or hardware writes."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import os
import signal
import time
import tempfile
import unittest
from unittest.mock import patch

BIN = Path(__file__).resolve().parents[3] / 'bin'


def load(name):
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, str(BIN / ('agentoo-' + name))))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesktopCommands(unittest.TestCase):
    def test_nested_backlight_preserves_adjustment(self):
        display = load('display')
        backlight = display.display_backlight
        for direction, option in [('up', '-inc'), ('down', '-dec')]:
            with self.subTest(direction=direction), \
                    patch.object(display.sys, 'argv', ['agentoo-display', 'backlight', direction]), \
                    patch.object(backlight.Path, 'glob', return_value=[Path('/sys/class/backlight/panel')]), \
                    patch.object(backlight.Path, 'is_dir', return_value=True), \
                    patch.object(backlight.os, 'execvp') as execute, \
                    patch.object(display, 'hyprctl') as compositor, \
                    patch.object(display.time, 'sleep') as delay:
                display.main()
                execute.assert_called_once_with('xbacklight',
                    ['xbacklight', '-ctrl', 'panel', '-perceived', option, '5'])
                compositor.assert_not_called()
                delay.assert_not_called()

    def test_help_is_safe_at_leaf(self):
        for command, leaf in [('display', 'backlight'), ('screenshot', 'region'), ('git', 'enable-write'), ('git', 'setup-hooks')]:
            for prefix in [[str(BIN / 'agentoo'), command], [str(BIN / ('agentoo-' + command))]]:
                result = subprocess.run([*prefix, leaf, '--help'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_region_cancel_does_not_capture(self):
        screenshot = load('screenshot')
        with patch.object(screenshot.sys, 'argv', ['agentoo-screenshot', 'region']), patch.object(screenshot.shutil, 'which', return_value='/tool'), patch.object(screenshot, 'capture_process', return_value=subprocess.CompletedProcess([], 1, '')) as run:
            self.assertEqual(screenshot.main(), 1)
            self.assertEqual(run.call_count, 1)

    def test_capture_failure_removes_private_file(self):
        screenshot = load('screenshot')
        with tempfile.TemporaryDirectory() as home, patch.dict(screenshot.os.environ, HOME=home), patch.object(screenshot.sys, 'argv', ['agentoo-screenshot', 'full']), patch.object(screenshot.shutil, 'which', return_value='/tool'), patch.object(screenshot, 'capture_process', return_value=subprocess.CompletedProcess([], 1)):
            previous = screenshot.os.umask(0o077)
            try:
                self.assertEqual(screenshot.main(), 1)
                self.assertEqual(list((Path(home) / 'Downloads/Screenshots').iterdir()), [])
            finally:
                screenshot.os.umask(previous)

    def test_pid_termination_stops_capture_and_removes_file(self):
        with tempfile.TemporaryDirectory() as home:
            directory = Path(home)
            grim = directory / 'grim'
            pidfile = directory / 'child.pid'
            grim.write_text('#!/usr/bin/env python3\nimport os,time\nfrom pathlib import Path\n'
                            + f'Path({str(pidfile)!r}).write_text(str(os.getpid()))\n'
                            + 'time.sleep(30)\n')
            grim.chmod(0o755)
            child = subprocess.Popen([str(BIN / 'agentoo-screenshot'), 'full'],
                                     env=dict(os.environ, HOME=home, PATH=f'{home}:' + os.environ['PATH']),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pidfile.exists())
                capture_pid = int(pidfile.read_text())
                child.send_signal(signal.SIGTERM)
                child.communicate(timeout=3)
                self.assertEqual(child.returncode, 143)
                self.assertEqual(list((directory / 'Downloads/Screenshots').iterdir()), [])
                with self.assertRaises(ProcessLookupError):
                    os.kill(capture_pid, 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_git_forwarding_preserves_arguments(self):
        git = load('git')
        args = ['-c', 'alias.example=!printf hello', 'example', '--no-input', '--help']
        with patch.object(git.os, 'geteuid', return_value=0):
            command = git.git_command(args)
        self.assertEqual(command[-len(args):], args)
        self.assertIn(str(git.SHARE / 'lib/git_transaction.py'), command)


if __name__ == '__main__':
    unittest.main()
