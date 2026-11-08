#!/usr/bin/env python3
"""Supply Kitty's selected Agentoo host configuration."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host_selection import read_host


def host_config(hosts):
    host = read_host()
    try:
        return (hosts / f"{host}.conf").read_text()
    except FileNotFoundError:
        return ""


if __name__ == "__main__":
    try:
        sys.stdout.write(host_config(Path("/etc/xdg/kitty/hosts")))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Agentoo Kitty configuration: {error}", file=sys.stderr)
        sys.exit(1)
