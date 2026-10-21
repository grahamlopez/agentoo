"""Wallpaper selection and session initialization; no work on import."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.common import atomic_write


def state_directory():
    value = os.environ.get('XDG_STATE_HOME', '')
    return (Path(value) if value and Path(value).is_absolute() else Path.home() / '.local/state') / 'agentoo'


def selection(path):
    try:
        value = path.read_text().removesuffix('\n')
    except FileNotFoundError:
        return None
    if not value or not Path(value).is_absolute() or '\n' in value or '\0' in value:
        raise RuntimeError(f'Invalid wallpaper selection in {path}')
    return value


def process_identity(pid):
    # Linux start time distinguishes a stale PID from a reused one. Open a pidfd
    # before checking it, so a later signal cannot target a replacement process.
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def stop_managed(saved):
    try:
        pid = saved['pid']
        if not isinstance(pid, int) or pid <= 1:
            return
        descriptor = os.pidfd_open(pid)
        try:
            if process_identity(pid) == saved['start']:
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                if not select.select([descriptor], [], [], 2)[0]:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
        finally:
            os.close(descriptor)
    except (FileNotFoundError, ProcessLookupError, ValueError, KeyError, TypeError):
        pass


def runtime_directory():
    value = os.environ.get('XDG_RUNTIME_DIR', '')
    if not value or not Path(value).is_absolute():
        raise RuntimeError('XDG_RUNTIME_DIR must name the current user runtime directory')
    directory = Path(value) / 'agentoo'
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory


def apply_image(image, runtime):
    if not os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('A running Wayland session is required')
    executable = shutil.which('swaybg')
    if not executable:
        raise RuntimeError('Install @gui-desktop for swaybg')
    image = Path(image).expanduser().absolute()
    if '\n' in str(image) or '\0' in str(image):
        raise RuntimeError('Image paths cannot contain newlines or NUL bytes')
    if not image.is_file():
        raise RuntimeError(f'Image is not a regular file: {image}')
    with image.open('rb'):
        pass
    # Separate records for simultaneous Wayland sessions; no global pkill.
    session = hashlib.sha256(os.environ['WAYLAND_DISPLAY'].encode()).hexdigest()[:16]
    record = runtime / ('wallpaper-' + session + '.json')
    log = runtime / ('wallpaper-' + session + '.log')
    with log.open('w+') as errors:
        child = subprocess.Popen([executable, '--image', str(image), '--mode', 'fill'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
            start_new_session=True)
        try:
            identity = process_identity(child.pid)
            # swaybg has no readiness protocol. Catch immediate compositor and
            # decoder failures, including decoder errors that do not exit.
            try:
                child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
            errors.seek(0)
            diagnostic = errors.read()
            if child.poll() is not None or 'failed' in diagnostic.lower() or 'error' in diagnostic.lower():
                raise RuntimeError('swaybg could not display the image: ' + diagnostic.strip())
            old = json.loads(record.read_text()) if record.exists() else None
            atomic_write(record, json.dumps({'pid': child.pid, 'start': identity}))
            if old is not None:
                stop_managed(old)
        except BaseException:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            raise
    return str(image)


def run(args):
    state = state_directory()
    saved = state / 'wallpaper'
    if args.action is None:
        value = selection(saved)
        if value is not None:
            print(value)
        return 0
    if args.action == 'startup' and selection(saved) is None:
        return 0
    os.umask(0o077)
    state.mkdir(parents=True, exist_ok=True)
    # One lock serializes selection updates and process replacement. Readers see
    # an entire old or new selection through atomic replacement.
    with (state / 'wallpaper.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'clear':
            value = os.environ.get('XDG_RUNTIME_DIR', '')
            if value and Path(value).is_absolute():
                runtime = Path(value) / 'agentoo'
                for record in runtime.glob('wallpaper-*.json'):
                    stop_managed(json.loads(record.read_text()))
                    record.unlink(missing_ok=True)
            saved.unlink(missing_ok=True)
            print('Wallpaper selection cleared.', file=sys.stderr)
            return 0
        image = args.file if args.action == 'set' else selection(saved)
        if image is None:
            return 0
        if args.action == 'startup' and not Path(image).is_file():
            print(f'agentoo desktop: warning: remembered image is missing: {image}', file=sys.stderr)
            return 1
        applied = apply_image(image, runtime_directory())
        if args.action == 'set':
            atomic_write(saved, applied + '\n')
            print(f'Wallpaper set: {applied}', file=sys.stderr)
    return 0



if __name__ == '__main__':
    def interrupted(number, _frame):
        raise SystemExit(128 + number)

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if len(sys.argv) != 1:
            raise RuntimeError('Internal wallpaper initialization takes no arguments')
        raise SystemExit(run(SimpleNamespace(action='startup')))
    except (OSError, RuntimeError) as error:
        print(f'agentoo desktop: {error}', file=sys.stderr)
        raise SystemExit(1)
