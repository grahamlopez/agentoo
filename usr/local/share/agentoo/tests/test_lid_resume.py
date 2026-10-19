"""Exercise resume forwarding, duplicate prevention, and compositor-exit cleanup."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "hypr/lid-resume.py"
spec = importlib.util.spec_from_file_location("lid_resume", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResumeTests(unittest.TestCase):
    def test_signal_filter(self):
        self.assertTrue(module.is_resume(module.RESUME))
        self.assertFalse(module.is_resume(module.RESUME.replace(b"false", b"true")))
        self.assertFalse(module.is_resume(b"unrelated signal (false,)"))

    def test_session_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix="lid-resume-") as temporary:
            root = Path(temporary)
            directory = root / "hypr/test-instance"
            directory.mkdir(parents=True)
            os.mkfifo(root / "signals")
            signals = os.open(root / "signals", os.O_RDWR)
            for name, body in {
                "gdbus": ('import os\n'
                          'for line in open(os.environ["SIGNALS"]):\n'
                          '    print(line, end="", flush=True)\n'),
                "hyprctl": ('import os, sys\n'
                            'with open(os.environ["CALLS"], "a") as f:\n'
                            '    f.write(repr(sys.argv[1:]) + "\\n")\n'),
            }.items():
                executable = root / name
                executable.write_text("#!" + sys.executable + "\n" + body)
                executable.chmod(0o755)
            environment = {
                **os.environ, "PATH": str(root) + ":" + os.environ["PATH"],
                "HYPRLAND_INSTANCE_SIGNATURE": "test-instance",
                "XDG_RUNTIME_DIR": str(root), "SIGNALS": str(root / "signals"),
                "CALLS": str(root / "calls"),
            }
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(directory / ".socket2.sock"))
                server.listen()
                server.settimeout(3)
                watcher = subprocess.Popen([sys.executable, str(SOURCE)], env=environment)
                connection = None
                try:
                    connection, _ = server.accept()
                    duplicate = subprocess.run([sys.executable, str(SOURCE)],
                                               env=environment, timeout=3)
                    self.assertEqual(duplicate.returncode, 0)
                    os.write(signals, module.RESUME.replace(b"false", b"true") + b"\n")
                    os.write(signals, module.RESUME + b"\n")
                    deadline = time.monotonic() + 3
                    while not (root / "calls").exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    lines = (root / "calls").read_text().splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertIn("test-instance", lines[0])
                    self.assertIn(module.CALLBACK, lines[0])
                    connection.close()
                    connection = None
                    self.assertEqual(watcher.wait(timeout=3), 0)
                finally:
                    if connection is not None:
                        connection.close()
                    if watcher.poll() is None:
                        watcher.terminate()
                        watcher.wait(timeout=3)
                    os.close(signals)


if __name__ == "__main__":
    unittest.main()
