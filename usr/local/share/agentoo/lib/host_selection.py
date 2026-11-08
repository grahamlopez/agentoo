"""Read the selected Agentoo target through eselect's native profile reporting."""
import re
import subprocess
import sys

HOST_NAME = r'[A-Za-z0-9][A-Za-z0-9_-]*'


def read_host():
    result = subprocess.run(['eselect', '--brief', '--colour=no', 'profile', 'show'],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('eselect profile show failed: ' + result.stderr.strip())
    match = re.fullmatch(r'\s*agentoo:hosts/(' + HOST_NAME + r')\s*', result.stdout)
    if match is None:
        raise ValueError('select an Agentoo host profile with eselect profile set agentoo:hosts/NAME; '
                         f'current profile: {result.stdout.strip() or "(unset)"}')
    return match[1]


if __name__ == '__main__':
    try:
        print(read_host())
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Agentoo target: {error}', file=sys.stderr)
        sys.exit(1)
