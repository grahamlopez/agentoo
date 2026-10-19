"""Forward logind resume signals to this Hyprland session; no polling or root."""
import fcntl
import os
from pathlib import Path
import select
import signal
import socket
import subprocess


RESUME = (b"/org/freedesktop/login1: "
          b"org.freedesktop.login1.Manager.PrepareForSleep (false,)")
CALLBACK = "if agentoo_lid_resume then agentoo_lid_resume() end"


def is_resume(line):
    return line.strip() == RESUME


def watch(instance, runtime):
    directory = Path(runtime) / "hypr" / instance
    # Keep one listener across config reloads; a new compositor gets its own lock.
    with (directory / "agentoo-lid-resume.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with socket.socket(socket.AF_UNIX) as compositor:
            compositor.connect(str(directory / ".socket2.sock"))
            process = subprocess.Popen([
                "gdbus", "monitor", "--system", "--dest", "org.freedesktop.login1",
                "--object-path", "/org/freedesktop/login1",
            ], stdout=subprocess.PIPE, env={**os.environ, "LC_ALL": "C"})
            try:
                pending = b""
                while True:
                    ready, _, _ = select.select([compositor, process.stdout], [], [])
                    if compositor in ready and not compositor.recv(65536):
                        return # Also exits if Hyprland crashes; no orphan watcher.
                    if process.stdout in ready:
                        data = os.read(process.stdout.fileno(), 65536)
                        if not data:
                            raise RuntimeError("logind resume listener disconnected")
                        pending += data
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            if is_resume(line):
                                subprocess.run([
                                    "hyprctl", "-i", instance, "eval", CALLBACK,
                                ], check=True, timeout=5, stdout=subprocess.DEVNULL)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                process.stdout.close()


if __name__ == "__main__":
    def stop(_signum, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    watch(os.environ["HYPRLAND_INSTANCE_SIGNATURE"], os.environ["XDG_RUNTIME_DIR"])
