"""Run Python discovery and Lua regression scripts from a checkout or installation."""
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    tests = Path(__file__).resolve().parent
    root = tests.parents[4]
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(tests)], cwd=root)
    if result.returncode:
        return result.returncode
    lua = shutil.which('lua')
    if lua is None:
        print('Skipped Lua regression tests: lua is not installed.', file=sys.stderr)
        return 0
    for script in sorted(tests.glob('test_*.lua')):
        result = subprocess.run([lua, str(script)], cwd=root)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
