"""Read the installer's single host assignment as data, never as shell code."""
from pathlib import Path
import re

SELECTOR = Path('/etc/agentoo/target-host')
HOST_NAME = r'[A-Za-z0-9][A-Za-z0-9_-]*'


def read_host(selector):
    match = re.fullmatch(r'\s*GENTOO_TARGET_HOST="(' + HOST_NAME + r')"\s*', selector.read_text())
    if match is None:
        raise ValueError(f'{selector}: expected GENTOO_TARGET_HOST="name"')
    return match[1]
