"""Wallpaper command contracts with an isolated fake Wayland client."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BIN = Path(__file__).resolve().parents[3] / 'bin'
spec = importlib.util.spec_from_loader('desktop', importlib.machinery.SourceFileLoader('desktop', str(BIN / 'agentoo-desktop')))
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class Wallpaper(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'runtime').mkdir()
        (self.root / 'bin').mkdir()
        self.image = self.root / 'an image; $literal.jpg'
        self.image.write_bytes(b'fake image')
        fake = self.root / 'bin/swaybg'
        fake.write_text('#!' + sys.executable + '\n'
                        'import os,sys,time\n'
                        'if os.environ.get("FAIL_IMAGE"):\n'
                        ' print("Failed to load image", file=sys.stderr, flush=True)\n'
                        'time.sleep(60)\n')
        fake.chmod(0o755)
        self.environment = dict(os.environ, HOME=str(self.root),
            XDG_STATE_HOME=str(self.root / 'state'), XDG_RUNTIME_DIR=str(self.root / 'runtime'),
            WAYLAND_DISPLAY='test-wallpaper', PATH=str(fake.parent) + ':' + os.environ['PATH'])
        self.environment.pop('FAIL_IMAGE', None)
        self.patch = patch.dict(os.environ, self.environment, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.clear)

    def command(self, *args, **environment):
        return subprocess.run([str(BIN / 'agentoo'), 'desktop', *args],
            env=dict(os.environ, **environment), capture_output=True, text=True, timeout=8)

    def clear(self):
        self.command('wallpaper', 'clear')

    def record(self):
        return next((self.root / 'runtime/agentoo').glob('wallpaper-*.json'))

    def test_help_and_completion_without_effects(self):
        for args in [(), ('--help',), ('wallpaper', '--help'),
                     ('wallpaper', 'set', '--help'), ('wallpaper', 'clear', '--help'),
                     ('wallpaper', 'restore', '--help')]:
            result = self.command(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)
        result = subprocess.run([str(BIN / 'agentoo'), '__complete', '4', 'desktop', 'wallpaper', 'set', ''],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('files', result.stdout)
        self.assertFalse((self.root / 'state').exists())

    def test_set_replace_restore_clear(self):
        result = self.command('wallpaper', 'set', str(self.image))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.command('wallpaper').stdout, str(self.image) + '\n')
        first = json.loads(self.record().read_text())
        self.assertEqual(self.command('wallpaper', 'restore').returncode, 0)
        second = json.loads(self.record().read_text())
        self.assertNotEqual(first['pid'], second['pid'])
        try:
            descriptor = os.pidfd_open(first['pid'])
        except ProcessLookupError:
            pass
        else:
            try:
                self.assertTrue(select.select([descriptor], [], [], 0)[0])
            finally:
                os.close(descriptor)
        self.assertEqual(self.command('wallpaper', 'clear').returncode, 0)
        self.assertEqual(self.command('wallpaper').stdout, '')
        self.assertFalse(self.record_exists())

    def record_exists(self):
        return bool(list((self.root / 'runtime/agentoo').glob('wallpaper-*.json')))

    def test_failed_decoder_keeps_selection_and_old_process(self):
        self.assertEqual(self.command('wallpaper', 'set', str(self.image)).returncode, 0)
        before = self.record().read_text()
        result = self.command('wallpaper', 'set', str(self.image), FAIL_IMAGE='1')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.record().read_text(), before)
        self.assertEqual(self.command('wallpaper').stdout, str(self.image) + '\n')
        os.kill(json.loads(before)['pid'], 0)

    def test_missing_image_restore_and_no_session(self):
        self.assertEqual(self.command('wallpaper', 'restore', WAYLAND_DISPLAY='').returncode, 0)
        self.assertFalse((self.root / 'state').exists())
        result = self.command('wallpaper', 'set', str(self.image), WAYLAND_DISPLAY='')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.command('wallpaper').stdout, '')
        self.assertEqual(self.command('wallpaper', 'set', str(self.image)).returncode, 0)
        self.image.unlink()
        result = self.command('wallpaper', 'restore')
        self.assertEqual(result.returncode, 1)
        self.assertIn('warning', result.stderr)
        self.assertEqual(self.command('wallpaper').stdout, str(self.image) + '\n')
        self.assertEqual(self.command('wallpaper', 'clear', WAYLAND_DISPLAY='').returncode, 0)

    def test_stale_record_does_not_signal_unrelated_process(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            record = desktop.runtime_directory() / 'wallpaper-stale.json'
            record.write_text(json.dumps({'pid': child.pid, 'start': 'wrong-start-time'}))
            self.assertEqual(self.command('wallpaper', 'clear').returncode, 0)
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait()

    def test_xdg_fallback_and_invalid_arguments(self):
        with patch.dict(os.environ, XDG_STATE_HOME='relative'):
            self.assertEqual(desktop.state_directory(), self.root / '.local/state/agentoo')
        self.assertEqual(self.command('wallpaper', 'set').returncode, 2)
        self.assertEqual(self.command('wallpaper', '--unknown').returncode, 2)
        self.assertFalse((self.root / 'state').exists())


if __name__ == '__main__':
    unittest.main()
