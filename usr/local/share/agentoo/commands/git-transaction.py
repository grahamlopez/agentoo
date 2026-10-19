#!/usr/bin/env python3
"""Bracket live system Git writes with Hyprland reload suspension."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


def ipc(runtime, signature, *args):
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime))
    result = subprocess.run(
        ['/usr/bin/hyprctl', '--instance', signature, *args],
        env=env, text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'hyprctl failed')
    return result.stdout.strip()


def configure(runtime, signature, disabled):
    result = ipc(runtime, signature, 'eval',
                 'hl.config({ misc = { disable_autoreload = '
                 + ('true' if disabled else 'false') + ' } })')
    if result != 'ok':
        raise RuntimeError(f'Hyprland rejected reload setting: {result}')


def instances():
    for directory in Path('/run/user').glob('*/hypr/*'):
        if directory.is_dir() and directory.parent.parent.name.isdecimal():
            yield directory.parent.parent, directory.name


def transaction(command):
    paused = []
    status = 1
    try:
        for runtime, signature in instances():
            # Ignore stale instance directories, but never silently ignore failure
            # to pause a compositor that answered the option query.
            try:
                option = json.loads(ipc(runtime, signature, '-j', 'getoption',
                                        'misc.disable_autoreload'))
            except (RuntimeError, subprocess.TimeoutExpired):
                continue
            previous = option['bool']
            if not isinstance(previous, bool):
                raise RuntimeError('invalid Hyprland autoreload option')
            paused.append((runtime, signature, previous))
            configure(runtime, signature, True)
        try:
            status = subprocess.run(command).returncode
        finally:
            # Also covers reset/restore, absent hooks, and partially failed Git
            # operations. Do not reload a configuration that failed repair.
            repaired = subprocess.run(
                ['/usr/local/bin/agentoo', 'permissions', 'fix']).returncode == 0
            if repaired:
                for runtime, signature, _ in paused:
                    try:
                        result = ipc(runtime, signature, 'reload')
                        if result != 'ok':
                            raise RuntimeError(result)
                    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                        print(f'agentoo: Hyprland reload failed: {error}', file=sys.stderr)
                        status = status or 1
            else:
                print('agentoo: permission repair failed; skipping Hyprland reload.', file=sys.stderr)
                status = status or 1
    finally:
        for runtime, signature, previous in reversed(paused):
            try:
                configure(runtime, signature, previous)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                print(f'agentoo: could not restore Hyprland automatic reload: {error}', file=sys.stderr)
                status = status or 1
    return status if status >= 0 else 128 - status


def main():
    # Serialize deployments, including their permission repair and final reload.
    directory = Path('/run/agentoo')
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / 'git-transaction.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        def interrupted(number, _frame):
            raise SystemExit(128 + number)
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        return transaction(sys.argv[1:])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'agentoo: Git deployment guard failed: {error}', file=sys.stderr)
        sys.exit(1)
